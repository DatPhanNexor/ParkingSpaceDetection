from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Protocol, Sequence, Tuple, TypedDict, Union, cast
from urllib.parse import urlparse
import csv
import json
import time
import uuid

import cv2
import numpy as np

class TorchCudaAPI(Protocol):
    def is_available(self) -> bool: ...
    def empty_cache(self) -> None: ...
    def get_device_name(self, device: int = 0) -> str: ...


class TorchModuleProtocol(Protocol):
    cuda: TorchCudaAPI


class TensorProtocol(Protocol):
    def cpu(self) -> TensorProtocol: ...
    def numpy(self) -> np.ndarray: ...
    def __iter__(self) -> Iterator[TensorProtocol]: ...


class YOLOBoxesProtocol(Protocol):
    xyxy: TensorProtocol
    conf: TensorProtocol
    cls: TensorProtocol


class YOLOMasksProtocol(Protocol):
    data: Iterable[TensorProtocol]


class YOLOResultProtocol(Protocol):
    boxes: Optional[YOLOBoxesProtocol]
    masks: Optional[YOLOMasksProtocol]


class YOLOModelProtocol(Protocol):
    def to(self, device: str) -> object: ...
    def predict(self, source: np.ndarray, **kwargs: object) -> Sequence[YOLOResultProtocol]: ...


class YOLOFactoryProtocol(Protocol):
    def __call__(self, model_path: str) -> YOLOModelProtocol: ...


class SlotStatePayload(TypedDict):
    slot_id: int
    state: str
    confidence: Optional[float]
    box: Optional[Tuple[int, int, int, int]]
    polygon: Optional[Tuple[Tuple[int, int], ...]]


class BoardlockPayload(TypedDict, total=False):
    frame: np.ndarray
    empty: int
    occupied: int
    total: int
    rate: float
    fps: float
    vehicles: int
    board_visible: bool
    measurement_valid: bool
    reason: str
    device: str
    slot_states: List[SlotStatePayload]


class BoardlockEngineProtocol(Protocol):
    def process_frame(
        self,
        frame: np.ndarray,
        *,
        show_boxes: bool,
        show_labels: bool,
        image_size: int,
    ) -> BoardlockPayload: ...
    def release(self) -> None: ...


class BoardlockFactoryProtocol(Protocol):
    def __call__(
        self, *, model_path: Path, parkingvision_dir: Path, device: str
    ) -> BoardlockEngineProtocol: ...


class ThresholdLoaderProtocol(Protocol):
    def __call__(self) -> Dict[str, Dict[str, float]]: ...


class FourCCFactoryProtocol(Protocol):
    def __call__(self, c1: str, c2: str, c3: str, c4: str) -> int: ...


_torch_module: Optional[TorchModuleProtocol] = None
_yolo_factory: Optional[YOLOFactoryProtocol] = None
_boardlock_factory: Optional[BoardlockFactoryProtocol] = None
YOLO_IMPORT_ERROR: Optional[Exception] = None
BOARDLOCK_IMPORT_ERROR: Optional[Exception] = None

try:
    _torch_module = cast(TorchModuleProtocol, import_module("torch"))
except Exception:
    pass

try:
    _ul_module = import_module("ultralytics")
    _yolo_factory = cast(YOLOFactoryProtocol, getattr(_ul_module, "YOLO"))
except Exception as exc:
    YOLO_IMPORT_ERROR = exc

try:
    _pv8_module = import_module("parkingvision_v8_bridge")
    _boardlock_factory = cast(
        BoardlockFactoryProtocol,
        getattr(_pv8_module, "ParkingVisionV8BoardlockEngine"),
    )
except Exception as exc:
    BOARDLOCK_IMPORT_ERROR = exc

VEHICLE_CLASS_IDS = [2, 3, 5, 7]  # COCO: car, motorcycle, bus, truck
VEHICLE_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

IMAGE_VIDEO_MODEL_NAME = "yolo11n-seg.pt"
PARKINGVISION_DEFAULT_MODEL_NAME = "parking_v8s_e15_best.pt"
PARKINGVISION_MODEL_NAMES = [
    "parking_v8s_e15_best.pt",
    "parking_v8s_best.pt",
    "yolov8s.pt",
]

COMMON_DROIDCAM_SOURCES = [
    "http://192.168.1.11:4747/video",
    "http://192.168.1.11:4747/mjpegfeed",
    "rtsp://192.168.1.11:4747/video",
    "rtsp://192.168.1.11:8554/live",
]

REGION_NAMES = [
    "upper_level_l",
    "upper_level_m",
    "upper_level_r",
    "close_perp",
    "far_side",
    "close_side",
    "far_perp",
    "small_park",
]

# Same values as src/parkingspace/regions.py. Keep a local fallback so this folder
# works without editing the original src directory.
ORIGINAL_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "upper_level_l": {"min_area": 2000, "max_aspect_ratio": 16, "min_solidity": 0.7, "min_width": 60, "max_width": 500, "min_height": 40, "max_height": 300},
    "upper_level_m": {"min_area": 2000, "max_aspect_ratio": 16, "min_solidity": 0.7, "min_width": 120, "max_width": 1050, "min_height": 50, "max_height": 300},
    "upper_level_r": {"min_area": 2000, "max_aspect_ratio": 16, "min_solidity": 0.7, "min_width": 170, "max_width": 500, "min_height": 100, "max_height": 150},
    "close_perp": {"min_area": 10, "max_aspect_ratio": 5, "min_solidity": 0.6, "min_width": 10, "max_width": 200, "min_height": 10, "max_height": 200},
    "far_side": {"min_area": 100, "max_aspect_ratio": 5, "min_solidity": 0.7, "min_width": 30, "max_width": 200, "min_height": 30, "max_height": 200},
    "close_side": {"min_area": 100, "max_aspect_ratio": 5, "min_solidity": 0.6, "min_width": 30, "max_width": 200, "min_height": 30, "max_height": 200},
    "far_perp": {"min_area": 100, "max_aspect_ratio": 5, "min_solidity": 0.7, "min_width": 30, "max_width": 200, "min_height": 30, "max_height": 200},
    "small_park": {"min_area": 200, "max_aspect_ratio": 2, "min_solidity": 0.9, "min_width": 30, "max_width": 200, "min_height": 30, "max_height": 200},
}

Box = Tuple[int, int, int, int]
VehicleBox = Tuple[int, int, int, int, float, str]
EmptySlot = Tuple[int, int, int, int, float]


@dataclass
class ProjectPaths:
    project_root: Path
    app_dir: Path
    parkingvision_dir: Path
    parkingvision_models_dir: Path


@dataclass
class CameraOpenResult:
    cap: cv2.VideoCapture
    first_frame: Optional[np.ndarray]
    source: Union[int, str]
    label: str


def resolve_project_paths(app_dir: Optional[Path] = None) -> ProjectPaths:
    app = Path(app_dir or Path(__file__).resolve().parent).resolve()
    root = app.parent
    pv8 = root / "ParkingVisionV8"
    return ProjectPaths(
        project_root=root,
        app_dir=app,
        parkingvision_dir=pv8,
        parkingvision_models_dir=pv8 / "models",
    )


def parse_camera_source(source: Union[str, int]) -> Union[int, str]:
    if isinstance(source, int):
        if source < 0:
            raise ValueError("Camera index must be a non-negative integer.")
        return source
    text = str(source or "").strip().strip('"')
    if not text:
        raise ValueError("Camera source is required (index or HTTP/HTTPS/RTSP URL).")
    if text.isdigit():
        return int(text)
    parsed = urlparse(text)
    if parsed.scheme.lower() in {"http", "https", "rtsp"} and parsed.netloc:
        return text
    raise ValueError("Camera source must be a non-negative index or an HTTP/HTTPS/RTSP URL.")


def _video_capture(source: Union[int, str], backend: Optional[int] = None) -> cv2.VideoCapture:
    if backend is None:
        return cv2.VideoCapture(source)
    if isinstance(source, str) and backend == cv2.CAP_FFMPEG:
        params = []
        for prop_name in ("CAP_PROP_OPEN_TIMEOUT_MSEC", "CAP_PROP_READ_TIMEOUT_MSEC"):
            prop = getattr(cv2, prop_name, None)
            if prop is not None:
                params.extend([prop, 1500])
        if params:
            try:
                return cv2.VideoCapture(source, backend, params)
            except Exception:
                pass
    return cv2.VideoCapture(source, backend)


def open_camera_source(source: Union[str, int], width: int = 1280, height: int = 720) -> CameraOpenResult:
    parsed = parse_camera_source(source)
    attempts: List[Tuple[str, Optional[int]]] = []
    if isinstance(parsed, int):
        attempts = [("ANY", None)]
    else:
        attempts = [("FFMPEG", cv2.CAP_FFMPEG), ("ANY", None)]

    errors: List[str] = []
    for name, backend in attempts:
        cap = _video_capture(parsed, backend)
        if not cap.isOpened():
            errors.append(f"{name}: not opened")
            cap.release()
            continue
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        except Exception:
            pass
        ok, frame = cap.read()
        if ok and frame is not None and frame.size > 0:
            return CameraOpenResult(cap=cap, first_frame=frame, source=parsed, label=f"{parsed} via {name}")
        errors.append(f"{name}: opened but read failed")
        cap.release()

    hint = "Try camera 0/1/2 or DroidCam URL such as http://192.168.1.11:4747/video"
    raise RuntimeError(f"Cannot open camera source {source!r}. Attempts: {'; '.join(errors) or 'none'}. {hint}")


def scan_camera_sources(max_index: int = 2, extra_sources: Optional[Iterable[str]] = None) -> List[str]:
    candidates: List[Union[int, str]] = list(range(max_index + 1))
    for src in extra_sources or COMMON_DROIDCAM_SOURCES:
        if src not in candidates:
            candidates.append(src)

    available: List[str] = []
    for src in candidates:
        try:
            opened = open_camera_source(src)
            available.append(str(src))
            opened.cap.release()
        except Exception:
            continue
    return available


def resolve_model_path(model_path: str | Path, paths: ProjectPaths) -> Path:
    path = Path(str(model_path or "").strip())
    if path.is_absolute():
        return path
    candidates = [
        paths.project_root / path,
        paths.app_dir / path,
        paths.parkingvision_models_dir / path.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return paths.project_root / path


@dataclass
class EngineSettings:
    model_path: str = IMAGE_VIDEO_MODEL_NAME
    device: str = "auto"  # auto, cpu, cuda
    quality_mode: str = "balanced"
    confidence: float = 0.25
    image_size: int = 960
    detect_every_n_frames: int = 6
    total_capacity: int = 20
    use_calibrated_map: bool = True
    save_video: bool = True
    save_history: bool = True
    show_boxes: bool = True
    show_labels: bool = True


@dataclass
class DetectionStats:
    timestamp: str
    input_mode: str
    input_source: str
    model: str
    device: str
    vehicles_detected: int
    parked_vehicles_detected: int
    occupied_spaces: int
    available_spaces: int
    total_spaces: int
    occupancy_rate: float
    fps: float
    processing_time: float
    detected_batches: int
    displayed_frames: int
    occupied: int
    empty: int
    total: int
    measurement_valid: bool
    reason: str
    source_mode: str
    result_image: str = ""
    result_video: str = ""
    output_path: str = ""
    csv_path: str = ""
    logic: str = ""


@dataclass(frozen=True)
class SlotState:
    slot_id: int
    state: str
    box: tuple[int, int, int, int] | None = None
    polygon: tuple[tuple[int, int], ...] | None = None
    confidence: float | None = None


@dataclass
class VisualState:
    empty_slots: List[EmptySlot]
    all_vehicle_boxes: List[VehicleBox]
    parked_vehicle_boxes: List[VehicleBox]
    vehicle_mask: Optional[np.ndarray]
    stats: DetectionStats
    note: str = ""
    rendered_frame: Optional[np.ndarray] = None
    slot_states: List[SlotState] = field(default_factory=list)
    tracking_measurement_valid: bool = False
    tracking_reason: str = "tracking_not_available"


@dataclass
class DetectionOutput:
    visual: VisualState
    rendered_frame: np.ndarray
    csv_path: str = ""
    image_path: str = ""


class DetectionEngine:
    def __init__(self, project_root: Path, app_dir: Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.app_dir = Path(app_dir).resolve()
        self.output_dir = self.app_dir / "desktop_outputs"
        self.images_dir = self.output_dir / "images"
        self.videos_dir = self.output_dir / "videos"
        self.csv_dir = self.output_dir / "csv"
        self.parkingvision_dir = self.project_root / "ParkingVisionV8"
        self.parkingvision_models_dir = self.parkingvision_dir / "models"
        self.paths = ProjectPaths(
            project_root=self.project_root,
            app_dir=self.app_dir,
            parkingvision_dir=self.parkingvision_dir,
            parkingvision_models_dir=self.parkingvision_models_dir,
        )
        for folder in (self.output_dir, self.images_dir, self.videos_dir, self.csv_dir):
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise RuntimeError(f"Cannot create output directory {folder}: {exc}") from exc

        self._model: Optional[YOLOModelProtocol] = None
        self._model_key: Optional[Tuple[str, str]] = None
        self._boardlock_engine: Optional[BoardlockEngineProtocol] = None
        self._boardlock_key: Optional[Tuple[str, str]] = None
        self._last_error = ""
        self._regions_loaded = False
        self._regions_original: Dict[str, np.ndarray] = {}
        self._ignore_original: List[np.ndarray] = []
        self._probability_map_original: Optional[np.ndarray] = None
        self._probability_map_original_shape: Optional[Tuple[int, int]] = None
        self._thresholds = ORIGINAL_THRESHOLDS

    @property
    def last_error(self) -> str:
        return self._last_error

    def runtime_path_report(self) -> List[str]:
        return [
            f"Resolved project root: {self.project_root}",
            f"Resolved ParkingVisionV8: {self.parkingvision_dir}",
            f"Resolved ParkingVisionV8 models: {self.parkingvision_models_dir}",
            f"ParkingVisionV8 bridge: {'loaded' if _boardlock_factory is not None else 'not loaded'}",
        ]

    def boardlock_total_hint(self) -> int:
        for name in ("parkingvision_slots_template_9zones.json", "slots_template_9zones.json"):
            path = self.parkingvision_dir / name
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                slots = data if isinstance(data, list) else data.get("slots", [])
                total = len(slots) if isinstance(slots, list) else 0
                if total > 0:
                    return total
            except Exception:
                continue
        return 9

    @staticmethod
    def _valid_json(path: Path) -> bool:
        if not path.exists():
            return False
        try:
            json.loads(path.read_text(encoding="utf-8"))
            return True
        except Exception:
            return False

    def calibrated_map_loaded(self) -> bool:
        return self._valid_json(self.project_root / "regions.json")

    def parking_map_loaded(self) -> bool:
        candidates = [
            self.project_root / "regions.json",
            self.app_dir / "regions.json",
            self.parkingvision_dir / "parkingvision_slots_template_9zones.json",
            self.parkingvision_dir / "slots_template_9zones.json",
        ]
        return any(self._valid_json(path) for path in candidates)

    def resolve_path(self, value: str | Path) -> Path:
        return resolve_model_path(value, self.paths)

    def default_model_for_mode(self, input_mode: str) -> str:
        mode = (input_mode or "Video").strip()
        if mode in {"Image", "Video"}:
            return IMAGE_VIDEO_MODEL_NAME
        return PARKINGVISION_DEFAULT_MODEL_NAME

    def list_models_for_mode(self, input_mode: str) -> List[str]:
        """Return only models that make sense for the selected workflow."""
        mode = (input_mode or "Video").strip()
        if mode in {"Image", "Video"}:
            # The report/demo contract is explicit: Image and Video use YOLO11 segmentation.
            return [IMAGE_VIDEO_MODEL_NAME]

        values: List[str] = []
        for name in PARKINGVISION_MODEL_NAMES:
            path = self.parkingvision_models_dir / name
            if path.exists() or name == PARKINGVISION_DEFAULT_MODEL_NAME:
                values.append(name)
        return values or [PARKINGVISION_DEFAULT_MODEL_NAME]

    def list_models(self) -> List[str]:
        # Backward-compatible default for callers that have not yet selected a mode.
        return self.list_models_for_mode("Video")

    def is_parkingvision_model(self, model_path: str | Path) -> bool:
        path = Path(model_path)
        if path.name in PARKINGVISION_MODEL_NAMES:
            return True
        resolved = self.resolve_path(model_path)
        try:
            return resolved.exists() and resolved.resolve().parent == self.parkingvision_models_dir.resolve()
        except Exception:
            return False

    def normalize_model_for_mode(self, input_mode: str, model_path: str | Path) -> Tuple[str, str]:
        """Return a safe model value plus an optional user-facing warning."""
        mode = (input_mode or "Video").strip()
        requested = str(model_path or "").strip()

        if mode in {"Image", "Video"}:
            if Path(requested).name != IMAGE_VIDEO_MODEL_NAME:
                return (
                    IMAGE_VIDEO_MODEL_NAME,
                    f"{mode} mode uses {IMAGE_VIDEO_MODEL_NAME}; switched from {requested or '<empty>'}.",
                )
            return IMAGE_VIDEO_MODEL_NAME, ""

        if not requested or not self.is_parkingvision_model(requested):
            return (
                PARKINGVISION_DEFAULT_MODEL_NAME,
                f"Webcam/DroidCam mode uses ParkingVisionV8/{PARKINGVISION_DEFAULT_MODEL_NAME}; switched from {requested or '<empty>'}.",
            )
        return Path(requested).name, ""

    def enforce_model_for_mode(self, settings: EngineSettings, input_mode: str) -> str:
        corrected, warning = self.normalize_model_for_mode(input_mode, settings.model_path)
        if corrected != settings.model_path:
            settings.model_path = corrected
            self._last_error = warning
        return warning

    def list_demo_videos(self) -> List[str]:
        demo = self.project_root / "Demo"
        if not demo.exists():
            return []
        videos = sorted(p for p in demo.iterdir() if p.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"})
        return [str(p.relative_to(self.project_root)) for p in videos]

    def pick_device(self, requested: str) -> str:
        requested = (requested or "auto").lower().strip()
        cuda_ok = False
        tm = _torch_module
        if tm is not None:
            try:
                cuda_ok = bool(tm.cuda.is_available())
            except Exception:
                cuda_ok = False
        if requested == "cuda":
            if not cuda_ok:
                self._last_error = "CUDA requested but not available; fallback to CPU."
            return "cuda" if cuda_ok else "cpu"
        if requested == "cpu":
            return "cpu"
        return "cuda" if cuda_ok else "cpu"

    def _get_boardlock_engine(self, settings: EngineSettings) -> BoardlockEngineProtocol:
        factory = _boardlock_factory
        if factory is None:
            raise RuntimeError(f"Cannot load ParkingVisionV8 bridge. Detail: {BOARDLOCK_IMPORT_ERROR}")
        model_path = self.resolve_path(settings.model_path)
        if not model_path.exists():
            raise RuntimeError(f"ParkingVisionV8 model not found: {model_path}")
        if not self.parkingvision_dir.exists():
            raise RuntimeError(f"ParkingVisionV8 folder not found: {self.parkingvision_dir}")
        device = self.pick_device(settings.device)
        key = (str(model_path.resolve()), device)
        current_engine = self._boardlock_engine
        if current_engine is not None and self._boardlock_key == key:
            return current_engine
        if current_engine is not None:
            try:
                current_engine.release()
            except Exception:
                pass
        local_engine = factory(
            model_path=model_path,
            parkingvision_dir=self.parkingvision_dir,
            device=device,
        )
        self._boardlock_engine = local_engine
        self._boardlock_key = key
        return local_engine

    def open_camera_source(self, source: str | int) -> CameraOpenResult:
        return open_camera_source(source)

    def load_model(self, settings: EngineSettings, input_mode: str = "") -> None:
        input_mode = input_mode or "Video"
        self.enforce_model_for_mode(settings, input_mode)
        if input_mode == "Webcam":
            self._get_boardlock_engine(settings)
            return
        factory = _yolo_factory
        if factory is None:
            raise RuntimeError(f"Missing ultralytics. Install with: pip install ultralytics. Detail: {YOLO_IMPORT_ERROR}")
        device = self.pick_device(settings.device)
        raw_model = settings.model_path or IMAGE_VIDEO_MODEL_NAME
        resolved = self.resolve_path(raw_model)
        if not resolved.exists():
            raise RuntimeError(
                f"{input_mode} model not found: {resolved}. "
                f"Image/Video mode requires {IMAGE_VIDEO_MODEL_NAME} in the project root."
            )
        model_path = str(resolved)
        key = (model_path, device)
        if self._model is not None and self._model_key == key:
            return
        local_model = factory(model_path)
        try:
            local_model.to(device)
        except Exception as exc:
            self._last_error = f"CUDA failed, fallback to CPU: {exc}"
            device = "cpu"
            local_model.to(device)
        # Warm up with small frame. It costs little and removes the ugly first-frame pause.
        try:
            dummy = np.zeros((320, 320, 3), dtype=np.uint8)
            local_model.predict(dummy, conf=0.25, imgsz=320, classes=VEHICLE_CLASS_IDS, device=device, verbose=False)
        except Exception:
            pass
        self._model = local_model
        self._model_key = (model_path, device)

    def _load_regions(self) -> None:
        if self._regions_loaded:
            return
        self._regions_loaded = True
        self._regions_original.clear()
        self._ignore_original.clear()

        prob_path = self.project_root / "Demo" / "probability_map.png"
        prob = cv2.imread(str(prob_path), cv2.IMREAD_GRAYSCALE) if prob_path.exists() else None
        if prob is not None:
            self._probability_map_original = prob
            self._probability_map_original_shape = prob.shape[:2]

        regions_path = self.project_root / "regions.json"
        if not regions_path.exists():
            self._last_error = "regions.json not found. Calibrated mode cannot be used."
            return
        try:
            # Prefer original project loader if present. Local fallback keeps the app isolated.
            try:
                regions_module = import_module("parkingspace.regions")
                get_thresholds = cast(
                    ThresholdLoaderProtocol,
                    getattr(regions_module, "get_thresholds"),
                )
                self._thresholds = get_thresholds()
            except Exception:
                self._thresholds = ORIGINAL_THRESHOLDS

            data = json.loads(regions_path.read_text(encoding="utf-8"))
            for name in REGION_NAMES:
                if name in data:
                    self._regions_original[name] = np.asarray(data[name], dtype=np.float32)
            self._ignore_original = [np.asarray(x, dtype=np.float32) for x in data.get("ignore_regions", [])]
        except Exception as exc:
            self._last_error = f"Cannot load regions.json: {exc}"

    def _scaled_regions(self, frame_shape: Tuple[int, int]) -> Tuple[Dict[str, np.ndarray], List[np.ndarray], float, float]:
        self._load_regions()
        h, w = frame_shape[:2]
        base_h, base_w = self._probability_map_original_shape or (h, w)
        sx = w / max(float(base_w), 1.0)
        sy = h / max(float(base_h), 1.0)
        regions: Dict[str, np.ndarray] = {}
        for name, poly in self._regions_original.items():
            scaled = poly.copy()
            scaled[:, 0] *= sx
            scaled[:, 1] *= sy
            regions[name] = scaled.astype(np.int32)
        ignores: List[np.ndarray] = []
        for poly in self._ignore_original:
            scaled = poly.copy()
            scaled[:, 0] *= sx
            scaled[:, 1] *= sy
            ignores.append(scaled.astype(np.int32))
        return regions, ignores, sx, sy

    def _scaled_thresholds(self, name: str, sx: float, sy: float) -> Dict[str, float]:
        raw = self._thresholds.get(name, ORIGINAL_THRESHOLDS[name])
        area_scale = max(sx * sy, 0.0001)
        return {
            "min_area": raw["min_area"] * area_scale,
            "max_aspect_ratio": raw["max_aspect_ratio"],
            "min_solidity": raw["min_solidity"],
            "min_width": raw["min_width"] * sx,
            "max_width": raw["max_width"] * sx,
            "min_height": raw["min_height"] * sy,
            "max_height": raw["max_height"] * sy,
        }

    @staticmethod
    def _point_inside(polygons: Iterable[np.ndarray], point: Tuple[float, float]) -> bool:
        return any(cv2.pointPolygonTest(poly, point, False) >= 0 for poly in polygons)

    def _box_in_parking_regions(self, box: VehicleBox, frame_shape: Tuple[int, int]) -> bool:
        regions, _, _, _ = self._scaled_regions(frame_shape)
        if not regions:
            return True
        x1, y1, x2, y2, _, _ = box
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        if self._point_inside(regions.values(), (cx, cy)):
            return True
        # Also accept if meaningful overlap with any region. Center-only fails for diagonal cars.
        bw, bh = max(1, x2 - x1), max(1, y2 - y1)
        box_mask = np.zeros(frame_shape[:2], dtype=np.uint8)
        cv2.rectangle(box_mask, (x1, y1), (x2, y2), 255, -1)
        for poly in regions.values():
            region_mask = np.zeros(frame_shape[:2], dtype=np.uint8)
            cv2.fillPoly(region_mask, [poly], 255)
            inter = cv2.countNonZero(cv2.bitwise_and(box_mask, region_mask))
            if inter / float(bw * bh) > 0.18:
                return True
        return False

    @staticmethod
    def _contour_center(contour: np.ndarray) -> Optional[Tuple[int, int]]:
        m = cv2.moments(contour)
        if m["m00"] == 0:
            return None
        return int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"])

    @staticmethod
    def _verify_nearby_vehicle(contour: np.ndarray, vehicle_mask_scaled: np.ndarray, aspect_ratio: float, search_radius: int = 50, aspect_ratio_tolerance: float = 0.4) -> List[Box]:
        x, y, w, h = cv2.boundingRect(contour)
        search_x1 = max(x - search_radius, 0)
        search_y1 = max(y - search_radius, 0)
        search_x2 = min(x + w + search_radius, vehicle_mask_scaled.shape[1])
        search_y2 = min(y + h + search_radius, vehicle_mask_scaled.shape[0])
        roi = vehicle_mask_scaled[search_y1:search_y2, search_x1:search_x2]
        nearby_contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        matching: List[Box] = []
        for nearby in nearby_contours:
            nx, ny, nw, nh = cv2.boundingRect(nearby)
            if nw <= 0 or nh <= 0:
                continue
            nearby_aspect = nh / float(nw)
            if abs(nearby_aspect - aspect_ratio) <= aspect_ratio_tolerance:
                matching.append((search_x1 + nx, search_y1 + ny, nw, nh))
        return matching

    @staticmethod
    def _space_score(area: float, width: int, height: int, aspect_ratio: float, solidity: float, vehicle_bboxes: List[Box], thresholds: Dict[str, float]) -> float:
        score = 0.0
        ideal_area = (thresholds["min_area"] + (thresholds["max_width"] * thresholds["max_height"])) / 2.0
        score += 30.0 * min(area / max(ideal_area, 1.0), 1.0)
        max_asp = thresholds["max_aspect_ratio"]
        score += 20.0 * min(max_asp / max(aspect_ratio, 0.001), 1.0)
        min_sol = thresholds["min_solidity"]
        if solidity > min_sol:
            score += 20.0 * min((solidity - min_sol) / max(1.0 - min_sol, 0.001), 1.0)
        if vehicle_bboxes:
            score += 30.0
        return score

    def _detect_vehicles(self, frame: np.ndarray, settings: EngineSettings, input_mode: str = "Video") -> Tuple[np.ndarray, List[VehicleBox], float, str]:
        self.load_model(settings, input_mode=input_mode)
        model = self._model
        if model is None:
            raise RuntimeError("YOLO model did not initialize.")
        device = self.pick_device(settings.device)
        start = time.time()
        imgsz = int(settings.image_size)
        try:
            result = model.predict(
                frame,
                conf=float(settings.confidence),
                iou=0.45,
                imgsz=imgsz,
                classes=VEHICLE_CLASS_IDS,
                device=device,
                verbose=False,
            )
        except Exception as exc:
            detail = str(exc).lower()
            if imgsz > 960 and ("cuda" in detail or "memory" in detail or "out of memory" in detail):
                settings.quality_mode = "balanced"
                settings.image_size = 960
                settings.detect_every_n_frames = max(int(settings.detect_every_n_frames), 6)
                self._last_error = f"Accurate mode failed at {imgsz}px; fallback to Balanced 960px. Detail: {exc}"
                result = model.predict(
                    frame,
                    conf=float(settings.confidence),
                    iou=0.45,
                    imgsz=960,
                    classes=VEHICLE_CLASS_IDS,
                    device=device,
                    verbose=False,
                )
            else:
                raise
        elapsed = time.time() - start
        if not result:
            raise RuntimeError("YOLO returned no result object.")
        r = result[0]
        h, w = frame.shape[:2]
        mask_total = np.zeros((h, w), dtype=np.uint8)
        boxes: List[VehicleBox] = []

        xyxy: List[List[int]] = []
        confs: List[float] = []
        clss: List[int] = []
        result_boxes = r.boxes
        if result_boxes is not None:
            try:
                xyxy_array = result_boxes.xyxy.cpu().numpy().astype(np.int64)
                conf_array = result_boxes.conf.cpu().numpy().reshape(-1)
                cls_array = result_boxes.cls.cpu().numpy().astype(np.int64).reshape(-1)
                xyxy = [[int(value) for value in row] for row in xyxy_array] # pyright: ignore[reportGeneralTypeIssues]
                confs = [float(value) for value in conf_array]
                clss = [int(value) for value in cls_array]
            except Exception:
                xyxy, confs, clss = [], [], []

        # Segmentation masks are the key part of the original project. We also fill
        # boxes into the mask to avoid false EMPTY labels when a small segmentation mask misses a parked car.
        result_masks = r.masks
        if result_masks is not None:
            for m in result_masks.data:
                try:
                    binary = m.cpu().numpy().astype(np.uint8)
                    if binary.shape != (h, w):
                        binary = cv2.resize(binary, (w, h), interpolation=cv2.INTER_NEAREST)
                    mask_total = cv2.bitwise_or(mask_total, binary)
                except Exception:
                    continue

        for i, box in enumerate(xyxy):
            if i >= len(clss):
                continue
            class_id = int(clss[i])
            if class_id not in VEHICLE_CLASS_IDS:
                continue
            x1, y1, x2, y2 = box[:4]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w - 1, x2), min(h - 1, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            conf = float(confs[i]) if i < len(confs) else 0.0
            label = VEHICLE_NAMES.get(class_id, "vehicle")
            boxes.append((x1, y1, x2, y2, conf, label))
            cv2.rectangle(mask_total, (x1, y1), (x2, y2), 1, -1)

        # Fill holes and expand slightly. This is what prevents cars sitting on a slot
        # from being misread as EMPTY because of a thin mask gap.
        if np.any(mask_total):
            k = max(5, int(round(min(h, w) * 0.007)))
            if k % 2 == 0:
                k += 1
            kernel = np.ones((k, k), np.uint8)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_CLOSE, kernel, iterations=1)
            mask_total = cv2.dilate(mask_total, kernel, iterations=1)
        return mask_total.astype(np.uint8), boxes, elapsed, device

    @staticmethod
    def _vehicle_iou(a: VehicleBox, b: VehicleBox) -> float:
        ax1, ay1, ax2, ay2 = a[:4]
        bx1, by1, bx2, by2 = b[:4]
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(1, (bx2 - bx1) * (by2 - by1))
        return inter / float(area_a + area_b - inter + 1e-6)

    def _nms_vehicle_boxes(self, boxes: List[VehicleBox], iou_threshold: float = 0.42) -> List[VehicleBox]:
        if not boxes:
            return []
        boxes_sorted = sorted(boxes, key=lambda b: float(b[4]), reverse=True)
        kept: List[VehicleBox] = []
        for box in boxes_sorted:
            x1, y1, x2, y2, conf, label = box
            area = max(1, (x2 - x1) * (y2 - y1))
            if area < 80:
                continue
            duplicate = False
            for kept_box in kept:
                if self._vehicle_iou(box, kept_box) >= iou_threshold:
                    duplicate = True
                    break
                # When a tiled pass produces an inner box, suppress it too.
                kx1, ky1, kx2, ky2 = kept_box[:4]
                ix1, iy1 = max(x1, kx1), max(y1, ky1)
                ix2, iy2 = min(x2, kx2), min(y2, ky2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                if inter / float(area + 1e-6) > 0.72:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(box)
        kept.sort(key=lambda b: (b[1], b[0]))
        return kept

    @staticmethod
    def _slot_vehicle_overlap(slot: EmptySlot, vehicle: VehicleBox) -> Tuple[float, float]:
        sx, sy, sw, sh, _ = slot
        vx1, vy1, vx2, vy2 = vehicle[:4]
        sx2, sy2 = sx + sw, sy + sh
        ix1, iy1 = max(sx, vx1), max(sy, vy1)
        ix2, iy2 = min(sx2, vx2), min(sy2, vy2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        slot_area = max(1, sw * sh)
        veh_area = max(1, (vx2 - vx1) * (vy2 - vy1))
        return inter / float(slot_area), inter / float(veh_area)

    def _filter_empty_slots_by_vehicles(self, slots: List[EmptySlot], vehicle_boxes: List[VehicleBox], vehicle_mask: np.ndarray) -> List[EmptySlot]:
        """Image-only cleanup: if a detected vehicle overlaps a candidate slot, that slot is not EMPTY.

        This avoids the common still-image failure where the calibrated probability map
        proposes an empty rectangle but YOLO detected a car sitting on top of it.
        """
        if not slots:
            return []
        filtered: List[EmptySlot] = []
        for slot in slots:
            sx, sy, sw, sh, score = slot
            slot_area = max(1, sw * sh)
            roi = vehicle_mask[max(0, sy):max(0, sy + sh), max(0, sx):max(0, sx + sw)]
            mask_overlap = float(np.count_nonzero(roi)) / float(slot_area) if roi.size else 0.0
            occupied = mask_overlap > 0.10
            if not occupied:
                for vb in vehicle_boxes:
                    slot_ratio, veh_ratio = self._slot_vehicle_overlap(slot, vb)
                    vx1, vy1, vx2, vy2 = vb[:4]
                    vcx, vcy = (vx1 + vx2) / 2.0, (vy1 + vy2) / 2.0
                    center_inside = sx <= vcx <= sx + sw and sy <= vcy <= sy + sh
                    if slot_ratio > 0.16 or (slot_ratio > 0.08 and center_inside) or veh_ratio > 0.28:
                        occupied = True
                        break
            if not occupied:
                filtered.append(slot)
        filtered.sort(key=lambda b: (b[1] // 80, b[0]))
        return filtered

    def _detect_vehicles_image_enhanced(self, frame: np.ndarray, settings: EngineSettings) -> Tuple[np.ndarray, List[VehicleBox], float, str]:
        """Still-image detector.

        Video mode is intentionally untouched. For a still image we can spend extra time:
        full-frame detection + overlapping tiled detection + NMS. This improves small/far
        car detection without making video playback lag.
        """
        h, w = frame.shape[:2]
        strong = EngineSettings(
            model_path=settings.model_path,
            device=settings.device,
            quality_mode=settings.quality_mode,
            confidence=min(float(settings.confidence), 0.14),
            image_size=int(settings.image_size),
            detect_every_n_frames=settings.detect_every_n_frames,
            total_capacity=settings.total_capacity,
            use_calibrated_map=settings.use_calibrated_map,
            save_video=settings.save_video,
            save_history=settings.save_history,
            show_boxes=settings.show_boxes,
            show_labels=settings.show_labels,
        )
        t0 = time.time()
        base_mask, base_boxes, _, device = self._detect_vehicles(frame, strong, input_mode="Image")
        all_boxes: List[VehicleBox] = list(base_boxes)
        combined_mask = base_mask.copy()

        # Overlapping crops. They help YOLO see small cars in still images.
        crops: List[Tuple[int, int, int, int]] = []
        if w >= 900 and h >= 450:
            x_mid_l, x_mid_r = int(w * 0.42), int(w * 0.58)
            y_mid_t, y_mid_b = int(h * 0.40), int(h * 0.62)
            crops.extend([
                (0, 0, x_mid_r, y_mid_b),
                (x_mid_l, 0, w, y_mid_b),
                (0, y_mid_t, x_mid_r, h),
                (x_mid_l, y_mid_t, w, h),
                (0, 0, w, int(h * 0.55)),
                (0, int(h * 0.35), w, h),
            ])
        # Remove invalid/duplicate crop boxes.
        unique_crops: List[Tuple[int, int, int, int]] = []
        seen = set()
        for x1, y1, x2, y2 in crops:
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 - x1 < 280 or y2 - y1 < 220:
                continue
            key = (x1, y1, x2, y2)
            if key not in seen:
                seen.add(key)
                unique_crops.append(key)

        for x1, y1, x2, y2 in unique_crops:
            crop = frame[y1:y2, x1:x2]
            try:
                cmask, cboxes, _, _ = self._detect_vehicles(crop, strong, input_mode="Image")
            except Exception:
                continue
            if cmask is not None and cmask.size:
                combined_mask[y1:y2, x1:x2] = np.maximum(combined_mask[y1:y2, x1:x2], cmask)
            for bx1, by1, bx2, by2, conf, label in cboxes:
                # Drop boxes cut too hard by crop edges unless they are large enough.
                all_boxes.append((bx1 + x1, by1 + y1, bx2 + x1, by2 + y1, conf, label))

        merged = self._nms_vehicle_boxes(all_boxes, iou_threshold=0.42)
        # Rebuild mask using merged boxes too. Occupancy logic needs a strong mask.
        for x1, y1, x2, y2, _, _ in merged:
            cv2.rectangle(combined_mask, (max(0, x1), max(0, y1)), (min(w - 1, x2), min(h - 1, y2)), 1, -1)
        if np.any(combined_mask):
            k = max(5, int(round(min(h, w) * 0.009)))
            if k % 2 == 0:
                k += 1
            kernel = np.ones((k, k), np.uint8)
            combined_mask = cv2.morphologyEx(combined_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=1)
            combined_mask = cv2.dilate(combined_mask, kernel, iterations=1)
        return combined_mask.astype(np.uint8), merged, time.time() - t0, device


    def _find_empty_slots_original_logic(self, frame: np.ndarray, vehicle_mask: np.ndarray) -> List[EmptySlot]:
        self._load_regions()
        if self._probability_map_original is None or not self._regions_original:
            return []
        h, w = frame.shape[:2]
        regions, ignores, sx, sy = self._scaled_regions(frame.shape)
        prob = cv2.resize(self._probability_map_original, (w, h), interpolation=cv2.INTER_NEAREST)
        vehicle_scaled = (vehicle_mask * 255).astype(np.uint8)
        inv = cv2.bitwise_not(vehicle_scaled)
        combined = cv2.bitwise_and(prob, prob, mask=inv)
        _, binary = cv2.threshold(combined, 50, 255, cv2.THRESH_BINARY)
        kernel_size = max(3, int(round(5 * max(sx, sy))))
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        eroded = cv2.erode(binary, kernel, iterations=6)
        contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        slots: List[EmptySlot] = []
        avg_width_space = max(60, int(round(200 * sx)))
        search_radius = max(20, int(round(50 * max(sx, sy))))
        for contour in contours:
            center = self._contour_center(contour)
            if center is None:
                continue
            if self._point_inside(ignores, center):
                continue
            region_name = None
            for name in REGION_NAMES:
                poly = regions.get(name)
                if poly is not None and cv2.pointPolygonTest(poly, center, False) >= 0:
                    region_name = name
                    break
            if region_name is None:
                continue
            thresholds = self._scaled_thresholds(region_name, sx, sy)
            area = cv2.contourArea(contour)
            if area < thresholds["min_area"]:
                continue
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull) if hull is not None else 1.0
            solidity = area / hull_area if hull_area > 0 else 0.0
            if solidity < thresholds["min_solidity"]:
                continue
            x, y, bw, bh = cv2.boundingRect(contour)
            if not (thresholds["min_width"] <= bw <= thresholds["max_width"] and thresholds["min_height"] <= bh <= thresholds["max_height"]):
                continue
            aspect = max(bw, bh) / float(max(1, min(bw, bh)))
            if aspect > thresholds["max_aspect_ratio"]:
                continue
            nearby = self._verify_nearby_vehicle(contour, vehicle_scaled, aspect, search_radius=search_radius, aspect_ratio_tolerance=0.4)
            score = self._space_score(area, bw, bh, aspect, solidity, nearby, thresholds)
            # Keep the original behavior: accepted contours count as empty spaces. Split long contours.
            if bw > avg_width_space:
                num_spaces = max(1, int(bw / float(avg_width_space)))
                space_w = bw / float(num_spaces)
                for j in range(num_spaces):
                    sx0 = int(x + j * space_w)
                    slots.append((sx0, y, int(space_w), bh, float(score)))
            else:
                slots.append((x, y, bw, bh, float(score)))
        # Stable left-to-right/top-to-bottom ordering keeps labels from dancing.
        slots.sort(key=lambda b: (b[1] // 80, b[0]))
        return slots

    def analyze_frame(self, frame: np.ndarray, settings: EngineSettings, input_mode: str, input_source: str, displayed_frames: int = 1, detected_batches: int = 1, fps: float = 0.0) -> VisualState:
        start = time.time()
        self.enforce_model_for_mode(settings, input_mode)
        if input_mode == "Webcam":
            boardlock = self._get_boardlock_engine(settings)
            try:
                payload = boardlock.process_frame(
                    frame,
                    show_boxes=bool(settings.show_boxes),
                    show_labels=bool(settings.show_labels),
                    image_size=int(settings.image_size),
                )
            except Exception as exc:
                self._last_error = f"ParkingVisionV8 inference failed: {exc}"
                payload = {
                    "frame": frame.copy(),
                    "empty": 0,
                    "occupied": 0,
                    "total": self.boardlock_total_hint(),
                    "rate": 0.0,
                    "fps": float(fps),
                    "vehicles": 0,
                    "board_visible": False,
                    "measurement_valid": False,
                    "reason": f"inference_error:{type(exc).__name__}",
                    "slot_states": [],
                }
            elapsed = time.time() - start
            # pyrefly: ignore [bad-argument-type]
            occupied = int(payload.get("occupied", 0))
            # pyrefly: ignore [bad-argument-type]
            total = int(payload.get("total", 0))
            # pyrefly: ignore [bad-argument-type]
            empty = int(payload.get("empty", max(total - occupied, 0)))
            measurement_valid = bool(payload.get("measurement_valid", False))
            reason = str(payload.get("reason", "ok" if measurement_valid else "invalid_measurement"))
            raw_slot_states = payload.get("slot_states", [])
            try:
                # pyrefly: ignore [bad-index, not-iterable]
                slot_ids = {int(item["slot_id"]) for item in raw_slot_states}
            except (KeyError, TypeError, ValueError):
                slot_ids = set()
            if measurement_valid and (
                len(raw_slot_states) != total or slot_ids != set(range(1, total + 1))
            ):
                measurement_valid = False
                reason = "slot_count_mismatch"
            slot_states = (
                [
                    SlotState(
                        slot_id=int(item["slot_id"]),
                        state=str(item["state"]),
                        # pyrefly: ignore [bad-argument-type, bad-index]
                        confidence=float(item["confidence"]) if item.get("confidence") is not None else None,
                        box=item.get("box"),
                        # pyrefly: ignore [missing-attribute]
                        polygon=item.get("polygon"),
                    )
                    for item in raw_slot_states
                ]
                if measurement_valid and len(raw_slot_states) == total
                else []
            )
            vehicle_count = int(payload.get("vehicles", occupied))
            stats = DetectionStats(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                input_mode=input_mode,
                input_source=input_source,
                model=settings.model_path,
                device=str(payload.get("device", self.pick_device(settings.device))),
                vehicles_detected=vehicle_count,
                parked_vehicles_detected=occupied,
                occupied_spaces=occupied,
                available_spaces=empty,
                total_spaces=total,
                occupancy_rate=float(payload.get("rate", round(100.0 * occupied / max(total, 1), 1))),
                fps=float(payload.get("fps", round(float(fps), 1))),
                processing_time=round(elapsed, 3),
                detected_batches=detected_batches,
                displayed_frames=displayed_frames,
                occupied=occupied,
                empty=empty,
                total=total,
                measurement_valid=measurement_valid,
                reason=reason,
                source_mode=input_mode,
                logic="ParkingVisionV8 boardlock",
            )
            return VisualState(
                empty_slots=[],
                all_vehicle_boxes=[],
                parked_vehicle_boxes=[],
                vehicle_mask=None,
                stats=stats,
                note="ParkingVisionV8 boardlock" if payload.get("board_visible") else "ParkingVisionV8 board not visible",
                rendered_frame=cast(Optional[np.ndarray], payload.get("frame")),
                slot_states=slot_states,
                tracking_measurement_valid=measurement_valid,
                tracking_reason=reason,
            )

        mask, boxes, detect_time, device = self._detect_vehicles(frame, settings, input_mode=input_mode)
        parked_boxes = [b for b in boxes if self._box_in_parking_regions(b, frame.shape)] if settings.use_calibrated_map else boxes[:]
        empty_slots = self._find_empty_slots_original_logic(frame, mask) if settings.use_calibrated_map else []

        tracking_valid = bool(settings.use_calibrated_map and self._regions_original)
        
        slot_states = []
        if tracking_valid:
            combined = []
            for b in parked_boxes:
                combined.append({"type": "occupied", "box": b[:4], "conf": b[4]})
            for s in empty_slots:
                x, y, w, h, score = s
                combined.append({"type": "empty", "box": (x, y, x + w, y + h), "conf": score})
            
            combined.sort(key=lambda item: (item["box"][1] // 80, item["box"][0]))
            
            for i, item in enumerate(combined, start=1):
                slot_states.append(SlotState(
                    slot_id=i,
                    state="OCCUPIED" if item["type"] == "occupied" else "EMPTY",
                    confidence=float(item["conf"]),
                    box=tuple(int(v) for v in item["box"]),
                    polygon=None
                ))
            
            available = sum(1 for s in slot_states if s.state == "EMPTY")
            occupied = sum(1 for s in slot_states if s.state == "OCCUPIED")
            total_spaces = available + occupied
        else:
            available = len(empty_slots) if settings.use_calibrated_map and empty_slots else max(settings.total_capacity - len(parked_boxes), 0)
            total_from_scene = available + len(parked_boxes)
            total_spaces = max(settings.total_capacity, total_from_scene, 1)
            occupied = max(total_spaces - available, len(parked_boxes))
            if occupied > total_spaces:
                total_spaces = occupied
                available = 0

        rate = 100.0 * occupied / max(total_spaces, 1)
        elapsed = time.time() - start
        stats = DetectionStats(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            input_mode=input_mode,
            input_source=input_source,
            model=settings.model_path,
            device=device,
            vehicles_detected=len(boxes),
            parked_vehicles_detected=len(parked_boxes),
            occupied_spaces=int(occupied),
            available_spaces=int(available),
            total_spaces=int(total_spaces),
            occupancy_rate=round(rate, 1),
            fps=round(float(fps), 1),
            processing_time=round(elapsed, 3),
            detected_batches=detected_batches,
            displayed_frames=displayed_frames,
            occupied=int(occupied),
            empty=int(available),
            total=int(total_spaces),
            measurement_valid=tracking_valid,
            reason="calibrated_map_canonical" if tracking_valid else "capacity_estimate",
            source_mode=input_mode,
            logic="calibrated_map+canonical_slot_states" if tracking_valid else "fallback_capacity_minus_vehicle_count",
        )

        return VisualState(
            empty_slots=empty_slots,
            all_vehicle_boxes=boxes,
            parked_vehicle_boxes=parked_boxes,
            vehicle_mask=mask,
            stats=stats,
            tracking_measurement_valid=tracking_valid,
            tracking_reason="ok" if tracking_valid else "parking_regions_unavailable",
            slot_states=slot_states,
        )

    def draw_overlay(self, frame: np.ndarray, visual: Optional[VisualState], settings: Optional[EngineSettings] = None) -> np.ndarray:
        if visual is None:
            return frame.copy()
        if visual.rendered_frame is not None:
            return visual.rendered_frame.copy()
        show_boxes = True if settings is None else bool(settings.show_boxes)
        show_labels = True if settings is None else bool(settings.show_labels)
        out = frame.copy()
        h, w = out.shape[:2]
        # Soft vehicle tint only for parked vehicles. It helps users see OCCUPIED without drowning the image.
        if show_boxes and visual.vehicle_mask is not None and visual.vehicle_mask.shape[:2] == (h, w):
            tint = np.zeros_like(out)
            tint[:, :] = (30, 90, 200)  # BGR amber-ish tint
            mask255 = (visual.vehicle_mask > 0).astype(np.uint8) * 255
            colored = cv2.bitwise_and(tint, tint, mask=mask255)
            out = cv2.addWeighted(out, 0.82, colored, 0.18, 0)

        # Draw canonical slot states
        if hasattr(visual, "slot_states") and visual.slot_states:
            for slot in visual.slot_states:
                if slot.box:
                    x1, y1, x2, y2 = slot.box
                    is_occupied = slot.state == "OCCUPIED"
                    
                    if show_boxes:
                        color = (0, 170, 255) if is_occupied else (70, 255, 40)
                        thickness = 2 if is_occupied else 3
                        cv2.rectangle(out, (x1, y1), (x2, y2), color, thickness)
                        
                    if show_labels:
                        text = f"{slot.state} {slot.slot_id}"
                        color = (0, 215, 255) if is_occupied else (70, 255, 40)
                        ty = max(20, y1 - 8)
                        cv2.putText(out, text, (x1, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.78 if not is_occupied else 0.68, color, 2, cv2.LINE_AA)
        else:
            # Fallback if slot_states not present (e.g., when not using map)
            for i, (x, y, bw, bh, score) in enumerate(visual.empty_slots, start=1):
                if show_boxes:
                    cv2.rectangle(out, (x, y), (x + bw, y + bh), (70, 255, 40), 3)
                if show_labels:
                    label = f"EMPTY {i}"
                    ty = max(22, y - 8)
                    cv2.putText(out, label, (x, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (70, 255, 40), 2, cv2.LINE_AA)
            for i, (x1, y1, x2, y2, conf, label) in enumerate(visual.parked_vehicle_boxes, start=1):
                if show_boxes:
                    cv2.rectangle(out, (x1, y1), (x2, y2), (0, 170, 255), 2)
                if show_labels:
                    text = f"OCCUPIED {i}"
                    cv2.putText(out, text, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (0, 215, 255), 2, cv2.LINE_AA)

        if show_labels:
            top = f"EMPTY: {visual.stats.available_spaces}   OCCUPIED: {visual.stats.occupied_spaces}/{visual.stats.total_spaces}   FPS: {visual.stats.fps:.1f}"
            cv2.rectangle(out, (0, 0), (min(w, 760), 42), (4, 12, 24), -1)
            cv2.putText(out, top, (12, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (235, 245, 255), 2, cv2.LINE_AA)
        return out


    def analyze_image_frame(self, frame: np.ndarray, settings: EngineSettings, input_source: str) -> VisualState:
        """High-accuracy still-image analysis.

        This is separate from analyze_frame() so video behavior remains unchanged.
        """
        start = time.time()
        self.enforce_model_for_mode(settings, "Image")
        mask, boxes, detect_time, device = self._detect_vehicles_image_enhanced(frame, settings)
        parked_boxes = [b for b in boxes if self._box_in_parking_regions(b, frame.shape)] if settings.use_calibrated_map else boxes[:]
        empty_slots = self._find_empty_slots_original_logic(frame, mask) if settings.use_calibrated_map else []
        if settings.use_calibrated_map:
            empty_slots = self._filter_empty_slots_by_vehicles(empty_slots, parked_boxes, mask)

        tracking_valid = bool(settings.use_calibrated_map and self._regions_original)
        
        slot_states = []
        if tracking_valid:
            combined = []
            for b in parked_boxes:
                combined.append({"type": "occupied", "box": b[:4], "conf": b[4]})
            for s in empty_slots:
                x, y, w, h, score = s
                combined.append({"type": "empty", "box": (x, y, x + w, y + h), "conf": score})
            
            combined.sort(key=lambda item: (item["box"][1] // 80, item["box"][0]))
            
            for i, item in enumerate(combined, start=1):
                slot_states.append(SlotState(
                    slot_id=i,
                    state="OCCUPIED" if item["type"] == "occupied" else "EMPTY",
                    confidence=float(item["conf"]),
                    box=tuple(int(v) for v in item["box"]),
                    polygon=None
                ))
            
            available = sum(1 for s in slot_states if s.state == "EMPTY")
            occupied = sum(1 for s in slot_states if s.state == "OCCUPIED")
            total_spaces = available + occupied
        else:
            available = len(empty_slots) if settings.use_calibrated_map and empty_slots else max(settings.total_capacity - len(parked_boxes), 0)
            total_from_scene = available + len(parked_boxes)
            total_spaces = max(settings.total_capacity, total_from_scene, 1)
            occupied = max(total_spaces - available, len(parked_boxes))
            if occupied > total_spaces:
                total_spaces = occupied
                available = 0

        rate = 100.0 * occupied / max(total_spaces, 1)
        elapsed = time.time() - start
        stats = DetectionStats(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            input_mode="Image",
            input_source=input_source,
            model=settings.model_path,
            device=device,
            vehicles_detected=len(boxes),
            parked_vehicles_detected=len(parked_boxes),
            occupied_spaces=int(occupied),
            available_spaces=int(available),
            total_spaces=int(total_spaces),
            occupancy_rate=round(rate, 1),
            fps=0.0,
            processing_time=round(elapsed, 3),
            detected_batches=1,
            displayed_frames=1,
            occupied=int(occupied),
            empty=int(available),
            total=int(total_spaces),
            measurement_valid=tracking_valid,
            reason="calibrated_map_canonical" if tracking_valid else "capacity_estimate",
            source_mode="Image",
            logic="image_tiled_yolo+calibrated_map+canonical_slot_states" if tracking_valid else "image_tiled_yolo+fallback_capacity",
        )

        return VisualState(
            empty_slots=empty_slots,
            all_vehicle_boxes=boxes,
            parked_vehicle_boxes=parked_boxes,
            vehicle_mask=mask,
            stats=stats,
            tracking_measurement_valid=tracking_valid,
            tracking_reason="ok" if tracking_valid else "parking_regions_unavailable",
            slot_states=slot_states,
        )

    def run_image(self, image_path: str, settings: EngineSettings) -> DetectionOutput:
        self.enforce_model_for_mode(settings, "Image")
        src_path = self.resolve_path(image_path)
        frame = cv2.imread(str(src_path))
        if frame is None:
            raise RuntimeError(f"Cannot read image: {src_path}")
        t0 = time.time()
        visual = self.analyze_image_frame(frame, settings, str(src_path))
        rendered = self.draw_overlay(frame, visual, settings)
        ts = self._output_token()
        visual.stats.processing_time = round(time.time() - t0, 3)
        image_path_out = ""
        csv_path_out = ""
        if settings.save_video:
            image_out = self.images_dir / f"image_result_{ts}.jpg"
            if not cv2.imwrite(str(image_out), rendered):
                raise RuntimeError(f"Cannot write result image: {image_out}")
            image_path_out = str(image_out)
            visual.stats.result_image = image_path_out
            visual.stats.output_path = image_path_out
            csv_path = self.save_summary_csv(visual.stats, f"result_{ts}.csv")
            csv_path_out = str(csv_path)
            visual.stats.csv_path = csv_path_out
        if settings.save_history:
            self.append_history(visual.stats)
        return DetectionOutput(visual=visual, rendered_frame=rendered, csv_path=csv_path_out, image_path=image_path_out)

    @staticmethod
    def _video_writer_fourcc(codec: str) -> int:
        if len(codec) != 4:
            raise ValueError("Video codec must contain exactly four characters.")
        factory = cast(FourCCFactoryProtocol, getattr(cv2, "VideoWriter_fourcc"))
        return factory(codec[0], codec[1], codec[2], codec[3])

    def make_video_writer(
        self,
        _source: Union[int, str],
        first_frame: np.ndarray,
        fps: float = 25.0,
    ) -> Tuple[cv2.VideoWriter, str]:
        ts = self._output_token()
        path = self.videos_dir / f"video_result_{ts}.mp4"
        h, w = first_frame.shape[:2]
        fourcc = self._video_writer_fourcc("mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, max(float(fps), 1.0), (w, h))
        if not writer.isOpened():
            path = self.videos_dir / f"video_result_{ts}.avi"
            writer = cv2.VideoWriter(
                str(path),
                self._video_writer_fourcc("XVID"),
                max(float(fps), 1.0),
                (w, h),
            )
        if not writer.isOpened():
            raise RuntimeError(f"Cannot create video output writer in {self.videos_dir}")
        return writer, str(path)

    def save_stream_summary(
        self,
        visual: Optional[VisualState],
        last_rendered: Optional[np.ndarray],
        result_video: str = "",
        save_outputs: bool = True,
        save_history: bool = True,
    ) -> Optional[str]:
        if visual is None:
            return None
        ts = self._output_token()
        if save_outputs and last_rendered is not None:
            image_path = self.images_dir / f"last_frame_{ts}.jpg"
            if not cv2.imwrite(str(image_path), last_rendered):
                raise RuntimeError(f"Cannot write result image: {image_path}")
            visual.stats.result_image = str(image_path)
        if result_video:
            visual.stats.result_video = result_video
        visual.stats.output_path = result_video or visual.stats.result_image
        csv_path = None
        if save_outputs:
            csv_path = self.save_summary_csv(visual.stats, f"result_{ts}.csv")
            visual.stats.csv_path = str(csv_path)
        if save_history:
            self.append_history(visual.stats)
        return str(csv_path) if csv_path is not None else None

    def save_summary_csv(self, stats: DetectionStats, filename: str) -> Path:
        path = self.csv_dir / filename
        fieldnames = list(stats.__dataclass_fields__.keys())
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(self._safe_csv_row(stats.__dict__))
        return path

    def append_history(self, stats: DetectionStats) -> None:
        path = self.csv_dir / "detection_history.csv"
        fieldnames = list(stats.__dataclass_fields__.keys())
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            elif path.stat().st_size > 0:
                try:
                    with path.open("r", encoding="utf-8-sig", newline="") as rf:
                        first = rf.readline().strip()
                    if first and first.split(",") != fieldnames:
                        f.write("\n")
                        writer.writeheader()
                except Exception:
                    pass
            writer.writerow(self._safe_csv_row(stats.__dict__))

    @staticmethod
    def _output_token() -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        return f"{stamp}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _safe_csv_row(row: Dict[str, object]) -> Dict[str, object]:
        return {
            key: f"'{value}" if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value
            for key, value in row.items()
        }

    def release(self) -> None:
        if self._boardlock_engine is not None:
            try:
                self._boardlock_engine.release()
            except Exception:
                pass
            self._boardlock_engine = None
            self._boardlock_key = None

    def scan_cameras(self, max_index: int = 2) -> List[str]:
        return scan_camera_sources(max_index=max_index, extra_sources=COMMON_DROIDCAM_SOURCES)
