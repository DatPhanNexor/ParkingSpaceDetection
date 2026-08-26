from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Optional, Union
import math
import os
import platform
import subprocess
import sys
import threading
import tkinter as tk
import time
from urllib.parse import urlparse
from uuid import uuid4

import cv2
import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk

_APP_MODULE_DIR = Path(__file__).resolve().parent
if str(_APP_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_MODULE_DIR))

from billing_manager import (
    BillingConfig,
    BillingManager,
    ParkingObservation,
    VideoTrackAssigner,
    format_duration,
    format_vnd,
)
from detection_engine import DetectionEngine, EngineSettings, VisualState

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".m4v"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
CameraSource = Union[int, str]


@dataclass(frozen=True)
class TaggedInferenceResult:
    """Inference output tied to the submitted frame and run."""

    session_id: int
    frame_id: int
    visual: VisualState
    rendered_frame: object
    source_time_seconds: float = 0.0
    run_id: str = ""


def inference_result_is_current(result: TaggedInferenceResult, session_id: int) -> bool:
    return result.session_id == session_id


def should_submit_inference(frame_id: int, every: int, worker_busy: bool) -> bool:
    if worker_busy:
        return False
    interval = max(int(every), 1)
    return frame_id == 1 or frame_id % interval == 0


def normalize_camera_source(raw: object) -> CameraSource:
    """Validate an OpenCV camera index or supported network camera URL."""
    if isinstance(raw, bool):
        raise ValueError("Camera source is invalid.")
    if isinstance(raw, int):
        if raw < 0:
            raise ValueError("Camera index must be non-negative.")
        return raw
    value = str(raw).strip()
    if not value:
        raise ValueError("Camera source is required.")
    
    # Handle the UI text formats explicitly
    if value == "0 - DroidCam":
        return 0
    if value == "1 - Webcam":
        return 1
        
    if value.isdigit():
        return int(value)
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https", "rtsp"} or not parsed.hostname:
        raise ValueError("Camera source must be an index or HTTP/HTTPS/RTSP URL.")
    if any(ch.isspace() for ch in value):
        raise ValueError("Camera URL cannot contain spaces.")
    return value


def fit_letterbox_size(image_size: tuple[int, int], viewport_size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Return resized width/height and centered x/y for a no-crop preview."""
    iw, ih = image_size
    vw, vh = viewport_size
    if iw <= 0 or ih <= 0 or vw <= 0 or vh <= 0:
        return 1, 1, 0, 0
    ratio = min(vw / float(iw), vh / float(ih))
    new_w = max(1, int(iw * ratio))
    new_h = max(1, int(ih * ratio))
    return new_w, new_h, (vw - new_w) // 2, (vh - new_h) // 2


class ParkingSpaceDesktopApp(ctk.CTkFrame):
    """Clean desktop dashboard for the original ParkingSpaceDetection project.

    Goals:
    - Desktop app only, no browser.
    - No RTSP control in the UI.
    - No sidebars that hide buttons.
    - Full-frame preview using letterbox scaling, so the video is never cropped.
    - Smooth playback: preview thread keeps moving while YOLO runs in the background.
    """

    def __init__(self, parent, project_root: Path, app_dir: Path, auth_session=None, on_action=None):
        super().__init__(parent)
        self.project_root = Path(project_root)
        self.app_dir = Path(app_dir)
        self.auth_session = auth_session
        self.on_action = on_action
        
        self._is_running = False
        self._is_closing = False
        self._logout_requested = False
        self._window_action = "exit"
        self._after_ids: set[str] = set()
        self._close_after_id: str | None = None

        self.engine = DetectionEngine(self.project_root, self.app_dir)
        self.billing_config = BillingConfig()
        self.billing_manager = BillingManager(self.billing_config)
        self.video_track_assigner = VideoTrackAssigner(self.billing_config)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.colors = {
            "bg": "#091421",
            "panel": "#0f1d30",
            "card": "#14243a",
            "card2": "#182b45",
            "soft": "#203754",
            "line": "#355375",
            "text": "#f8fbff",
            "muted": "#bdcbe0",
            "blue": "#2f8ee8",
            "green": "#38d69f",
            "orange": "#ffb833",
            "red": "#ff5d7a",
        }

        self.winfo_toplevel().title("Parking Space Detection")
        self.configure(fg_color=self.colors["bg"])
        self._load_app_logo()
        self._set_window_size()

        # Core state
        models = self.engine.list_models_for_mode("Video")
        demos = self.engine.list_demo_videos()
        self.video_sources = demos[:] if demos else ["Demo\\exp1.mp4"]
        self.input_mode = ctk.StringVar(value="Video")
        self.source_path = ctk.StringVar(value=self.video_sources[0])
        self.demo_video = ctk.StringVar(value=self.video_sources[0])
        self.model_path = ctk.StringVar(value=self.engine.default_model_for_mode("Video"))
        self.device = ctk.StringVar(value="auto")
        self.preset = ctk.StringVar(value="Balanced")
        self.parking_map_loaded = bool(self.engine.parking_map_loaded())
        self.calibrated_map_loaded = bool(self.engine.calibrated_map_loaded())
        self.use_map = ctk.BooleanVar(value=self.calibrated_map_loaded)
        self.show_boxes = ctk.BooleanVar(value=True)
        self.show_labels = ctk.BooleanVar(value=True)
        self.save_output = ctk.BooleanVar(value=True)
        self.save_history = ctk.BooleanVar(value=True)
        self.total_slots = ctk.IntVar(value=20)
        self.camera_index = ctk.StringVar(value="0 - DroidCam")
        self.camera_source = ctk.StringVar(value="0 - DroidCam")

        self.confidence = 0.25
        self.image_size = 960
        self.detect_every = 6
        self.quality_mode = "balanced"

        # Runtime state
        self.running = False
        self._shutdown_deadline = 0.0
        self.stop_event = threading.Event()
        self.stream_thread: Optional[threading.Thread] = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.detect_future: Optional[Future[TaggedInferenceResult]] = None
        self.frame_queue: Queue = Queue(maxsize=1)
        self.visual_lock = threading.Lock()
        self.latest_visual: Optional[VisualState] = None
        self.latest_rendered = None
        self.latest_csv_path = ""
        self.latest_image_path = ""
        self.latest_video_path = ""
        self.active_settings: Optional[EngineSettings] = None
        self._pending_first_frame = None
        self.preview_image_ref = None
        self._last_preview_frame = None
        self._preview_resize_job = None
        self._displayed_frames = 0
        self._detected_batches = 0
        self._last_preview_time = time.time()
        self._last_fps = 0.0
        self._session_id = 0
        self._active_session_id: Optional[int] = None
        self._capture_lock = threading.Lock()
        self._active_capture = None
        self._active_capture_session: Optional[int] = None
        self._billing_run_id = ""
        self._billing_mode = ""
        self._billing_source = ""
        self._billing_clock = 0.0
        self._billing_status = "Chờ xe"
        self._last_billed_frame_id = -1

        self._build_ui(models, demos)
        self._apply_preset("Balanced")
        self._refresh_source_controls(log_change=False)
        self.after(16, self._pump_preview) # pyright: ignore[reportArgumentType]
        self.after(350, self._refresh_billing_panel) # pyright: ignore[reportArgumentType]
        self.winfo_toplevel().protocol("WM_DELETE_WINDOW", self._on_close)
        self._log("Ready. Clean UI loaded. Full-frame preview enabled, no cropping.")
        if self.parking_map_loaded:
            self._log("Parking map loaded.")
        else:
            self._log("Parking map not loaded. Vehicle count mode only.")
        for line in self.engine.runtime_path_report():
            self._log(line)

    def after(self, ms, func=None, *args):
        # pyrefly: ignore [bad-argument-type]
        id_ = super().after(ms, func, *args)
        if hasattr(self, "_after_ids"):
            self._after_ids.add(id_)
        return id_

    # pyrefly: ignore [bad-override-param-name]
    def after_cancel(self, id_): # pyright: ignore[reportIncompatibleMethodOverride]
        if hasattr(self, "_after_ids"):
            self._after_ids.discard(id_)
        super().after_cancel(id_)

    def _request_window_close(self, action: str) -> None:
        if getattr(self, "_is_closing", False):
            return
        self._is_closing = True
        self._window_action = action
        self._logout_requested = (action == "logout")
        
        self._shutdown_deadline = time.monotonic() + 2.5
        self.stop_event.set()
        
        try:
            msg = "Đang đăng xuất..." if self._logout_requested else "Closing safely..."
            self.status_label.configure(text=msg)
            self._log(msg)
            self.run_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
        except Exception:
            pass
            
        if self._is_running:
            self._is_running = False
            self._stop()
            
        with self._capture_lock:
            if self._active_capture is not None:
                self._active_capture.release()
                self._active_capture = None
                
        try:
            self.after(180, self._finish_window_close) # pyright: ignore[reportArgumentType]
        except Exception:
            self._finish_window_close()

    def _handle_logout(self):
        self._request_window_close("logout")

    # ---------------- UI helpers ----------------
    def _set_window_size(self):
        sw = max(1, int(self.winfo_screenwidth()))
        sh = max(1, int(self.winfo_screenheight()))
        w = min(max(1100, int(sw * 0.94)), max(1, sw - 24))
        h = min(max(680, int(sh * 0.88)), max(1, sh - 60), 900)
        x = max(0, int((sw - w) / 2))
        y = max(0, int((sh - h) / 2) - 10)
        self.winfo_toplevel().geometry(f"{w}x{h}+{x}+{y}")
        self.winfo_toplevel().minsize(min(1180, w), min(720, h))

    def _load_app_logo(self):
        self.window_icon_ref = None
        self.header_logo_image = None
        try:
            png_path = self.app_dir / "assets" / "parking_logo_3d.png"
            ico_path = self.app_dir / "assets" / "parking_logo_3d.ico"
            logo = Image.open(png_path).convert("RGBA")
            icon = ImageOps.contain(logo, (64, 64), Image.Resampling.LANCZOS)
            self.window_icon_ref = ImageTk.PhotoImage(icon)
            # pyrefly: ignore [bad-argument-type]
            self.winfo_toplevel().iconphoto(True, self.window_icon_ref) # pyright: ignore[reportArgumentType]
            if platform.system() == "Windows" and ico_path.exists():
                self.winfo_toplevel().iconbitmap(default=str(ico_path))
            self.header_logo_image = ctk.CTkImage(
                light_image=logo,
                dark_image=logo,
                size=(50, 50),
            )
        except (OSError, ValueError, RuntimeError, tk.TclError):
            self.window_icon_ref = None
            self.header_logo_image = None

    def _font(self, size: int, weight: str = "normal"):
        # pyrefly: ignore [bad-argument-type]
        return ctk.CTkFont(size=size, weight=weight) # pyright: ignore[reportArgumentType]

    def _label(self, parent, text: str, size: int = 12, weight: str = "normal", color: Optional[str] = None):
        return ctk.CTkLabel(parent, text=text, font=self._font(size, weight), text_color=color or self.colors["text"])

    def _card(self, parent, **grid_kwargs):
        frame = ctk.CTkFrame(
            parent,
            fg_color=self.colors["card"],
            border_width=1,
            border_color=self.colors["line"],
            corner_radius=10,
        )
        frame.grid(**grid_kwargs)
        return frame

    def _build_ui(self, models, demos):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=0, minsize=60)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(2, 0))
        header.grid_columnconfigure(0, weight=0)
        header.grid_columnconfigure(1, weight=1)
        header.grid_columnconfigure(2, weight=0)
        
        if self.header_logo_image is not None:
            ctk.CTkLabel(
                header,
                text="",
                image=self.header_logo_image,
                width=58,
                height=58,
                fg_color="transparent",
            ).grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
            
        title_status_container = ctk.CTkFrame(header, fg_color="transparent")
        title_status_container.grid(row=0, column=1, rowspan=2, sticky="w")
        
        self._label(title_status_container, "AI Parking Detection Dashboard", 18, "bold").pack(anchor="w")
        self.status_label = self._label(title_status_container, "Ready", 11, "normal", self.colors["muted"])
        self.status_label.pack(anchor="w")
        
        logout_btn = ctk.CTkButton(
            header, 
            text="ĐĂNG XUẤT", 
            width=120, 
            height=36, 
            corner_radius=8,
            fg_color="#ff5d7a", 
            hover_color="#e04c66",
            font=self._font(13, "bold"),
            command=self._handle_logout
        )
        logout_btn.grid(row=0, column=2, rowspan=2, sticky="e", padx=(10, 0))
        
        self.progress = ctk.CTkProgressBar(header, height=3)
        self.progress.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(2, 0))
        self.progress.set(0)

        # Clean control deck
        deck = ctk.CTkFrame(self, fg_color=self.colors["panel"], corner_radius=9)
        deck.grid(row=1, column=0, sticky="ew", padx=8, pady=(1, 2))
        for i in range(5):
            deck.grid_columnconfigure(i, weight=1, uniform="top_cards")
        deck.grid_rowconfigure(0, weight=1)

        # 1. Input card
        input_card = self._card(deck, row=0, column=0, sticky="nsew", padx=(4, 2), pady=2)
        input_card.grid_columnconfigure(0, weight=1)
        self._label(input_card, "1. Input", 10, "bold", "#7bc3ff").grid(row=0, column=0, sticky="w", padx=7, pady=(2, 0))
        self.mode_segment = ctk.CTkSegmentedButton(
            input_card,
            values=["Image", "Video", "Webcam"],
            variable=self.input_mode,
            height=25,
            font=self._font(12, "bold"),
            command=lambda _: self._refresh_source_controls(),
        )
        self.mode_segment.grid(row=1, column=0, sticky="ew", padx=6, pady=(1, 3))
        self.source_holder = ctk.CTkFrame(input_card, fg_color="transparent")
        self.source_holder.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 3))
        self.source_holder.grid_columnconfigure(0, weight=1)
        self.demo_menu = ctk.CTkOptionMenu(
            self.source_holder,
            values=self.video_sources,
            variable=self.demo_video,
            height=25,
            font=self._font(12, "normal"),
            command=self._choose_demo,
        )
        self.choose_file_btn = ctk.CTkButton(self.source_holder, text="Choose file", height=24, font=self._font(12, "bold"), command=self._choose_file)
        self.camera_menu = ctk.CTkSegmentedButton(self.source_holder, values=["0 - DroidCam", "1 - Webcam"], variable=self.camera_index, height=22, font=self._font(12, "bold"), command=self._choose_camera_index)
        self.webcam_panel = ctk.CTkFrame(
            self.source_holder,
            fg_color=self.colors["card2"],
            border_width=1,
            border_color=self.colors["line"],
            corner_radius=7,
        )
        self.webcam_panel.grid_columnconfigure(0, weight=1)
        self.webcam_panel.grid_columnconfigure(1, weight=0)
        self._label(self.webcam_panel, "Active Webcam", 11, "bold", "#7bc3ff").grid(row=0, column=0, sticky="w", padx=8, pady=(1, 0))
        self._label(self.webcam_panel, "DroidCam / Phone Camera", 12, "bold").grid(row=1, column=0, sticky="w", padx=8, pady=(0, 0))
        self._label(self.webcam_panel, "Realtime detection source", 10, "normal", self.colors["muted"]).grid(row=2, column=0, sticky="w", padx=8, pady=(0, 0))
        self.webcam_status_label = self._label(self.webcam_panel, "Status: Not connected", 10, "bold", self.colors["orange"])
        self.webcam_status_label.grid(row=3, column=0, sticky="w", padx=8, pady=(1, 4))
        self.scan_btn = ctk.CTkButton(
            self.webcam_panel,
            text="Check DroidCam",
            height=24,
            width=108,
            font=self._font(12, "bold"),
            command=self._check_droidcam,
        )
        self.scan_btn.grid(row=3, column=1, sticky="e", padx=(6, 7), pady=(1, 4))

        # 2. Model card
        model_card = self._card(deck, row=0, column=1, sticky="nsew", padx=2, pady=2)
        model_card.grid_columnconfigure(0, weight=1)
        self._label(model_card, "2. Model", 10, "bold", "#7bc3ff").grid(row=0, column=0, sticky="w", padx=7, pady=(2, 0))
        self.model_menu = ctk.CTkOptionMenu(
            model_card,
            values=models or [self.engine.default_model_for_mode("Video")],
            variable=self.model_path,
            height=25,
            font=self._font(12),
            command=self._on_model_selected,
        )
        self.model_menu.grid(row=1, column=0, sticky="ew", padx=6, pady=(1, 3))
        ctk.CTkSegmentedButton(model_card, values=["auto", "cpu", "cuda"], variable=self.device, height=24, font=self._font(12, "bold")).grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 3))

        # 3. Quality card
        quality_card = self._card(deck, row=0, column=2, sticky="nsew", padx=2, pady=2)
        quality_card.grid_columnconfigure(0, weight=1)
        self._label(quality_card, "3. Quality", 10, "bold", "#7bc3ff").grid(row=0, column=0, sticky="w", padx=7, pady=(2, 0))
        self.preset_segment = ctk.CTkSegmentedButton(
            quality_card,
            values=["Fast", "Balanced", "Accurate"],
            variable=self.preset,
            height=25,
            font=self._font(12, "bold"),
            command=self._apply_preset,
        )
        self.preset_segment.grid(row=1, column=0, sticky="ew", padx=6, pady=(1, 3))
        self.preset_info = self._label(quality_card, "", 10, "normal", self.colors["muted"])
        self.preset_info.grid(row=2, column=0, sticky="w", padx=6, pady=(0, 3))

        # 4. Parking card
        parking_card = self._card(deck, row=0, column=3, sticky="nsew", padx=2, pady=2)
        parking_card.grid_columnconfigure(0, weight=1)
        self._label(parking_card, "4. Parking setup", 10, "bold", "#7bc3ff").grid(row=0, column=0, sticky="w", padx=7, pady=(2, 0))
        map_text = "Parking map: Loaded" if self.parking_map_loaded else "Parking map: Not loaded"
        map_color = self.colors["green"] if self.parking_map_loaded else self.colors["orange"]
        self.parking_map_label = self._label(parking_card, map_text, 11, "bold", map_color)
        self.parking_map_label.grid(row=1, column=0, sticky="w", padx=7, pady=(1, 2))
        checks = ctk.CTkFrame(parking_card, fg_color="transparent")
        checks.grid(row=2, column=0, sticky="ew", padx=7, pady=(0, 3))
        checks.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkCheckBox(
            checks,
            text="Boxes",
            variable=self.show_boxes,
            width=86,
            height=22,
            font=self._font(12),
            command=lambda: self._on_option_toggle("show_boxes", self.show_boxes, "Boxes"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 1))
        ctk.CTkCheckBox(
            checks,
            text="Labels",
            variable=self.show_labels,
            width=86,
            height=22,
            font=self._font(12),
            command=lambda: self._on_option_toggle("show_labels", self.show_labels, "Labels"),
        ).grid(row=0, column=1, sticky="w", pady=(0, 1))
        ctk.CTkCheckBox(
            checks,
            text="Save",
            variable=self.save_output,
            width=86,
            height=22,
            font=self._font(12),
            command=lambda: self._on_option_toggle("save_video", self.save_output, "Save output"),
        ).grid(row=1, column=0, sticky="w")
        ctk.CTkCheckBox(
            checks,
            text="History",
            variable=self.save_history,
            width=86,
            height=22,
            font=self._font(12),
            command=lambda: self._on_option_toggle("save_history", self.save_history, "History"),
        ).grid(row=1, column=1, sticky="w")

        # 5. Action card
        action_card = self._card(deck, row=0, column=4, sticky="nsew", padx=(2, 4), pady=2)
        action_card.grid_columnconfigure(0, weight=1)
        self._label(action_card, "5. Action", 10, "bold", "#7bc3ff").grid(row=0, column=0, sticky="w", padx=7, pady=(2, 0))
        self.run_btn = ctk.CTkButton(
            action_card,
            text="▶ RUN",
            height=25,
            fg_color=self.colors["green"],
            hover_color="#2ac08c",
            text_color="#06131f",
            font=self._font(14, "bold"),
            command=self._run,
        )
        self.run_btn.configure(text="RUN")
        self.run_btn.grid(row=1, column=0, sticky="ew", padx=8, pady=(1, 4))
        self.stop_btn = ctk.CTkButton(action_card, text="STOP", height=25, fg_color=self.colors["red"], hover_color="#d94f6b", font=self._font(13, "bold"), command=self._stop)
        self.stop_btn.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 4))
        ctk.CTkButton(action_card, text="Open outputs", height=25, fg_color=self.colors["blue"], hover_color="#3b9bf1", font=self._font(12, "bold"), command=self._open_outputs).grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 3))

        # Horizontal stats.
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 2))
        for i in range(6):
            stats.grid_columnconfigure(i, weight=1, uniform="stats_cards")
        stats.grid_rowconfigure(0, weight=1)
        self.stat_empty = self._mini_stat(stats, 0, "EMPTY", "0", "available")
        self.stat_occ = self._mini_stat(stats, 1, "OCCUPIED", "0/0", "slots")
        self.stat_vehicle = self._mini_stat(stats, 2, "VEHICLES", "0", "parked/all")
        self.stat_rate = self._mini_stat(stats, 3, "RATE", "0%", "occupancy")
        self.stat_fps = self._mini_stat(stats, 4, "FPS", "0", "preview")
        self.stat_revenue = self._mini_stat(stats, 5, "DOANH THU", "0đ", "đã thu trong phiên")

        # Preview remains full width for Image; Video/Webcam add the billing panel.
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 1))
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=3)
        self.content_container.grid_columnconfigure(1, weight=1, minsize=380)
        self.content_container.grid_propagate(False)
        preview_card = ctk.CTkFrame(self.content_container, fg_color="#07111f", border_width=1, border_color="#42668e", corner_radius=9)
        preview_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        preview_card.grid_rowconfigure(0, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)
        preview_card.grid_propagate(False)
        self.preview_card = preview_card
        self.preview_canvas = ctk.CTkCanvas(
            preview_card,
            bg="#0a1628",
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.preview_canvas.create_text(
            20,
            20,
            anchor="nw",
            text="Choose Image / Video / Webcam, then press RUN",
            fill="#c2d2e7",
            font=("Arial", 16, "bold"),
        )
        self.preview_card.bind("<Configure>", self._on_preview_resize)
        self._build_billing_panel()

        # Log
        self.log_frame = ctk.CTkFrame(
            self,
            height=55,
            fg_color=self.colors["card"],
            border_width=1,
            border_color=self.colors["line"],
            corner_radius=7,
        )
        self.log_frame.grid(row=4, column=0, sticky="ew", padx=8, pady=(1, 8))
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(
            self.log_frame,
            height=40,
            fg_color=self.colors["card"],
            text_color="#d5e6f8",
            border_width=0,
            wrap="word",
            font=self._font(12, "normal"),
        )
        self.log_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=4)
        self.log_box.configure(state="disabled")

    def _build_billing_panel(self):
        self.billing_panel = ctk.CTkFrame(
            self.content_container,
            fg_color=self.colors["panel"],
            border_width=1,
            border_color=self.colors["line"],
            corner_radius=9,
        )
        self.billing_panel.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.billing_panel.grid_columnconfigure(0, weight=1)
        self.billing_panel.grid_rowconfigure(0, weight=0)
        self.billing_panel.grid_rowconfigure(1, weight=0)
        self.billing_panel.grid_rowconfigure(2, weight=0)
        self.billing_panel.grid_rowconfigure(3, weight=1, minsize=50)
        self.billing_panel.grid_rowconfigure(4, weight=0, minsize=30)
        self.billing_panel.grid_rowconfigure(5, weight=1, minsize=50)
        self.billing_panel.grid_rowconfigure(6, weight=0)
        self._label(self.billing_panel, "THANH TOÁN THỜI GIAN THỰC", 14, "bold", "#7bc3ff").grid(
            row=0, column=0, sticky="w", padx=12, pady=(6, 0)
        )
        self._label(self.billing_panel, "20.000đ/giờ • Làm tròn 5.000đ", 11, color=self.colors["muted"]).grid(
            row=1, column=0, sticky="w", padx=12, pady=(0, 6)
        )
        self._label(self.billing_panel, "XE ĐANG ĐỖ", 11, "bold", self.colors["green"]).grid(
            row=2, column=0, sticky="w", padx=12, pady=(0, 3)
        )
        active = ctk.CTkScrollableFrame(self.billing_panel, height=50, fg_color=self.colors["card"], corner_radius=7)
        active.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 6))
        active.grid_columnconfigure((0, 1, 2), weight=1)
        for column, text, anchor in ((0, "Vị trí", "w"), (1, "Thời gian", ""), (2, "Tạm tính", "e")):
            self._label(active, text, 10, "bold", self.colors["muted"]).grid(row=0, column=column, sticky=anchor, padx=4)
        
        self.active_billing_rows = []
        for row_index in range(1, 21):
            labels = (
                self._billing_label(active, "", is_bold=True),
                self._billing_label(active, "", is_bold=False),
                self._billing_label(active, "", is_bold=True, color=self.colors["orange"]),
            )
            for column, label in enumerate(labels):
                anchor = "w" if column == 0 else ("e" if column == 2 else "")
                label.grid(row=row_index, column=column, sticky=anchor, padx=4, pady=2)
            self.active_billing_rows.append(labels)

        self._label(self.billing_panel, "XE VỪA RỜI BÃI", 11, "bold", self.colors["orange"]).grid(
            row=4, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        recent = ctk.CTkScrollableFrame(self.billing_panel, height=50, fg_color=self.colors["card"], corner_radius=7)
        recent.grid(row=5, column=0, sticky="nsew", padx=10, pady=(0, 6))
        recent.grid_columnconfigure((0, 1, 2), weight=1)
        self.recent_billing_rows = []
        for row_index in range(6):
            labels = (
                self._billing_label(recent, "", is_bold=True),
                self._billing_label(recent, "", is_bold=False),
                self._billing_label(recent, "", is_bold=True, color=self.colors["orange"]),
            )
            for column, label in enumerate(labels):
                anchor = "w" if column == 0 else ("e" if column == 2 else "")
                label.grid(row=row_index, column=column, sticky=anchor, padx=4, pady=2)
            self.recent_billing_rows.append(labels)

        summary_frame = ctk.CTkFrame(self.billing_panel, fg_color=self.colors["card2"], corner_radius=7)
        summary_frame.grid(row=6, column=0, sticky="ew", padx=10, pady=4)
        summary_frame.grid_columnconfigure(0, weight=1)
        summary_frame.grid_rowconfigure(0, weight=0, minsize=30)
        summary_frame.grid_rowconfigure(1, weight=0, minsize=30)
        summary_frame.grid_rowconfigure(2, weight=0, minsize=34)
        self.billing_total_label = self._label(summary_frame, "Tổng đã thu trong phiên: 0đ", 12, "bold")
        self.billing_total_label.grid(row=0, column=0, sticky="w", padx=10, pady=(2, 0))
        self.billing_tracking_label = self._label(summary_frame, "Đang theo dõi: 0 xe", 11)
        self.billing_tracking_label.grid(row=1, column=0, sticky="w", padx=10)
        self.billing_status_label = self._label(summary_frame, "Trạng thái: Chờ xe", 11, "bold", self.colors["muted"])
        self.billing_status_label.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 2))

    def _mini_stat(self, parent, column: int, title: str, value: str, sub: str):
        card = self._card(parent, row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 3, 3), pady=0)
        card.grid_columnconfigure(0, weight=1)
        self._label(card, title, 10, "bold", self.colors["muted"]).grid(row=0, column=0, sticky="w", padx=7, pady=(0, 0))
        label = self._label(card, value, 16, "bold")
        label.grid(row=1, column=0, sticky="w", padx=7, pady=(0, 0))
        self._label(card, sub, 9, "normal", self.colors["muted"]).grid(row=2, column=0, sticky="w", padx=7, pady=(0, 0))
        return label

    def _update_billing_row(self, row_widgets, position: str, duration: str, fee: str):
        if not isinstance(row_widgets, tuple) or len(row_widgets) != 3:
            return
        row_widgets[0].configure(text=position)
        row_widgets[1].configure(text=duration)
        row_widgets[2].configure(text=fee)

    def _billing_label(self, parent, text: str, is_bold: bool = False, color: Optional[str] = None):
        if not hasattr(self, "_billing_font_normal"):
            self._billing_font_normal = ctk.CTkFont(family="Segoe UI", size=12, weight="normal")
            self._billing_font_bold = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        font = self._billing_font_bold if is_bold else self._billing_font_normal
        return ctk.CTkLabel(parent, text=text, font=font, text_color=color or self.colors["text"])

    def _set_billing_status(self, status: str):
        self._billing_status = status
        if hasattr(self, "billing_status_label"):
            self.billing_status_label.configure(text=f"Trạng thái: {status}")

    def _refresh_billing_panel(self):
        if getattr(self, "_is_closing", False):
            return
        try:
            if self._billing_mode not in {"Video", "Webcam"}:
                for labels in self.active_billing_rows:
                    self._update_billing_row(labels, "", "", "")
                for labels in self.recent_billing_rows:
                    self._update_billing_row(labels, "", "", "")
                self.billing_total_label.configure(text="Tổng đã thu trong phiên: 0đ")
                self.billing_tracking_label.configure(text="Đang theo dõi: 0 xe")
                self.billing_status_label.configure(text="Trạng thái: Chờ xe")
                self.stat_revenue.configure(text="0đ")
                return
            if self._billing_mode == "Webcam" and self.running:
                now = time.monotonic()
            else:
                now = self._billing_clock
            snapshot = self.billing_manager.snapshot(now=now, status=self._billing_status)
            active_sessions = list(snapshot.active_sessions)
            
            def sort_key(s):
                try:
                    return int(s.position_id)
                except ValueError:
                    return float('inf')
            
            active_sessions.sort(key=sort_key)
            
            for index, labels in enumerate(self.active_billing_rows):
                if index < len(active_sessions):
                    session = active_sessions[index]
                    pos_id_text = f"Ô {session.position_id}" if session.position_id.isdigit() else session.position_id
                    values = (
                        pos_id_text,
                        format_duration(session.duration_seconds),
                        format_vnd(session.provisional_fee_vnd),
                    )
                else:
                    values = ("", "", "")
                self._update_billing_row(labels, values[0], values[1], values[2])

            recent = list(snapshot.recent_transactions)[:6]
            for index, labels in enumerate(self.recent_billing_rows):
                if index < len(recent):
                    transaction = recent[index]
                    pos_id_text = f"Ô {transaction.position_id}" if transaction.position_id.isdigit() else transaction.position_id
                    values = (
                        pos_id_text,
                        format_duration(transaction.duration_seconds),
                        f"Thu {format_vnd(transaction.fee_vnd)}",
                    )
                else:
                    values = ("", "", "")
                self._update_billing_row(labels, values[0], values[1], values[2])
            total_text = format_vnd(snapshot.total_revenue_vnd)
            self.billing_total_label.configure(text=f"Tổng đã thu trong phiên: {total_text}")
            self.billing_tracking_label.configure(text=f"Đang theo dõi: {len(active_sessions)} xe")
            self.billing_status_label.configure(text=f"Trạng thái: {self._billing_status}")
            self.stat_revenue.configure(text=total_text)
        except Exception as exc:
            self._log(f"Cảnh báo bảng thanh toán: {exc}")
        finally:
            if not getattr(self, "_is_closing", False):
                self.after(350, self._refresh_billing_panel) # pyright: ignore[reportArgumentType]

    def _update_billing(self, result: TaggedInferenceResult, mode: str):
        if (
            result.run_id != self._billing_run_id
            or result.frame_id <= self._last_billed_frame_id
            or mode not in {"Video", "Webcam"}
            or self.stop_event.is_set()
        ):
            return
        self._last_billed_frame_id = result.frame_id
        if mode == "Video":
            self._billing_clock = max(self._billing_clock, float(result.source_time_seconds))
        else:
            self._billing_clock = float(result.source_time_seconds)
        visual = result.visual
        observations = []
        waiting_for_track = False

        slot_states = list(getattr(visual, "slot_states", []))
        stats = visual.stats
        # pyrefly: ignore [unnecessary-type-conversion]
        valid = bool(stats.measurement_valid)
        
        # If parking map is enabled (or we are in Webcam mode where map is always expected)
        use_map = True
        if mode == "Video":
            use_map = self.active_settings is not None and self.active_settings.use_calibrated_map
            
        if use_map:
            if not slot_states:
                self._set_billing_status("Chờ dữ liệu vị trí")
                if mode == "Video":
                    # pyrefly: ignore [unexpected-keyword]
                    self._log("Video có parking map nhưng chưa nhận được trạng thái từng ô.", deduplicate=True) # pyright: ignore[reportCallIssue]
                return
                
            if valid and stats.total > 0 and len(slot_states) != stats.total:
                valid = False
            if not valid:
                self._set_billing_status("Chờ dữ liệu hợp lệ")
                return
                
            # Keep track of overlay slot IDs to ensure synchronization
            overlay_slot_ids = set()
            for slot in slot_states:
                slot_id = str(getattr(slot, "slot_id"))
                overlay_slot_ids.add(slot_id)
                observations.append(
                    ParkingObservation(
                        position_id=slot_id,
                        state=str(getattr(slot, "state")).upper(),
                        timestamp=result.source_time_seconds,
                        measurement_valid=True,
                        confidence=getattr(slot, "confidence", None),
                        frame_id=result.frame_id,
                    )
                )
        else:
            # When parking map is NOT used in Video mode
            self._set_billing_status("Video chưa có bản đồ vị trí để tính phí chính xác")
            # We explicitly disable billing tracking when map is missing as requested
            return

        transactions = self.billing_manager.update(observations, timestamp=result.source_time_seconds)
        snapshot = self.billing_manager.snapshot(now=result.source_time_seconds)
        if waiting_for_track:
            self._set_billing_status("Chưa đủ dữ liệu theo dõi")
        else:
            self._set_billing_status("Đang tính phí" if snapshot.active_sessions else "Chờ xe")
        if transactions:
            if self.save_history.get():
                csv_path = self.app_dir / "desktop_outputs" / "csv" / "billing_transactions.csv"
                try:
                    self.billing_manager.export_transactions_csv(csv_path, transactions)
                except Exception as exc:
                    self._log(f"Cảnh báo: Không thể ghi lịch sử thanh toán: {exc}")
            for transaction in transactions:
                self._log(
                    f"{transaction.position_id} đã rời bãi. "
                    f"Thời gian: {format_duration(transaction.duration_seconds)}. "
                    f"Phí: {format_vnd(transaction.fee_vnd)}. Doanh thu đã được cập nhật."
                )

    # ---------------- Controls ----------------
    def _on_model_selected(self, value):
        corrected, warning = self.engine.normalize_model_for_mode(self.input_mode.get(), value)
        if corrected != value:
            self.model_path.set(corrected)
            self._log(warning)

    def _refresh_model_options(self, mode: Optional[str] = None, log_change: bool = True):
        mode = mode or self.input_mode.get()
        values = self.engine.list_models_for_mode(mode)
        corrected, warning = self.engine.normalize_model_for_mode(mode, self.model_path.get())
        if corrected not in values:
            values = [corrected] + [v for v in values if v != corrected]
        self.model_menu.configure(values=values)
        if self.model_path.get() != corrected:
            self.model_path.set(corrected)
            if log_change and warning:
                self._log(warning)
        elif log_change:
            self._log(f"{mode} model list: {', '.join(values)}")

    def _choose_camera_index(self, value):
        self.camera_source.set(str(value))
        self.source_path.set(str(value))

    def _refresh_source_controls(self, log_change: bool = True):
        if self.running:
            self._log("Stopping current stream before switching input mode...")
            self._stop()
        for widget in (self.demo_menu, self.choose_file_btn, self.camera_menu, self.webcam_panel):
            widget.grid_forget()
        mode = self.input_mode.get()
        if mode == "Image":
            self._billing_mode = ""
            self._billing_run_id = ""
            self._last_billed_frame_id = -1
            self.billing_manager.reset_run()
            self.video_track_assigner.reset()
        self._apply_mode_specific_layout(mode)
        self._refresh_model_options(mode, log_change=log_change)
        if mode == "Video":
            self.demo_menu.grid(row=0, column=0, sticky="ew", pady=(0, 3))
            self.choose_file_btn.grid(row=1, column=0, sticky="ew", pady=(0, 0))
            self.source_path.set(self.demo_video.get())
            self.use_map.set(self.calibrated_map_loaded)
            self.total_slots.set(20)
        elif mode == "Image":
            self.choose_file_btn.grid(row=0, column=0, sticky="ew", pady=(0, 0))
            self.total_slots.set(20)
        else:
            self.camera_index.set("0 - DroidCam")
            self.camera_source.set("0 - DroidCam")
            self.source_path.set("0 - DroidCam")
            self.camera_menu.grid(row=0, column=0, sticky="ew", pady=(0, 2))
            self.webcam_panel.grid(row=1, column=0, sticky="ew", pady=(0, 1))
            total = self.engine.boardlock_total_hint()
            self.total_slots.set(total)

    def _apply_mode_specific_layout(self, mode: str):
        if not hasattr(self, "billing_panel"):
            return
        if mode == "Image":
            self.billing_panel.grid_remove()
            self.content_container.grid_columnconfigure(0, weight=1)
            self.content_container.grid_columnconfigure(1, weight=0, minsize=0)
            self.preview_card.grid_configure(padx=0)
        else:
            self.content_container.grid_columnconfigure(0, weight=3)
            self.content_container.grid_columnconfigure(1, weight=1, minsize=380)
            self.preview_card.grid_configure(padx=(0, 4))
            self.billing_panel.grid()
            
            self.billing_panel.grid_rowconfigure(3, weight=1, minsize=50)
            self.billing_panel.grid_rowconfigure(5, weight=1, minsize=50)

    def _choose_demo(self, value):
        self.source_path.set(value)

    def _choose_file(self):
        from tkinter import filedialog
        mode = self.input_mode.get()
        if mode == "Image":
            types = [("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        else:
            types = [("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.m4v"), ("All files", "*.*")]
        try:
            path = filedialog.askopenfilename(title=f"Choose {mode.lower()} file", filetypes=types)
        except Exception as exc:
            self._log(f"Choose file failed: {exc}")
            return
        if path:
            selected = Path(path).expanduser().resolve()
            suffix = selected.suffix.lower()
            if mode == "Video" and suffix not in VIDEO_EXTENSIONS:
                self._log(f"Unsupported video file: {selected}. Use .mp4, .avi, .mov, .mkv, .wmv, or .m4v.")
                return
            if mode == "Image" and suffix not in IMAGE_EXTENSIONS:
                self._log(f"Unsupported image file: {selected}. Use .jpg, .jpeg, .png, or .bmp.")
                return
            if mode == "Video":
                value = str(selected)
                if value not in self.video_sources:
                    self.video_sources.insert(0, value)
                    self.demo_menu.configure(values=self.video_sources)
                self.demo_video.set(value)
            if self.running and mode in {"Video", "Webcam"}:
                self._log("Stopping current stream before switching source...")
                self._stop()
            self.source_path.set(str(selected))
            self._log(f"Selected {mode.lower()} file: {selected}")

    def _set_webcam_status(self, status: str):
        color = self.colors["green"] if status == "Ready" else self.colors["orange"]
        self.webcam_status_label.configure(text=f"Status: {status}", text_color=color)

    def _check_droidcam(self):
        self._log("Checking DroidCam / Phone Camera on camera 0...")
        def job():
            cap = None
            try:
                cap = cv2.VideoCapture(0)
                opened = bool(cap is not None and cap.isOpened())
                ok = False
                if opened:
                    ok, frame = cap.read()
                    ok = bool(ok and frame is not None and frame.size > 0)
            except Exception as exc:
                self.after(0, lambda e=exc: self._log(f"Cannot open DroidCam on camera 0. Please check DroidCam connection and camera permission. Detail: {e}")) # pyright: ignore[reportArgumentType]
                self.after(0, lambda: self._set_webcam_status("Not connected")) # pyright: ignore[reportArgumentType]
                return
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass

            def done():
                if opened and ok:
                    self._set_webcam_status("Ready")
                    self.camera_index.set("0 - DroidCam")
                    self.camera_source.set("0 - DroidCam")
                    self._log("DroidCam detected on camera 0. Automatically selected.")
                else:
                    self._set_webcam_status("Not connected")
                    self._log("Cannot open DroidCam on camera 0. Please check DroidCam connection and camera permission.")

            self.after(0, done) # pyright: ignore[reportArgumentType]
        threading.Thread(target=job, daemon=True).start()

    def _change_capacity(self, delta: int):
        self.total_slots.set(max(1, min(200, self.total_slots.get() + delta)))

    def _on_option_toggle(self, attr: str, variable: ctk.BooleanVar, label: str):
        enabled = bool(variable.get())
        if self.active_settings is not None:
            setattr(self.active_settings, attr, enabled)
        self._log(f"{label} {'enabled' if enabled else 'disabled'}.")

    def _apply_preset(self, value=None):
        preset = value or self.preset.get()
        if preset == "Fast":
            self.quality_mode = "fast"
            self.confidence = 0.32
            self.image_size = 640
            self.detect_every = 10
            txt = "recommended • 640px • every 10f"
            log_text = "Quality mode: Fast | size=640 | every 10 frames"
        elif preset == "Accurate":
            self.quality_mode = "accurate"
            self.confidence = 0.22
            self.image_size = 1280
            self.detect_every = 3
            txt = "recommended • 1280px • every 3f"
            log_text = "Quality mode: Accurate | size=1280 | every 3 frames"
        else:
            self.quality_mode = "balanced"
            self.confidence = 0.25
            self.image_size = 960
            self.detect_every = 6
            txt = "recommended • 960px • every 6f"
            log_text = "Quality mode: Balanced | size=960 | every 6 frames"
        self.preset_info.configure(text=txt)
        if self.active_settings is not None:
            self.active_settings.quality_mode = self.quality_mode
            self.active_settings.confidence = self.confidence
            self.active_settings.image_size = self.image_size
            self.active_settings.detect_every_n_frames = self.detect_every
        self._log(log_text)

    def _settings(self) -> EngineSettings:
        corrected, _ = self.engine.normalize_model_for_mode(self.input_mode.get(), self.model_path.get())
        if corrected != self.model_path.get():
            self.model_path.set(corrected)
        return EngineSettings(
            model_path=corrected,
            device=self.device.get(),
            quality_mode=self.quality_mode,
            confidence=self.confidence,
            image_size=self.image_size,
            detect_every_n_frames=self.detect_every,
            total_capacity=int(self.total_slots.get()),
            use_calibrated_map=bool(self.calibrated_map_loaded),
            save_video=bool(self.save_output.get()),
            save_history=bool(self.save_history.get()),
            show_boxes=bool(self.show_boxes.get()),
            show_labels=bool(self.show_labels.get()),
        )

    # ---------------- Run pipeline ----------------
    def _run(self):
        if self.running:
            return
        mode = self.input_mode.get()
        source: CameraSource = self.source_path.get().strip()
        if mode == "Webcam":
            try:
                source = normalize_camera_source(self.camera_source.get())
            except ValueError as exc:
                self._log(str(exc))
                self.status_label.configure(text="Invalid camera source")
                return
            self.source_path.set(str(source))
        if mode in {"Image", "Video"} and not source:
            self._log("Please choose a source first.")
            return
        self._session_id += 1
        session_id = self._session_id
        self._active_session_id = session_id
        self.running = True
        self.stop_event.clear()
        self.latest_visual = None
        self.latest_rendered = None
        if self.detect_future is not None:
            try:
                self.detect_future.cancel()
            except Exception:
                pass
            self.detect_future = None
        self._displayed_frames = 0
        self._detected_batches = 0
        self._last_fps = 0.0
        self.progress.set(0)
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="Running...")
        corrected, warning = self.engine.normalize_model_for_mode(mode, self.model_path.get())
        if corrected != self.model_path.get():
            self.model_path.set(corrected)
        if warning:
            self._log(warning)
        model_path = self.engine.resolve_path(corrected)
        self._log(f"RUN {mode}: {source} | model={corrected}")
        if mode == "Webcam":
            self._log("Selected mode: Webcam")
            self._log("Device: DroidCam / Phone Camera")
            self._log(f"Source: {source}")
            self._log("Using ParkingVisionV8 bridge with latest-frame-only webcam processing.")
        self._log(f"Resolved model path: {model_path}")
        settings = self._settings()
        self.active_settings = settings
        quality_label = settings.quality_mode.capitalize()
        self._log(f"Quality mode: {quality_label} | size={settings.image_size} | every {settings.detect_every_n_frames} frames")
        if mode == "Webcam":
            total = self.engine.boardlock_total_hint()
            self.total_slots.set(total)
            settings.total_capacity = total
        if mode in {"Video", "Webcam"}:
            self._billing_run_id = f"{mode.lower()}-{session_id}-{uuid4().hex[:8]}"
            self._billing_mode = mode
            self._billing_source = str(source)
            self._billing_clock = time.monotonic() if mode == "Webcam" else 0.0
            self._last_billed_frame_id = -1
            self.billing_manager.start_run(self._billing_run_id, mode, str(source))
            self.video_track_assigner.reset()
            self._set_billing_status("Chờ xe")
            self.stat_revenue.configure(text="0đ")
        else:
            self._billing_run_id = ""
            self._billing_mode = ""
            self._billing_source = ""
            self._last_billed_frame_id = -1
            self.billing_manager.reset_run()
            self.video_track_assigner.reset()
            self._billing_status = "Chờ xe"
            self.stat_revenue.configure(text="0đ")
        if mode == "Image":
            threading.Thread(target=self._run_image_thread, args=(str(source), settings, session_id), daemon=True).start()
        else:
            self.stream_thread = threading.Thread(
                target=self._run_stream_thread,
                args=(mode, source, settings, session_id, self._billing_run_id),
                daemon=True,
            )
            self.stream_thread.start()

    def _run_image_thread(self, source: str, settings: EngineSettings, session_id: int):
        try:
            out = self.engine.run_image(source, settings)
            self.latest_visual = out.visual
            self.latest_rendered = out.rendered_frame
            self.latest_csv_path = out.csv_path or ""
            self.latest_image_path = out.image_path or ""
            self.latest_video_path = ""
            self._put_frame(out.rendered_frame)
            self.after(0, self._update_stats, out.visual) # pyright: ignore[reportArgumentType]
            self.after(0, lambda: self.status_label.configure(text="Completed")) # pyright: ignore[reportArgumentType]
        except Exception as exc:
            self.after(0, lambda: self._log(f"ERROR: {exc}")) # pyright: ignore[reportArgumentType]
            self.after(0, lambda: self.status_label.configure(text="Error")) # pyright: ignore[reportArgumentType]
        finally:
            self._post_ui(self._finish_run, session_id)

    def _post_ui(self, callback, *args, **kwargs):
        if getattr(self, "_is_closing", False):
            return
        if kwargs:
            self.after(0, lambda: callback(*args, **kwargs)) # pyright: ignore[reportArgumentType]
        else:
            self.after(0, callback, *args)

    def _open_capture(self, mode: str, source: CameraSource, session_id: int):
        self._pending_first_frame = None
        if mode == "Webcam":
            try:
                opened = self.engine.open_camera_source(source)
                self._pending_first_frame = opened.first_frame
                with self._capture_lock:
                    self._active_capture_session = session_id
                    self._active_capture = opened.cap
                self._post_ui(self._log, f"Camera open success: {opened.label}")
                self._post_ui(self._log, "Capture opened: True")
                self._post_ui(self._set_webcam_status, "Ready")
                return opened.cap, opened.first_frame
            except Exception:
                self._post_ui(self._log, "Capture opened: False")
                self._post_ui(self._set_webcam_status, "Not connected")
                raise
        media_path = self.engine.resolve_path(str(source))
        if mode == "Video" and not media_path.exists():
            raise RuntimeError(f"Video file not found: {media_path}")
        cap = cv2.VideoCapture(str(media_path))
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        ok, frame = cap.read()
        if ok and frame is not None and frame.size > 0:
            self._pending_first_frame = frame
            with self._capture_lock:
                self._active_capture_session = session_id
                self._active_capture = cap
            if mode == "Video":
                h, w = frame.shape[:2]
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                self._post_ui(self._log, f"Video open success: {media_path} | {w}x{h} | fps={fps:.1f} | frames={frames}")
        elif mode == "Video":
            cap.release()
            raise RuntimeError(f"Cannot read first frame from video: {media_path}")
        return cap, self._pending_first_frame

    def _release_active_capture(self, session_id: int):
        capture = None
        with self._capture_lock:
            if self._active_capture_session != session_id:
                return
            capture = self._active_capture
            self._active_capture = None
            self._active_capture_session = None
        if capture is not None:
            try:
                capture.release()
            except Exception as exc:
                self._post_ui(self._log, f"Capture release warning: {exc}")

    def _analyze_tagged_frame(
        self,
        session_id: int,
        frame_id: int,
        frame,
        settings: EngineSettings,
        mode: str,
        source: str,
        detected_batches: int,
        fps: float,
        source_time_seconds: float = 0.0,
        run_id: str = "",
    ) -> TaggedInferenceResult:
        visual = self.engine.analyze_frame(
            frame,
            settings,
            mode,
            source,
            frame_id,
            detected_batches,
            fps,
        )
        rendered = self.engine.draw_overlay(frame, visual, settings)
        return TaggedInferenceResult(
            session_id=session_id,
            frame_id=frame_id,
            visual=visual,
            rendered_frame=rendered,
            source_time_seconds=source_time_seconds,
            run_id=run_id,
        )

    def _run_stream_thread(
        self,
        mode: str,
        source: CameraSource,
        settings: EngineSettings,
        session_id: int,
        run_id: str,
    ):
        if mode == "Webcam":
            self.latest_visual = None
            self.latest_rendered = None
            try:
                # pyrefly: ignore [unknown-name]
                self._put_frame(np.zeros((720, 1280, 3), dtype=np.uint8)) # pyright: ignore[reportUndefinedVariable]
            except Exception:
                pass

        cap = None
        writer = None
        video_path = ""
        try:
            cap, pending_frame = self._open_capture(mode, source, session_id)
            if not cap or not cap.isOpened():
                raise RuntimeError(f"Cannot open {mode.lower()} source: {source}")
            self.engine.load_model(settings, input_mode=mode)
            active_device = self.engine.pick_device(settings.device)
            self.after(0, lambda dev=active_device: self._log(f"Detection device: {dev}")) # pyright: ignore[reportArgumentType]
            if self.engine.last_error:
                self.after(0, lambda msg=self.engine.last_error: self._log(msg)) # pyright: ignore[reportArgumentType]

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) if mode == "Video" else 0
            source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
            if source_fps <= 1 or source_fps > 120:
                source_fps = 25.0
            max_frames = total_frames if mode == "Video" and total_frames > 0 else 999999

            frame_idx = 0
            last_visual: Optional[VisualState] = None
            last_rendered = None
            last_clock = time.time()
            frame_interval = 1.0 / max(source_fps, 1.0) if mode == "Video" else 0.001
            last_history_save = 0.0
            last_video_time = -1.0

            def maybe_save_history(visual: Optional[VisualState]) -> None:
                nonlocal last_history_save
                if visual is None or not settings.save_history:
                    return
                now_hist = time.time()
                if now_hist - last_history_save < 2.0:
                    return
                try:
                    self.engine.append_history(visual.stats)
                    last_history_save = now_hist
                except Exception as exc:
                    self._post_ui(self._log, f"WARN: Cannot write history: {exc}")

            def consume_completed_inference(wait_timeout: float = 0.0):
                nonlocal last_visual, last_rendered
                future = self.detect_future
                if future is None or (not future.done() and wait_timeout <= 0.0):
                    return False
                try:
                    result = future.result(timeout=wait_timeout if not future.done() else None)
                except FutureTimeoutError:
                    return False
                except Exception as exc:
                    if self.detect_future is future:
                        self.detect_future = None
                    self._post_ui(self._log, f"Detection error: {exc}")
                    self._post_ui(self._set_billing_status, "Chờ dữ liệu hợp lệ")
                    return False
                if self.detect_future is future:
                    self.detect_future = None
                if (
                    not inference_result_is_current(result, session_id)
                    or self._active_session_id != session_id
                    or self.stop_event.is_set()
                ):
                    return False
                last_visual = result.visual
                last_rendered = result.rendered_frame
                self.latest_visual = last_visual
                self.latest_rendered = last_rendered
                self._post_ui(self._update_stats, last_visual)
                self._post_ui(self._update_billing, result, mode)
                maybe_save_history(last_visual)
                return True

            def discard_pending_inference(wait_timeout: float = 2.0) -> None:
                future = self.detect_future
                if future is None:
                    return
                future.cancel()
                try:
                    future.result(timeout=wait_timeout)
                except FutureTimeoutError:
                    self._post_ui(self._log, "Inference worker cleanup timed out; stale result will be ignored.")
                except Exception:
                    pass
                if future.done() and self.detect_future is future:
                    self.detect_future = None

            source_read_failed = False
            while not self.stop_event.is_set() and frame_idx < max_frames:
                loop_start = time.time()
                new_visual_this_frame = consume_completed_inference()
                if pending_frame is not None:
                    ok, frame = True, pending_frame
                    pending_frame = None
                else:
                    ok, frame = cap.read()
                if not ok or frame is None:
                    source_read_failed = mode == "Webcam"
                    break
                frame_idx += 1
                self._displayed_frames += 1

                if mode == "Video":
                    fallback_time = frame_idx / max(source_fps, 1.0)
                    position_time = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
                    position_is_plausible = (
                        math.isfinite(position_time)
                        and position_time > last_video_time + 1e-6
                        and abs(position_time - fallback_time) <= max(2.0, frame_interval * 10.0)
                    )
                    if position_is_plausible:
                        candidate_time = position_time
                    else:
                        candidate_time = fallback_time
                    source_time_seconds = max(last_video_time, candidate_time)
                    last_video_time = source_time_seconds
                else:
                    source_time_seconds = time.monotonic()
                if self._active_session_id == session_id:
                    self._billing_clock = source_time_seconds

                # Smooth preview FPS, separate from YOLO speed.
                now = time.time()
                dt = now - last_clock
                if dt >= 0.5:
                    self._last_fps = self._displayed_frames / max(now - self._last_preview_time, 1e-6)
                    last_clock = now

                detect_every = max(int(settings.detect_every_n_frames), 1)
                worker_busy = self.detect_future is not None
                if mode == "Webcam":
                    should_detect = not worker_busy
                else:
                    should_detect = should_submit_inference(frame_idx, detect_every, worker_busy)
                if should_detect:
                    self._detected_batches += 1
                    self.detect_future = self.executor.submit(
                        self._analyze_tagged_frame,
                        session_id,
                        frame_idx,
                        frame.copy(),
                        settings,
                        mode,
                        str(source),
                        self._detected_batches,
                        self._last_fps,
                        source_time_seconds,
                        run_id,
                    )

                if mode == "Webcam":
                    # Do not alternate between raw webcam frames and annotated
                    # boardlock frames. That flickers labels and looks like the
                    # slot boxes are jumping. Keep showing the newest processed
                    # ParkingVisionV8 frame until the worker produces another.
                    if new_visual_this_frame and last_visual is not None and last_visual.rendered_frame is not None:
                        rendered = last_visual.rendered_frame
                    elif last_rendered is not None:
                        rendered = last_rendered
                    else:
                        rendered = frame
                else:
                    # Preserve the existing smooth Video overlay behavior. Billing
                    # still consumes the tagged source frame/time, never this preview frame.
                    rendered = self.engine.draw_overlay(frame, last_visual, settings) if last_visual is not None else frame
                last_rendered = rendered
                self.latest_rendered = rendered

                if settings.save_video:
                    if writer is None:
                        writer, video_path = self.engine.make_video_writer(source, rendered, source_fps)
                    if writer is not None:
                        writer.write(rendered)

                self._put_frame(rendered)
                if mode == "Video" and total_frames > 0:
                    self._post_ui(self.progress.set, min(frame_idx / max(total_frames, 1), 1.0))
                    self._post_ui(self.status_label.configure, text=f"Video: frame {frame_idx}")
                else:
                    self._post_ui(self.status_label.configure, text=f"{mode}: live frame {frame_idx}")

                # For video files, keep playback natural instead of racing to the end.
                if mode == "Video":
                    elapsed = time.time() - loop_start
                    if elapsed < frame_interval:
                        time.sleep(frame_interval - elapsed)

            if self.stop_event.is_set():
                # STOP abandons active sessions and never consumes a late result.
                discard_pending_inference()
            else:
                # A real departure may be in the final submitted video frame. Use
                # a bounded wait at natural EOF, never an unbounded worker join.
                consume_completed_inference(wait_timeout=2.0)
                if self.detect_future is not None and not self.detect_future.done():
                    self._post_ui(self._log, "Final inference was not ready in time and was ignored.")

            if writer is not None:
                writer.release()
                writer = None
                self.latest_video_path = video_path

            if last_visual is not None and (settings.save_video or settings.save_history):
                csv_path = self.engine.save_stream_summary(
                    last_visual,
                    last_rendered,
                    video_path,
                    save_outputs=settings.save_video,
                    save_history=settings.save_history,
                )
                self.latest_csv_path = csv_path or ""
                self.latest_image_path = last_visual.stats.result_image

            if self.stop_event.is_set():
                final_status = "Stopped"
                final_log = "Stopped."
                billing_status = "Tạm dừng"
            elif mode == "Webcam" and source_read_failed:
                final_status = "Camera disconnected"
                final_log = "Camera source disconnected or stopped returning frames."
                billing_status = "Chờ dữ liệu hợp lệ"
            elif mode == "Video":
                final_status = "Video ended"
                final_log = "Video ended."
                billing_status = "Video đã kết thúc"
            else:
                final_status = "Completed"
                final_log = "Completed."
                billing_status = "Chờ xe"
            self._post_ui(self.status_label.configure, text=final_status)
            self._post_ui(self._set_billing_status, billing_status)
            self._post_ui(self._log, final_log)
        except Exception as exc:
            self._post_ui(self._log, f"ERROR: {exc}")
            self._post_ui(self.status_label.configure, text="Error")
            self._post_ui(self._set_billing_status, "Chờ dữ liệu hợp lệ")
        finally:
            self._release_active_capture(session_id)
            if writer is not None:
                writer.release()
            self._post_ui(self._finish_run, session_id)

    def _stop(self):
        if not self.running:
            return
        self.status_label.configure(text="Stopping safely...")
        self._log("Stopping stream safely...")
        self.stop_event.set()
        if self._active_session_id is not None:
            self._release_active_capture(self._active_session_id)
        self.billing_manager.reset_run()
        self._set_billing_status("Tạm dừng")
        self.stop_btn.configure(state="disabled")

    def _finish_run(self, session_id: Optional[int] = None):
        if session_id is not None and session_id != self._active_session_id:
            return
        self.running = False
        self.active_settings = None
        self._active_session_id = None
        if getattr(self, "_is_closing", False):
            return
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")
        self.progress.set(1 if self.input_mode.get() != "Webcam" else 0)

    # ---------------- Preview + stats ----------------
    def _put_frame(self, frame):
        try:
            while not self.frame_queue.empty():
                self.frame_queue.get_nowait()
        except Exception:
            pass
        try:
            self.frame_queue.put_nowait(frame)
        except Exception:
            pass

    def _pump_preview(self):
        if getattr(self, "_is_closing", False):
            return
        try:
            frame = self.frame_queue.get_nowait()
            self._display_frame(frame)
        except Empty:
            pass
        try:
            self.after(16, self._pump_preview) # pyright: ignore[reportArgumentType]
        except Exception:
            pass

    def _on_preview_resize(self, event=None):  # noqa: ARG002 - Tk callback
        if self._last_preview_frame is None or getattr(self, "_is_closing", False):
            return
        if self._preview_resize_job is not None:
            try:
                self.after_cancel(self._preview_resize_job)
            except Exception:
                pass
        self._preview_resize_job = self.after(80, lambda: self._display_frame(self._last_preview_frame)) # pyright: ignore[reportArgumentType]

    def _display_frame(self, frame):
        try:
            if frame is None:
                return
            self._last_preview_frame = frame
            self.preview_canvas.update_idletasks()
            view_w = int(self.preview_canvas.winfo_width() or 0)
            view_h = int(self.preview_canvas.winfo_height() or 0)
            if view_w <= 24 or view_h <= 24:
                self.preview_card.update_idletasks()
                view_w = int(self.preview_card.winfo_width() or 0) - 4
                view_h = int(self.preview_card.winfo_height() or 0) - 4
            if view_w <= 24 or view_h <= 24:
                view_w, view_h = 960, 420
            view_w = max(1, view_w - 4)
            view_h = max(1, view_h - 4)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            iw, ih = image.size
            new_w, new_h, offset_x, offset_y = fit_letterbox_size((iw, ih), (view_w, view_h))
            resized = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
            # Letterbox canvas: show the WHOLE frame. No crop, no stretching.
            canvas = Image.new("RGB", (view_w, view_h), "#081221")
            canvas.paste(resized, (offset_x, offset_y))
            self.preview_image_ref = ImageTk.PhotoImage(canvas)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(0, 0, image=self.preview_image_ref, anchor="nw")
        except Exception as exc:
            self._log(f"Preview error: {exc}")

    def _update_stats(self, visual: VisualState):
        stats = visual.stats
        self.stat_empty.configure(text=str(stats.available_spaces))
        self.stat_occ.configure(text=f"{stats.occupied_spaces}/{stats.total_spaces}")
        self.stat_vehicle.configure(text=f"{stats.parked_vehicles_detected}/{stats.vehicles_detected}")
        self.stat_rate.configure(text=f"{stats.occupancy_rate:.1f}%")
        self.stat_fps.configure(text=f"{stats.fps:.1f}")

    # ---------------- Utility ----------------
    def _open_outputs(self):
        out = self.app_dir / "desktop_outputs"
        out.mkdir(exist_ok=True)
        try:
            if platform.system() == "Windows":
                os.startfile(str(out))
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(out)])
            else:
                subprocess.Popen(["xdg-open", str(out)])
        except Exception as exc:
            self._log(f"Cannot open output folder: {exc}")

    def _log(self, message: str):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        try:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        except Exception:
            pass
        try:
            log_path = self.app_dir / "desktop_outputs" / "app.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def shutdown_from_terminal(self):
        """Close cleanly when Ctrl+C is pressed in VS Code/PowerShell."""
        self._request_window_close("exit")

    def _finish_window_close(self):
        stream = self.stream_thread
        pending = self.detect_future
        worker_active = bool(
            (stream is not None and stream.is_alive())
            or (pending is not None and not pending.done())
        )
        if worker_active and time.monotonic() < self._shutdown_deadline:
            try:
                self.after(50, self._finish_window_close) # pyright: ignore[reportArgumentType]
                return
            except Exception:
                pass
                
        try:
            self.stop_event.set()
        except Exception:
            pass
            
        try:
            if self._active_session_id is not None:
                self._release_active_capture(self._active_session_id)
            self.billing_manager.reset_run()
        except Exception:
            pass
            
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            try:
                self.executor.shutdown(wait=False)
            except Exception:
                pass
        except Exception:
            pass
            
        if pending is None or pending.done():
            try:
                self.engine.release()
            except Exception:
                pass
                
        if hasattr(self, "_after_ids"):
            for after_id in list(self._after_ids):
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
            self._after_ids.clear()
            
        if hasattr(self, "on_action") and self.on_action:
            self.on_action(self._window_action)

    def _on_close(self):
        self._request_window_close("exit")
