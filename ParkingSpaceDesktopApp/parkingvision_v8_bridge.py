from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union
import importlib.util
import signal
import sys
import threading
import time

import cv2
import numpy as np

PARKINGVISION_TEMPLATE_CANDIDATES = (
    "parkingvision_slots_template_9zones.json",
    "slots_template_9zones.json",
)
PARKINGVISION_BOARD_CANDIDATES = (
    "parkingvision_board_lock_9zones.json",
    "board_lock_9zones.json",
)
PARKINGVISION_BASELINE_NAME = "empty_baseline_9zones.jpg"


@dataclass
class CaptureHandle:
    cap: cv2.VideoCapture
    first_frame: Optional[np.ndarray] = None


class SlotStatePayload(TypedDict):
    slot_id: int
    state: str
    confidence: Optional[float]
    box: Optional[Tuple[int, int, int, int]]
    polygon: Optional[Tuple[Tuple[int, int], ...]]


def summarize_slot_measurement(total: int, counts: Counter, board_visible: bool) -> Dict[str, Any]:
    """Keep canonical totals while marking missing or incomplete observations invalid."""
    total = max(int(total), 0)
    empty = int(counts.get("empty", 0)) if board_visible else 0
    occupied = int(counts.get("occupied", 0)) if board_visible else 0
    valid = bool(board_visible and total > 0 and empty + occupied == total)
    reason = "ok" if valid else ("no_board" if not board_visible else "slot_count_mismatch")
    return {"empty": empty, "occupied": occupied, "total": total, "measurement_valid": valid, "reason": reason}


def _import_parkingvision_module(parkingvision_dir: Path) -> ModuleType:
    module_path = Path(parkingvision_dir) / "run_droidcam_v8s_boardlock.py"
    if not module_path.exists():
        raise FileNotFoundError(f"ParkingVisionV8 runner not found: {module_path}")

    module_key = f"_desktop_bridge_{module_path.stem}"
    if module_key in sys.modules:
        return sys.modules[module_key]

    spec = importlib.util.spec_from_file_location(module_key, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import ParkingVisionV8 runner: {module_path}")

    module = importlib.util.module_from_spec(spec)

    original_signal = signal.signal
    patched_signal = False
    if threading.current_thread() is not threading.main_thread():
        patched_signal = True

        def safe_signal(*args, **kwargs):  # noqa: ANN002, ANN003 - proxy for stdlib API
            return None

        signal.signal = safe_signal

    try:
        sys.modules[module_key] = module
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_key, None)
        raise
    finally:
        if patched_signal:
            signal.signal = original_signal
    return module


class ParkingVisionV8BoardlockEngine:
    """Frame-by-frame adapter for ParkingVisionV8 boardlock mode.

    This class reads the existing ParkingVisionV8 model/config/code and returns
    annotated frames to the desktop dashboard. It does not write to
    ParkingVisionV8 and it never opens an OpenCV preview window.
    """

    def __init__(self, model_path: Union[str, Path], parkingvision_dir: Union[str, Path], device: str = "auto"):
        self.parkingvision_dir = Path(parkingvision_dir).resolve()
        self.models_dir = self.parkingvision_dir / "models"
        self.model_path = Path(model_path).resolve()
        self.device_request = device or "auto"

        if not self.parkingvision_dir.exists():
            raise FileNotFoundError(f"ParkingVisionV8 folder not found: {self.parkingvision_dir}")
        if not self.model_path.exists():
            raise FileNotFoundError(f"ParkingVisionV8 model not found: {self.model_path}")

        self.pv8 = _import_parkingvision_module(self.parkingvision_dir)
        try:
            from ultralytics import YOLO
        except ModuleNotFoundError as exc:
            if exc.name == "ultralytics":
                raise RuntimeError(
                    "Ultralytics is not installed in the active Python environment."
                ) from exc
            raise RuntimeError(
                f"Ultralytics dependency import failed: {exc.name}"
            ) from exc
        
        if getattr(self.pv8, "_yolo_factory", None) is None:
            raise RuntimeError("ParkingVisionV8 script failed to export YOLO factory (_yolo_factory).")

        self.template_path = self._first_existing(PARKINGVISION_TEMPLATE_CANDIDATES, required=True)
        self.board_cache_path = self._first_existing(PARKINGVISION_BOARD_CANDIDATES, required=False)
        self.baseline_path = self.parkingvision_dir / PARKINGVISION_BASELINE_NAME
        self.args = self._build_args()
        self.slots_template = self.pv8.load_slots_template(self.template_path, create_if_missing=False)
        if len(self.slots_template) != 9:
            raise RuntimeError(f"ParkingVisionV8 9-zone template must contain 9 zones, found {len(self.slots_template)} at {self.template_path}")

        self.cached_board_quad = self.pv8.load_board_cache_quad(self.board_cache_path) if self.board_cache_path is not None else None
        self.baseline_warped = self.pv8.load_empty_baseline(self.baseline_path) if self.baseline_path.exists() else None
        self.parking_model = YOLO(str(self.model_path))

        vehicle_path = self.models_dir / "yolov8s.pt"
        self.vehicle_model = None
        if vehicle_path.exists():
            try:
                if vehicle_path.resolve() == self.model_path:
                    self.vehicle_model = self.parking_model
                else:
                    self.vehicle_model = YOLO(str(vehicle_path))
            except Exception:
                self.vehicle_model = None

        self.tracker = self.pv8.BoardTracker(self.args)
        self.stabilizer = self.pv8.SlotStabilizer([int(s["id"]) for s in self.slots_template], self.args)
        self._last_time = time.time()
        self._fps = 0.0
        self._frame_index = 0
        self._capture: Optional[CaptureHandle] = None

    def _first_existing(self, names: Tuple[str, ...], required: bool) -> Optional[Path]:
        for name in names:
            path = self.parkingvision_dir / name
            if path.exists():
                return path
        if required:
            raise FileNotFoundError(f"Required ParkingVisionV8 config not found. Tried: {', '.join(names)}")
        return None

    def _build_args(self) -> Any:
        parser = self.pv8.build_parser()
        args = parser.parse_args(["--source", "0"])
        
        args.model = str(self.model_path)
        args.template = str(self.template_path)
        if self.board_cache_path is not None:
            args.board_cache = str(self.board_cache_path)
        args.empty_baseline = str(self.baseline_path)
        args.device = self.pv8.choose_device(self.device_request)
        if args.device == "cuda":
            args.device = "0"

        # Turn off internal standalone cv2.imshow rendering flags
        args.show_board = False
        args.show_board_status = False
        args.show_conf = False
        args.show_source = False
        
        return args

    @staticmethod
    def _parse_source(source: Union[str, int]) -> Union[int, str]:
        if isinstance(source, int):
            return source
        text = str(source).strip().strip('"')
        if text.isdigit():
            return int(text)
        return text

    def open_source(self, source: Union[str, int]) -> CaptureHandle:
        parsed = self._parse_source(source)
        caps = []
        if isinstance(parsed, int):
            caps = [cv2.VideoCapture(parsed, cv2.CAP_DSHOW), cv2.VideoCapture(parsed, cv2.CAP_MSMF), cv2.VideoCapture(parsed)]
        else:
            caps = [cv2.VideoCapture(parsed, cv2.CAP_FFMPEG), cv2.VideoCapture(parsed)]

        last_cap = None
        for cap in caps:
            last_cap = cap
            if not cap.isOpened():
                cap.release()
                continue
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            except Exception:
                pass
            ok, frame = cap.read()
            if ok and frame is not None and frame.size > 0:
                self._capture = CaptureHandle(cap=cap, first_frame=frame)
                return self._capture
            cap.release()

        if last_cap is not None:
            last_cap.release()
        raise RuntimeError(f"Cannot open camera source {source!r}")

    def release(self) -> None:
        if self._capture is not None:
            try:
                self._capture.cap.release()
            except Exception:
                pass
            self._capture = None

    @staticmethod
    def _draw_slot_results(frame: np.ndarray, results: list[Any], show_boxes: bool, show_labels: bool) -> Counter:
        counts: Counter = Counter()
        for r in results:
            counts[r.label] += 1
            color = (0, 255, 0) if r.label == "empty" else (0, 165, 255)
            if show_boxes:
                poly = r.polygon.astype(np.int32)
                cv2.polylines(frame, [poly], True, color, 3 if r.label == "occupied" else 2, cv2.LINE_AA)
            if show_labels:
                tag = f"{r.label.upper()} {r.id}"
                x1, y1, x2, y2 = [int(v) for v in r.box.tolist()]
                tx = max(8, min(frame.shape[1] - 120, x1 + 8))
                ty = max(24, min(frame.shape[0] - 8, y1 + 28))
                cv2.putText(frame, tag, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.68, color, 2, cv2.LINE_AA)
        return counts

    def process_frame(
        self,
        frame: np.ndarray,
        show_boxes: bool = True,
        show_labels: bool = True,
        image_size: int = 960,
    ) -> Dict[str, Any]:
        now = time.time()
        dt = max(now - self._last_time, 1e-6)
        instant_fps = 1.0 / dt
        self._fps = instant_fps if self._fps <= 0 else (self._fps * 0.82 + instant_fps * 0.18)
        self._last_time = now
        self._frame_index += 1

        display = frame.copy()
        raw_board = self.pv8.detect_board_quad(frame, self.args)
        if raw_board is None and self.cached_board_quad is not None and self.args.use_board_cache:
            raw_board = self.pv8.validate_board_quad(frame, self.cached_board_quad, self.args, source="board-cache")
        elif raw_board is not None and self.cached_board_quad is not None and self.args.use_board_cache and self.args.strict_board_cache:
            delta = self.pv8.quad_delta_ratio(raw_board.quad, self.cached_board_quad)
            if delta > self.args.board_cache_max_delta:
                raw_board = self.pv8.validate_board_quad(frame, self.cached_board_quad, self.args, source="board-cache")

        locked_board = self.tracker.update(raw_board)
        results = []
        if locked_board is not None:
            model_dets = self.pv8.detect_with_parking_model(self.parking_model, frame, self.args)
            vehicle_dets = [] if self.args.no_vehicle else self.pv8.detect_vehicles(self.vehicle_model, frame, self.args)
            results = self.pv8.classify_template_slots(
                frame,
                locked_board,
                self.slots_template,
                model_dets,
                vehicle_dets,
                self.stabilizer,
                self.args,
                baseline_warped=self.baseline_warped,
            )
            vehicle_count = max(len(vehicle_dets), sum(1 for r in results if r.label == "occupied"))
        else:
            if self.tracker.missed > self.args.board_reset_after:
                self.stabilizer.reset()
            vehicle_count = 0

        if show_boxes or show_labels:
            self.pv8.draw_board_status(display, locked_board, self.args)
        if show_boxes:
            old_show_labels = bool(getattr(self.args, "show_labels", True))
            old_show_conf = bool(getattr(self.args, "show_conf", False))
            old_show_source = bool(getattr(self.args, "show_source", False))
            try:
                self.args.show_labels = bool(show_labels)
                self.args.show_conf = False
                self.args.show_source = False
                counts: Counter = self.pv8.draw_slot_results(display, results, self.args)
            finally:
                self.args.show_labels = old_show_labels
                self.args.show_conf = old_show_conf
                self.args.show_source = old_show_source
        else:
            counts = self._draw_slot_results(display, results, False, bool(show_labels))
        board_measurement_valid = bool(
            locked_board is not None and getattr(locked_board, "source", "") != "locked-hold"
        )
        measurement = summarize_slot_measurement(len(self.slots_template), counts, board_measurement_valid)
        if locked_board is not None and not board_measurement_valid:
            measurement["reason"] = "board_unstable"
        total = measurement["total"]
        empty = measurement["empty"]
        occupied = measurement["occupied"]
        slot_states: List[SlotStatePayload] = []
        if measurement["measurement_valid"] and board_measurement_valid:
            if len(results) != total:
                measurement["measurement_valid"] = False
                measurement["reason"] = "slot_count_mismatch"
            else:
                candidates: List[SlotStatePayload] = []
                for result in results:
                    confidence_value = getattr(result, "score", None)
                    # Support ParkingVision's region attributes if available
                    box_val = getattr(result, "box", None)
                    poly_val = getattr(result, "polygon", None)
                    
                    if box_val is not None:
                        box_val = tuple(int(x) for x in box_val[:4])
                    if poly_val is not None:
                        poly_val = tuple((int(pt[0]), int(pt[1])) for pt in poly_val)

                    candidates.append(
                        {
                            "slot_id": int(result.id),
                            "state": str(result.label),
                            "confidence": float(confidence_value) if confidence_value is not None else None,
                            # pyrefly: ignore [bad-assignment]
                            "box": box_val,
                            "polygon": poly_val,
                        }
                    )
                slot_ids = {item["slot_id"] for item in candidates}
                if slot_ids == set(range(1, total + 1)):
                    slot_states = candidates
                else:
                    measurement["measurement_valid"] = False
                    measurement["reason"] = "slot_count_mismatch"
        if show_labels:
            self.pv8.draw_hud(
                display,
                counts,
                float(self._fps),
                "boardlock",
                locked_board is not None,
                float(locked_board.confidence if locked_board is not None else 0.0),
                total_override=total,
            )

        return {
            "frame": display,
            "empty": empty,
            "occupied": occupied,
            "total": total,
            "rate": round(100.0 * occupied / max(total, 1), 1),
            "fps": round(float(self._fps), 1),
            "vehicles": int(vehicle_count),
            "board_visible": locked_board is not None,
            "measurement_valid": measurement["measurement_valid"],
            "reason": measurement["reason"],
            "slot_states": slot_states,
            "model": str(self.model_path),
            "device": str(self.args.device),
            "template": str(self.template_path),
            "board_cache": str(self.board_cache_path) if self.board_cache_path is not None else "",
            "baseline_loaded": self.baseline_warped is not None,
        }
