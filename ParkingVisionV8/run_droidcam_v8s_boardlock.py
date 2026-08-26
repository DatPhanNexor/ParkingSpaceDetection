# -*- coding: utf-8 -*-
"""
Parking Vision V8S STRICT Occupancy FIX

Fix trá»ng tÃ¢m so vá»›i V11:
- KhÃ´ng tá»± dá»±ng Ã´ báº±ng YOLO/line-pair lung tung ná»¯a.
- Tá»± tÃ¬m cá»¥m báº£ng bÃ£i Ä‘á»— báº±ng váº¡ch vÃ ng/Ä‘á»/tráº¯ng, khÃ³a 4 gÃ³c, warp vá» máº·t pháº³ng chuáº©n.
- Chá»‰ dÃ¹ng 9 vÃ¹ng Ä‘á»— xe template cá»‘ Ä‘á»‹nh trong máº·t pháº³ng warp.
- Khi camera khÃ´ng nhÃ¬n tháº¥y báº£ng: áº©n toÃ n bá»™ Ã´, khÃ´ng dÃ¹ng cache cÅ© Ä‘á»ƒ váº½ bá»«a.
- Giáº£m nháº£y Empty/Occupied báº±ng EMA + hysteresis + xÃ¡c nháº­n nhiá»u frame.
- V13 strict: Ã´ chá»‰ Occupied khi cÃ³ blob váº­t thá»ƒ tháº­t trong vÃ¹ng trong cá»§a Ã´; khÃ´ng dÃ¹ng YOLO Ä‘á»ƒ tá»± quyáº¿t náº¿u thiáº¿u báº±ng chá»©ng hÃ¬nh áº£nh.

File nÃ y cá»‘ tÃ¬nh hÆ¡i dÃ i, vÃ¬ mÃ¡y tÃ­nh cÅ©ng pháº£i gÃ¡nh háº­u quáº£ cá»§a viá»‡c con ngÆ°á»i
muá»‘n mÃ´ hÃ¬nh Ä‘á»“ chÆ¡i hoáº¡t Ä‘á»™ng nhÆ° bÃ£i xe sÃ¢n bay.
"""

from __future__ import annotations

import argparse
import json
import math
import signal
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, TypedDict, cast, Mapping, Sequence, Union, Iterable

import argparse
import cv2
import importlib
import numpy as np

class TorchCudaAPI(Protocol):
    def is_available(self) -> bool: ...
    def empty_cache(self) -> None: ...
    def get_device_name(self, index: int = 0) -> str: ...

class TorchModule(Protocol):
    cuda: TorchCudaAPI

class TensorLikeProtocol(Protocol):
    def cpu(self) -> "TensorLikeProtocol": ...
    def numpy(self) -> np.ndarray: ...
    def tolist(self) -> list[Any]: ...
    def item(self) -> float: ...
    def __iter__(self) -> Any: ...

class BoxesProtocol(Protocol):
    xyxy: TensorLikeProtocol
    conf: TensorLikeProtocol
    cls: TensorLikeProtocol
    def __iter__(self) -> Any: ...

class YOLOResultProtocol(Protocol):
    boxes: Optional[BoxesProtocol]

class YOLOModelProtocol(Protocol):
    names: Mapping[int, str] | Sequence[str]
    def to(self, device: str) -> "YOLOModelProtocol": ...
    def predict(self, source: Any, **kwargs: Any) -> list[YOLOResultProtocol]: ...

YOLOFactory = Callable[[str], YOLOModelProtocol]

class RegionItem(TypedDict, total=False):
    id: int
    name: str
    region: Any

class RegionCollection(TypedDict):
    rois: list[RegionItem]
    slots: list[RegionItem]

_torch_module: Optional[TorchModule] = None
try:
    _torch_module = cast(TorchModule, importlib.import_module("torch"))
except ImportError:
    pass

_yolo_factory: Optional[YOLOFactory] = None
try:
    _ul_module = importlib.import_module("ultralytics")
    y_class: Any = getattr(_ul_module, "YOLO")
    if callable(y_class):
        _yolo_factory = cast(YOLOFactory, y_class)
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
TRAINED_MODEL = ROOT / "models" / "parking_v8s_e15_best.pt"
LEGACY_MODEL = ROOT / "models" / "parking_v8s_best.pt"
DEFAULT_MODEL = TRAINED_MODEL
FALLBACK_MODEL = ROOT / "models" / "yolov8s.pt"
DEFAULT_TEMPLATE = ROOT / "parkingvision_slots_template_9zones.json"
DEFAULT_BOARD_CACHE = ROOT / "parkingvision_board_lock_9zones.json"
LEGACY_BOARD_CACHE_CANDIDATES = [
    ROOT / "board_lock_9zones.json",
]
LEGACY_TEMPLATE_CANDIDATES = [
    ROOT / "slots_template_9zones.json",
]
DEFAULT_EMPTY_BASELINE = ROOT / "empty_baseline_9zones.jpg"
DEFAULT_REGIONS = ROOT / "regions.json"
COCO_VEHICLE_CLASSES = {2, 3, 5, 7}  # car, motorcycle, bus, truck
STOP_REQUESTED = False

# Canonical board plane. Slot template uses normalized coordinates, then scales to this.
CANON_W = 1000
CANON_H = 650

# Production thresholds for the 9-zone boardlock pipeline.
BOARD_CONF_THRES = 0.40
BOARD_VISIBLE_CONFIRM_FRAMES = 3
BOARD_LOST_CONFIRM_FRAMES = 2
YOLO_CONF_THRES = 0.30
YOLO_OVERLAP_THRES = 0.18
VISUAL_AREA_THRES = 0.070
VISUAL_CONTOUR_THRES = 0.055
VISUAL_EDGE_THRES = 0.0
VISUAL_MAX_UNIFORM_COLOR_RATIO = 0.40
VISUAL_UNIFORM_MAX_STD = 70.0
BASELINE_DIFF_THRES = 34
BASELINE_DIFF_RATIO_THRES = 0.085
BASELINE_CONTOUR_RATIO_THRES = 0.035
BASELINE_COLOR_DIFF_THRES = 18.0
BASELINE_UNIFORM_DIFF_MAX = 0.62
BASELINE_UNIFORM_CONTOUR_MAX = 0.55
BASELINE_UNIFORM_EDGE_MAX = 0.08
OCCUPIED_CONFIRM_FRAMES = 3
EMPTY_CONFIRM_FRAMES = 4

# Some zones sit close to printed arrows, yellow separators, and watermark/text areas.
# These overrides tighten only the evidence requirements; they do not force any zone to EMPTY.
ZONE_OCCUPANCY_OVERRIDES = {
    1: {
        # Slot 1 is near printed arrows, but previous thresholds were too strict
        # and could reject a real car. Accept only strong, centered YOLO evidence.
        "inner_crop_x": 0.20,
        "inner_crop_y": 0.16,
        "visual_car_blob_min": 0.075,
        "visual_car_color_min": 0.095,
        "baseline_diff_min_ratio": 0.135,
        "baseline_contour_min_ratio": 0.070,
        "baseline_color_diff_min": 22.0,
        "baseline_fill_min": 0.22,
        "baseline_thickness_min": 0.28,
        "baseline_min_dim": 0.16,
        "baseline_edge_min": 0.030,
        "yolo_baseline_min": 0.46,
        "yolo_visual_min": 0.32,
        "yolo_slot_iou": 0.08,
        "yolo_cover_slot": 0.16,
        "yolo_cover_obj": 0.34,
        "yolo_center_min_cover": 0.14,
        "yolo_min_slot_area": 0.08,
        "direct_yolo_no_visual": 1.0,
        "direct_yolo_conf": 0.48,
        "direct_yolo_cover_slot": 0.15,
        "direct_yolo_cover_obj": 0.32,
        "direct_yolo_iou": 0.08,
        "direct_yolo_min_slot_area": 0.08,
        "direct_yolo_score": 0.78,
        "require_yolo_for_occ": 1.0,
        "no_yolo_score_cap": 0.18,
        "match_expand_x": 0.08,
        "match_expand_y": 0.04,
        "occ_on": 0.55,
        "empty_off": 0.30,
        "occ_confirm_frames": 2,
        "empty_confirm_frames": 2,
        "uncertain_counter_decay": 0,
    },
    2: {
        "inner_crop_x": 0.21,
        "inner_crop_y": 0.17,
        "visual_car_blob_min": 0.080,
        "visual_car_color_min": 0.100,
        "baseline_diff_min_ratio": 0.150,
        "baseline_contour_min_ratio": 0.080,
        "baseline_color_diff_min": 24.0,
        "baseline_fill_min": 0.24,
        "baseline_thickness_min": 0.30,
        "baseline_min_dim": 0.17,
        "baseline_edge_min": 0.035,
        "yolo_baseline_min": 0.54,
        "yolo_visual_min": 0.40,
        "yolo_slot_iou": 0.11,
        "yolo_cover_slot": 0.22,
        "yolo_cover_obj": 0.40,
        "yolo_center_min_cover": 0.18,
        "yolo_min_slot_area": 0.11,
        "direct_yolo_no_visual": 1.0,
        "direct_yolo_conf": 0.47,
        "direct_yolo_cover_slot": 0.20,
        "direct_yolo_cover_obj": 0.36,
        "direct_yolo_iou": 0.09,
        "direct_yolo_min_slot_area": 0.10,
        "direct_yolo_score": 0.76,
        "require_yolo_for_occ": 1.0,
        "no_yolo_score_cap": 0.18,
        "match_expand_x": 0.06,
        "match_expand_y": 0.04,
        "occ_on": 0.58,
        "empty_off": 0.30,
        "occ_confirm_frames": 2,
        "empty_confirm_frames": 2,
    },
    3: {
        "inner_crop_x": 0.22,
        "inner_crop_y": 0.18,
        "visual_car_blob_min": 0.080,
        "visual_car_color_min": 0.100,
        "baseline_diff_min_ratio": 0.150,
        "baseline_contour_min_ratio": 0.080,
        "baseline_color_diff_min": 24.0,
        "baseline_fill_min": 0.24,
        "baseline_thickness_min": 0.30,
        "baseline_min_dim": 0.17,
        "baseline_edge_min": 0.035,
        "yolo_baseline_min": 0.56,
        "yolo_visual_min": 0.42,
        "yolo_slot_iou": 0.12,
        "yolo_cover_slot": 0.24,
        "yolo_cover_obj": 0.42,
        "yolo_center_min_cover": 0.18,
        "yolo_min_slot_area": 0.12,
        "direct_yolo_no_visual": 1.0,
        "direct_yolo_conf": 0.46,
        "direct_yolo_cover_slot": 0.19,
        "direct_yolo_cover_obj": 0.38,
        "direct_yolo_iou": 0.10,
        "direct_yolo_min_slot_area": 0.10,
        "direct_yolo_score": 0.76,
        "require_yolo_for_occ": 1.0,
        "no_yolo_score_cap": 0.18,
        "match_expand_x": 0.06,
        "match_expand_y": 0.04,
        "occ_on": 0.58,
        "empty_off": 0.30,
        "occ_confirm_frames": 2,
        "empty_confirm_frames": 2,
    },
    4: {
        "inner_crop_x": 0.21,
        "inner_crop_y": 0.17,
        "visual_car_blob_min": 0.080,
        "visual_car_color_min": 0.100,
        "baseline_diff_min_ratio": 0.150,
        "baseline_contour_min_ratio": 0.080,
        "baseline_color_diff_min": 24.0,
        "baseline_fill_min": 0.24,
        "baseline_thickness_min": 0.30,
        "baseline_min_dim": 0.17,
        "baseline_edge_min": 0.035,
        "yolo_baseline_min": 0.54,
        "yolo_visual_min": 0.40,
        "yolo_slot_iou": 0.11,
        "yolo_cover_slot": 0.22,
        "yolo_cover_obj": 0.40,
        "yolo_center_min_cover": 0.18,
        "yolo_min_slot_area": 0.11,
        "direct_yolo_no_visual": 1.0,
        "direct_yolo_conf": 0.47,
        "direct_yolo_cover_slot": 0.20,
        "direct_yolo_cover_obj": 0.36,
        "direct_yolo_iou": 0.09,
        "direct_yolo_min_slot_area": 0.10,
        "direct_yolo_score": 0.76,
        "require_yolo_for_occ": 1.0,
        "no_yolo_score_cap": 0.18,
        "match_expand_x": 0.07,
        "match_expand_y": 0.04,
        "occ_on": 0.58,
        "empty_off": 0.30,
        "occ_confirm_frames": 2,
        "empty_confirm_frames": 2,
    },
    6: {
        "inner_crop_x": 0.26,
        "inner_crop_y": 0.18,
        "visual_car_blob_min": 0.080,
        "visual_car_color_min": 0.105,
        "baseline_diff_min_ratio": 0.160,
        "baseline_contour_min_ratio": 0.085,
        "baseline_color_diff_min": 24.0,
        "baseline_fill_min": 0.24,
        "baseline_thickness_min": 0.30,
        "baseline_min_dim": 0.18,
        "baseline_edge_min": 0.035,
        "yolo_baseline_min": 0.58,
        "yolo_min_slot_area": 0.14,
    },
    7: {
        "inner_crop_x": 0.26,
        "inner_crop_y": 0.18,
        "visual_car_blob_min": 0.080,
        "visual_car_color_min": 0.105,
        "baseline_diff_min_ratio": 0.160,
        "baseline_contour_min_ratio": 0.085,
        "baseline_color_diff_min": 24.0,
        "baseline_fill_min": 0.24,
        "baseline_thickness_min": 0.30,
        "baseline_min_dim": 0.18,
        "baseline_edge_min": 0.035,
        "yolo_baseline_min": 0.58,
        "yolo_min_slot_area": 0.14,
    },
    8: {
        # Right-side horizontal zones are short in height, so strict overlap
        # can miss a real toy car when the box is slightly low/partial.
        "inner_crop_x": 0.14,
        "inner_crop_y": 0.12,
        "visual_car_blob_min": 0.075,
        "visual_car_color_min": 0.095,
        "baseline_diff_min_ratio": 0.125,
        "baseline_contour_min_ratio": 0.060,
        "baseline_color_diff_min": 20.0,
        "baseline_fill_min": 0.20,
        "baseline_thickness_min": 0.26,
        "baseline_min_dim": 0.15,
        "baseline_edge_min": 0.025,
        "yolo_baseline_min": 0.44,
        "yolo_visual_min": 0.30,
        "yolo_slot_iou": 0.035,
        "yolo_cover_slot": 0.085,
        "yolo_cover_obj": 0.20,
        "yolo_center_min_cover": 0.08,
        "yolo_min_slot_area": 0.035,
        "direct_yolo_no_visual": 1.0,
        "direct_yolo_conf": 0.36,
        "direct_yolo_cover_slot": 0.075,
        "direct_yolo_cover_obj": 0.18,
        "direct_yolo_iou": 0.03,
        "direct_yolo_min_slot_area": 0.035,
        "direct_yolo_score": 0.80,
        "require_yolo_for_occ": 1.0,
        "allow_strong_visual_without_yolo": 1.0,
        "strong_visual_no_yolo_min_score": 0.60,
        "strong_baseline_no_yolo_min_score": 0.54,
        "no_yolo_score_cap": 0.18,
        "match_expand_x": 0.10,
        "match_expand_y": 0.28,
        "occ_on": 0.52,
        "empty_off": 0.30,
        "occ_confirm_frames": 2,
        "empty_confirm_frames": 2,
        "uncertain_counter_decay": 0,
    },
    9: {
        # Same geometry issue as zone 8: accept partial but centered car boxes,
        # while still requiring either YOLO or a strong baseline/visual blob.
        "inner_crop_x": 0.14,
        "inner_crop_y": 0.12,
        "visual_car_blob_min": 0.075,
        "visual_car_color_min": 0.095,
        "baseline_diff_min_ratio": 0.125,
        "baseline_contour_min_ratio": 0.060,
        "baseline_color_diff_min": 20.0,
        "baseline_fill_min": 0.20,
        "baseline_thickness_min": 0.26,
        "baseline_min_dim": 0.15,
        "baseline_edge_min": 0.025,
        "yolo_baseline_min": 0.44,
        "yolo_visual_min": 0.30,
        "yolo_slot_iou": 0.035,
        "yolo_cover_slot": 0.085,
        "yolo_cover_obj": 0.20,
        "yolo_center_min_cover": 0.08,
        "yolo_min_slot_area": 0.035,
        "direct_yolo_no_visual": 1.0,
        "direct_yolo_conf": 0.36,
        "direct_yolo_cover_slot": 0.075,
        "direct_yolo_cover_obj": 0.18,
        "direct_yolo_iou": 0.03,
        "direct_yolo_min_slot_area": 0.035,
        "direct_yolo_score": 0.80,
        "require_yolo_for_occ": 1.0,
        "allow_strong_visual_without_yolo": 1.0,
        "strong_visual_no_yolo_min_score": 0.60,
        "strong_baseline_no_yolo_min_score": 0.54,
        "no_yolo_score_cap": 0.18,
        "match_expand_x": 0.10,
        "match_expand_y": 0.28,
        "occ_on": 0.52,
        "empty_off": 0.30,
        "occ_confirm_frames": 2,
        "empty_confirm_frames": 2,
        "uncertain_counter_decay": 0,
    },
}

# Default 9-zone template for the toy board in reference_9zones_board.jpg.
# Coordinates are normalized inside the detected board plane: x1, y1, x2, y2.
# Zone order: 1-4 top car row, 5-7 bottom car row, 8-9 right horizontal row.
DEFAULT_SLOTS_TEMPLATE = [
    {"id": 1, "name": "top_car_zone_1", "box": [0.155, 0.08, 0.275, 0.465]},
    {"id": 2, "name": "top_car_zone_2", "box": [0.275, 0.08, 0.395, 0.465]},
    {"id": 3, "name": "top_car_zone_3", "box": [0.395, 0.08, 0.52, 0.465]},
    {"id": 4, "name": "top_car_zone_4", "box": [0.52, 0.08, 0.65, 0.465]},
    {"id": 5, "name": "bottom_car_zone_5", "box": [0.065, 0.535, 0.245, 0.895]},
    {"id": 6, "name": "bottom_car_zone_6", "box": [0.245, 0.535, 0.425, 0.895]},
    {"id": 7, "name": "bottom_car_zone_7", "box": [0.425, 0.535, 0.62, 0.895]},
    {"id": 8, "name": "right_horizontal_zone_8", "box": [0.765, 0.095, 0.965, 0.245]},
    {"id": 9, "name": "right_horizontal_zone_9", "box": [0.765, 0.235, 0.965, 0.395]},
]


def stop_handler(_sig=None, _frame=None):
    global STOP_REQUESTED
    STOP_REQUESTED = True


signal.signal(signal.SIGINT, stop_handler)


@dataclass
class BoardDetection:
    quad: np.ndarray  # TL, TR, BR, BL in frame coordinates
    confidence: float
    area_ratio: float
    mark_ratio: float
    source: str = "live"


@dataclass
class SlotResult:
    id: int
    label: str
    score: float
    raw_score: float
    polygon: np.ndarray
    box: np.ndarray
    source: str
    debug: dict[str, Union[float, str]] = field(default_factory=dict)


@dataclass
class SlotHistory:
    state: str = "empty"
    ema: float = 0.0
    occ_hits: int = 0
    empty_hits: int = 0
    last_raw: float = 0.0
    scores: deque = field(default_factory=lambda: deque(maxlen=9))


class SlotStabilizer:
    """EMA + hysteresis per slot, so labels stop flipping like they have stage fright."""

    def __init__(self, slot_ids: Iterable[int], args):
        self.args = args
        self.hist: dict[int, SlotHistory] = {int(i): SlotHistory() for i in slot_ids}

    def reset(self) -> None:
        for h in self.hist.values():
            h.state = "empty"
            h.ema = 0.0
            h.occ_hits = 0
            h.empty_hits = 0
            h.last_raw = 0.0
            h.scores.clear()

    def update(self, slot_id: int, raw_score: float) -> tuple[str, float]:
        raw_score = float(max(0.0, min(1.0, raw_score)))
        h = self.hist.setdefault(int(slot_id), SlotHistory())
        alpha = float(self.args.smooth_alpha)
        h.ema = raw_score if not h.scores else (h.ema * (1.0 - alpha) + raw_score * alpha)
        h.last_raw = raw_score
        h.scores.append(raw_score)

        occ_on = zone_override(slot_id, "occ_on", self.args.occ_on)
        empty_off = zone_override(slot_id, "empty_off", self.args.empty_off)
        occ_confirm_frames = int(round(zone_override(slot_id, "occ_confirm_frames", self.args.occ_confirm_frames)))
        empty_confirm_frames = int(round(zone_override(slot_id, "empty_confirm_frames", self.args.empty_confirm_frames)))
        uncertain_decay = int(round(zone_override(slot_id, "uncertain_counter_decay", 1)))

        # Hysteresis: occupied needs higher score to enter, empty needs lower score to leave.
        if h.ema >= occ_on:
            h.occ_hits += 1
            h.empty_hits = max(0, h.empty_hits - 1)
        elif h.ema <= empty_off:
            h.empty_hits += 1
            h.occ_hits = max(0, h.occ_hits - 1)
        else:
            # Uncertain zone: keep old state and slowly decay counters.
            h.occ_hits = max(0, h.occ_hits - uncertain_decay)
            h.empty_hits = max(0, h.empty_hits - uncertain_decay)

        if h.state == "empty" and h.occ_hits >= occ_confirm_frames:
            h.state = "occupied"
            h.empty_hits = 0
        elif h.state == "occupied" and h.empty_hits >= empty_confirm_frames:
            h.state = "empty"
            h.occ_hits = 0

        return h.state, h.ema


class BoardTracker:
    """Tracks the board quadrilateral and hides slots when the board is gone."""

    def __init__(self, args):
        self.args = args
        self.quad: Optional[np.ndarray] = None
        self.visible_hits = 0
        self.missed = 999
        self.last_conf = 0.0
        self.locked_at = 0.0

    def reset(self) -> None:
        self.quad = None
        self.visible_hits = 0
        self.missed = 999
        self.last_conf = 0.0
        self.locked_at = 0.0

    def update(self, det: Optional[BoardDetection]) -> Optional[BoardDetection]:
        if det is None or det.confidence < self.args.board_min_conf:
            self.missed += 1
            self.visible_hits = max(0, self.visible_hits - 1)
            if self.missed > self.args.board_reset_after:
                # Keep no ghost layout. If the board is gone, boxes are gone. Revolutionary.
                self.quad = None
            return None

        cand = det.quad.astype(np.float32)
        if self.quad is None:
            self.quad = cand
            self.visible_hits = 1
            self.missed = 0
            self.last_conf = det.confidence
            self.locked_at = time.time()
        else:
            # Reject sudden impossible jumps unless they persist by resetting and reacquiring.
            diag = max(1.0, float(np.linalg.norm(self.quad[0] - self.quad[2])))
            jump = float(np.mean(np.linalg.norm(cand - self.quad, axis=1)) / diag)
            if jump > self.args.board_max_jump:
                # Do not let one noisy board detection drag all slots away from
                # their fixed template positions. Hide/reacquire only after
                # repeated misses instead of jumping the layout immediately.
                self.visible_hits = max(0, self.visible_hits - 1)
                self.missed += 1
                if self.missed > self.args.board_reset_after:
                    self.quad = None
                    return None
                return BoardDetection(self.quad.copy(), self.last_conf or det.confidence, det.area_ratio, det.mark_ratio, "locked-hold")
            else:
                if self.visible_hits >= self.args.board_warmup_frames and jump <= self.args.board_locked_deadband:
                    # The board is already locked and this is only sub-pixel/handheld jitter.
                    # Hold the previous homography so slot boxes and labels do not shimmer.
                    self.visible_hits += 1
                    self.missed = 0
                    self.last_conf = det.confidence
                    return BoardDetection(self.quad.copy(), det.confidence, det.area_ratio, det.mark_ratio, "locked-stable")
                a = float(self.args.board_smooth_alpha)
                if self.visible_hits >= self.args.board_warmup_frames:
                    a = min(a, float(getattr(self.args, "board_locked_smooth_alpha", a)))
                self.quad = self.quad * (1.0 - a) + cand * a
                self.visible_hits += 1
            self.missed = 0
            self.last_conf = det.confidence

        if self.visible_hits < self.args.board_warmup_frames:
            return None
        return BoardDetection(self.quad.copy(), det.confidence, det.area_ratio, det.mark_ratio, det.source)

    @property
    def is_visible(self) -> bool:
        return self.quad is not None and self.visible_hits >= self.args.board_warmup_frames and self.missed <= self.args.board_max_missed


def resolve_path(text: Union[str, Path]) -> Path:
    p = Path(str(text).strip().strip('"'))
    if p.is_absolute():
        return p
    for base in (Path.cwd(), ROOT, PROJECT_ROOT):
        c = base / p
        if c.exists():
            return c
    return ROOT / p


def parse_source(source_text: str) -> Union[int, str]:
    text = str(source_text).strip().strip('"')
    if text.isdigit():
        return int(text)
    if text.lower().startswith(("http://", "https://", "rtsp://", "rtsps://")):
        return text
    return str(resolve_path(text))


def should_run_inference(frame_id: int, yolo_every: int) -> bool:
    """Return whether this frame owns a fresh inference result."""
    return frame_id > 0 and frame_id % max(1, int(yolo_every)) == 0


def results_for_frame(results: list[SlotResult], result_frame_id: Optional[int], frame_id: int, yolo_every: int = 1) -> list[SlotResult]:
    """Prevent detections computed for an older frame from being drawn on this one, allowing a short TTL."""
    if result_frame_id is None:
        return []
    if frame_id - result_frame_id <= max(1, yolo_every):
        return results
    return []


def choose_device(device_text: str) -> str:
    v = str(device_text).lower().strip()
    cuda_ok = False
    tm = _torch_module
    if tm is not None:
        try:
            cuda_ok = tm.cuda.is_available()
        except Exception:
            pass
    if v == "auto":
        return "0" if cuda_ok else "cpu"
    if v in {"cpu", "cuda", "mps"}:
        return v
    if v.isdigit():
        return v
    return "0" if cuda_ok else "cpu"


def parse_crop_ratio(text: str) -> Optional[tuple[float, float, float, float]]:
    text = str(text or "").strip()
    if not text:
        return None
    vals = tuple(float(x.strip()) for x in text.replace(";", ",").split(","))
    if len(vals) != 4:
        raise ValueError("--crop-ratio format: left,top,right,bottom. Example: 0.02,0.02,0.98,0.96")
    l, t, r, b = vals
    if not (0 <= l < r <= 1 and 0 <= t < b <= 1):
        raise ValueError("crop-ratio must be within 0..1 and left<right, top<bottom")
    return vals


def apply_crop_ratio(frame: np.ndarray, crop_ratio: Optional[tuple[float, float, float, float]]):
    if crop_ratio is None:
        return frame.copy(), 0, 0
    h, w = frame.shape[:2]
    l, t, r, b = crop_ratio
    x1, y1, x2, y2 = int(w * l), int(h * t), int(w * r), int(h * b)
    x1, y1 = max(0, min(w - 2, x1)), max(0, min(h - 2, y1))
    x2, y2 = max(x1 + 2, min(w, x2)), max(y1 + 2, min(h, y2))
    return frame[y1:y2, x1:x2].copy(), x1, y1


def rotate_frame(frame: np.ndarray, angle: int) -> np.ndarray:
    angle = int(angle) % 360
    if angle == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def open_capture(source: Union[int, str], width: int, height: int, fps: int):
    if isinstance(source, int):
        for name, backend in [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW), ("ANY", cv2.CAP_ANY)]:
            cap = cv2.VideoCapture(source, backend)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
            ok, frame = cap.read()
            if ok and frame is not None and frame.size > 0:
                print(f"[OK] Opened camera {source} with {name}: {frame.shape[1]}x{frame.shape[0]}")
                return cap
            cap.release()
        return cv2.VideoCapture(source)
    source_text = str(source)
    is_stream = source_text.lower().startswith(("http://", "https://", "rtsp://", "rtsps://"))
    if is_stream:
        backends = [("FFMPEG", getattr(cv2, "CAP_FFMPEG", cv2.CAP_ANY)), ("ANY", cv2.CAP_ANY)]
        for name, backend in backends:
            cap = cv2.VideoCapture(source_text, backend)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print(f"[OK] Opened stream with {name}: {source_text}")
            return cap
        print(f"[ERROR] Could not open stream source: {source_text}")
        return cv2.VideoCapture(source_text)
    return cv2.VideoCapture(source_text)


def enhance_frame(frame: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l2, a, b)), cv2.COLOR_LAB2BGR)


def order_quad_points(pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    ordered = np.array([
        pts[np.argmin(s)],      # top-left
        pts[np.argmin(d)],      # top-right
        pts[np.argmax(s)],      # bottom-right
        pts[np.argmax(d)],      # bottom-left
    ], dtype=np.float32)
    return ordered


def expand_quad(quad: np.ndarray, scale_x: float, scale_y: float) -> np.ndarray:
    q = np.asarray(quad, dtype=np.float32).reshape(4, 2)
    c = q.mean(axis=0)
    # Project to local axes from minAreaRect-ish order.
    out = q.copy()
    for i in range(4):
        v = q[i] - c
        out[i] = c + np.array([v[0] * scale_x, v[1] * scale_y], dtype=np.float32)
    return out


def clamp_quad_to_frame(quad: np.ndarray, shape: tuple[int, int, int]) -> np.ndarray:
    h, w = shape[:2]
    q = quad.copy().astype(np.float32)
    q[:, 0] = np.clip(q[:, 0], -w * 0.05, w * 1.05)
    q[:, 1] = np.clip(q[:, 1], -h * 0.05, h * 1.05)
    return q


def polygon_area(pts: np.ndarray) -> float:
    pts = np.asarray(pts, dtype=np.float32)
    return float(abs(cv2.contourArea(pts.reshape(-1, 1, 2))))


def make_board_masks(frame: np.ndarray, args: argparse.Namespace) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    yellow = cv2.inRange(
        hsv,
        np.array([args.yellow_h_min, args.yellow_s_min, args.yellow_v_min], np.uint8),
        np.array([args.yellow_h_max, 255, 255], np.uint8),
    )
    red1 = cv2.inRange(hsv, np.array([0, args.red_s_min, args.red_v_min], np.uint8), np.array([12, 255, 255], np.uint8))
    red2 = cv2.inRange(hsv, np.array([168, args.red_s_min, args.red_v_min], np.uint8), np.array([179, 255, 255], np.uint8))
    red = cv2.bitwise_or(red1, red2)
    white = cv2.inRange(hsv, np.array([0, 0, args.white_v_min], np.uint8), np.array([179, args.white_s_max, 255], np.uint8))

    # Green/orange overlay boxes are not in the raw camera frame, but if someone tests on screenshots,
    # this avoids letting the HUD become "the parking board", because apparently screenshots also need babysitting.
    if args.ignore_hud_area:
        h, w = yellow.shape[:2]
        yellow[: int(h * 0.28), : int(w * 0.36)] = 0
        red[: int(h * 0.28), : int(w * 0.36)] = 0
        white[: int(h * 0.28), : int(w * 0.36)] = 0

    primary = cv2.bitwise_or(yellow, red)
    primary = cv2.morphologyEx(primary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=1)

    # Big dilation connects the parking-line islands into one board-level cloud.
    k = max(3, int(args.board_connect_kernel) | 1)
    connected = cv2.morphologyEx(primary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)), iterations=1)
    connected = cv2.dilate(connected, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)), iterations=args.board_dilate_iter)

    return {"yellow": yellow, "red": red, "white": white, "primary": primary, "connected": connected}



def _order_strip_points_by_y(pts: np.ndarray) -> np.ndarray:
    """Return TL, TR, BR, BL for a thin red strip, robust to perspective."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    top2 = pts[np.argsort(pts[:, 1])[:2]]
    bot2 = pts[np.argsort(pts[:, 1])[2:]]
    tl, tr = top2[np.argsort(top2[:, 0])]
    bl, br = bot2[np.argsort(bot2[:, 0])]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def detect_board_quad_from_red_strip(frame: np.ndarray, args: argparse.Namespace) -> Optional[BoardDetection]:
    """Detect the toy parking board from the big red bottom strip.

    This is intentionally used before the generic yellow-line detector. The old detector let
    overlay boxes/HUD/watermark pull the homography to the whole screen, which is how empty
    slots started cosplaying as occupied slots. Peak computer vision comedy.
    """
    h, w = frame.shape[:2]
    if h < 80 or w < 80:
        return None

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    red1 = cv2.inRange(hsv, np.array([0, args.red_s_min, args.red_v_min], np.uint8), np.array([12, 255, 255], np.uint8))
    red2 = cv2.inRange(hsv, np.array([168, args.red_s_min, args.red_v_min], np.uint8), np.array([179, 255, 255], np.uint8))
    red = cv2.bitwise_or(red1, red2)
    # Ignore title bar and random red-ish junk near the top.
    red[: int(h * args.red_strip_ignore_top), :] = 0
    # Avoid left skin/background blobs in DroidCam close-ups.
    if args.red_strip_ignore_left > 0:
        red[:, : int(w * args.red_strip_ignore_left)] = 0

    k = max(5, int(args.red_strip_kernel) | 1)
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)), iterations=2)

    contours, _ = cv2.findContours(red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = float(max(1, h * w))
    best = None
    for c in contours:
        area = float(cv2.contourArea(c))
        x, y, cw, ch = cv2.boundingRect(c)
        if area < args.red_strip_min_area * img_area:
            continue
        if (y + ch * 0.5) < args.red_strip_min_center_y * h:
            continue
        rect = cv2.minAreaRect(c)
        (_cx, _cy), (rw, rh), _ang = rect
        if rw <= 1 or rh <= 1:
            continue
        long_side = max(float(rw), float(rh))
        short_side = min(float(rw), float(rh))
        aspect = long_side / max(1.0, short_side)
        if aspect < args.red_strip_min_aspect:
            continue
        if long_side < args.red_strip_min_width * w:
            continue
        if short_side < args.red_strip_min_height * h or short_side > args.red_strip_max_height * h:
            continue
        # Prefer the huge horizontal-ish red board stripe low in the frame.
        score = area * aspect * (1.0 + y / max(1.0, h))
        if best is None or score > best[0]:
            best = (score, rect, area, aspect, (x, y, cw, ch))

    if best is None:
        return None

    _score, rect, area, aspect, bbox = best
    bx, by, bw, bh = bbox
    top_margin = float(args.board_red_top_margin) * h

    if getattr(args, "red_strip_axis_board", True):
        # The toy board in DroidCam is usually close to a fronto-parallel rectangle.
        # Axis-aligned red-strip extrapolation prevents the old tilted homography from throwing
        # fixed slots outside the parking board.
        bottom = float(by + bh)
        board_h = max(float(bh) * float(args.board_red_axis_h_factor), float(bw) / max(1e-6, float(args.board_red_axis_aspect)))
        top = max(top_margin, bottom - board_h)
        quad = np.array([[bx, top], [bx + bw, top], [bx + bw, bottom], [bx, bottom]], dtype=np.float32)
    else:
        strip = _order_strip_points_by_y(cv2.boxPoints(rect))
        tl, tr, br, bl = strip
        left_side = bl - tl
        right_side = br - tr

        up = float(args.board_red_up_factor)
        min_top = min(float((tl - left_side * up)[1]), float((tr - right_side * up)[1]))
        if min_top < top_margin:
            possible = []
            if abs(float(left_side[1])) > 1.0:
                possible.append((float(tl[1]) - top_margin) / float(left_side[1]))
            if abs(float(right_side[1])) > 1.0:
                possible.append((float(tr[1]) - top_margin) / float(right_side[1]))
            if possible:
                up = min(up, max(float(args.board_red_min_up_factor), min(possible)))
        quad = np.array([tl - left_side * up, tr - right_side * up, br, bl], dtype=np.float32)

    quad = expand_quad(quad, args.board_red_expand_x, args.board_red_expand_y)
    quad = clamp_quad_to_frame(quad, frame.shape)

    q_area = polygon_area(quad)
    if q_area / img_area < args.board_min_area or q_area / img_area > args.board_max_area:
        return None

    # Verify that the extrapolated plane actually contains board markings.
    masks = make_board_masks(frame, args)
    frame_to_board = cv2.getPerspectiveTransform(quad, np.array([[0, 0], [CANON_W, 0], [CANON_W, CANON_H], [0, CANON_H]], np.float32))
    primary_warp = cv2.warpPerspective(masks["primary"], frame_to_board, (CANON_W, CANON_H))
    primary_ratio = float(np.count_nonzero(primary_warp)) / float(CANON_W * CANON_H)
    if primary_ratio < max(0.006, args.board_min_mark_ratio * 0.45):
        return None

    conf = min(1.0, 0.55 + min(primary_ratio / max(1e-6, args.board_expected_mark_ratio), 1.0) * 0.35 + min(aspect / 7.0, 1.0) * 0.10)
    return BoardDetection(quad=quad, confidence=conf, area_ratio=float(q_area / img_area), mark_ratio=primary_ratio, source="red-strip-board")

def detect_board_quad(frame: np.ndarray, args: argparse.Namespace) -> Optional[BoardDetection]:
    if getattr(args, "red_strip_board", True):
        red_board = detect_board_quad_from_red_strip(frame, args)
        if red_board is not None:
            return red_board

    masks = make_board_masks(frame, args)
    connected = masks["connected"]
    h, w = frame.shape[:2]
    img_area = float(max(1, h * w))

    num, labels, stats, _centroids = cv2.connectedComponentsWithStats(connected, connectivity=8)
    keep_ids: list[int] = []
    for i in range(1, num):
        x, y, cw, ch, area = stats[i]
        if area < args.board_min_component_area * img_area:
            continue
        # Reject tiny line islands and weird titlebar/edge junk.
        if cw < args.board_min_width * w or ch < args.board_min_height * h:
            continue
        keep_ids.append(i)

    if not keep_ids:
        return None

    # Use the union of relevant components, not the single largest, because the toy board has separated markings.
    sel = np.isin(labels, keep_ids)
    ys, xs = np.where(sel)
    if len(xs) < args.board_min_pixels:
        return None

    pts = np.column_stack([xs, ys]).astype(np.float32)
    rect = cv2.minAreaRect(pts)
    (cx, cy), (rw, rh), _angle = rect
    if rw <= 1 or rh <= 1:
        return None
    aspect = max(rw, rh) / max(1.0, min(rw, rh))
    area_ratio = float((rw * rh) / img_area)
    if aspect < args.board_min_aspect or aspect > args.board_max_aspect:
        return None
    if area_ratio < args.board_min_area or area_ratio > args.board_max_area:
        return None

    quad = order_quad_points(cv2.boxPoints(rect))
    quad = expand_quad(quad, args.board_expand_x, args.board_expand_y)
    quad = clamp_quad_to_frame(quad, frame.shape)

    # Confidence from how many board-colored pixels exist inside the candidate quad.
    frame_to_board = cv2.getPerspectiveTransform(quad, np.array([[0, 0], [CANON_W, 0], [CANON_W, CANON_H], [0, CANON_H]], np.float32))
    primary_warp = cv2.warpPerspective(masks["primary"], frame_to_board, (CANON_W, CANON_H))
    white_warp = cv2.warpPerspective(masks["white"], frame_to_board, (CANON_W, CANON_H))
    primary_ratio = float(np.count_nonzero(primary_warp)) / float(CANON_W * CANON_H)
    white_ratio = float(np.count_nonzero(white_warp)) / float(CANON_W * CANON_H)

    mark_ratio = primary_ratio + min(white_ratio, 0.08) * 0.25
    conf = min(1.0, max(0.0, (mark_ratio / max(1e-6, args.board_expected_mark_ratio)) * 0.65 + min(area_ratio / 0.45, 1.0) * 0.35))
    if mark_ratio < args.board_min_mark_ratio:
        return None

    return BoardDetection(quad=quad, confidence=conf, area_ratio=area_ratio, mark_ratio=mark_ratio, source="color-board")


def load_slots_template(path: Path, create_if_missing: bool = False) -> list[dict]:
    if not path.exists():
        if path.name == DEFAULT_TEMPLATE.name:
            for candidate in LEGACY_TEMPLATE_CANDIDATES:
                if candidate.exists():
                    slots = load_slots_template(candidate, create_if_missing=False)
                    if len(slots) == 9:
                        print(f"[INFO] {DEFAULT_TEMPLATE.name} not found; using 9-zone legacy template once: {candidate.name}")
                        return slots
        if create_if_missing:
            save_slots_template(path, DEFAULT_SLOTS_TEMPLATE)
            return [dict(s) for s in DEFAULT_SLOTS_TEMPLATE]
        raise FileNotFoundError(f"Missing 9-zone slot template: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_slots = data.get("slots", data if isinstance(data, list) else [])
    except Exception:
        raw_slots = DEFAULT_SLOTS_TEMPLATE
    slots = []
    for i, s in enumerate(raw_slots, start=1):
        box = s.get("box") if isinstance(s, dict) else None
        if not isinstance(box, list) or len(box) != 4:
            continue
        x1, y1, x2, y2 = [float(v) for v in box]
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            continue
            
        raw_id = s.get("id", i) if isinstance(s, dict) else i
        slot_id = int(raw_id) if isinstance(raw_id, (int, str, float)) else i
        raw_name = s.get("name", f"slot_{i}") if isinstance(s, dict) else f"slot_{i}"
        slots.append({"id": slot_id, "name": str(raw_name), "box": [x1, y1, x2, y2]})
    return slots or [dict(s) for s in DEFAULT_SLOTS_TEMPLATE]


def resolve_board_cache_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Return (load_path, save_path). The new 9-zone cache is written even when legacy is read."""
    save_path = resolve_path(args.board_cache)
    load_path = save_path
    if not load_path.exists() and save_path.name == DEFAULT_BOARD_CACHE.name:
        for candidate in LEGACY_BOARD_CACHE_CANDIDATES:
            if candidate.exists():
                load_path = candidate
                print(f"[INFO] {DEFAULT_BOARD_CACHE.name} not found; using legacy cache once: {candidate.name}")
                break
    return load_path, save_path


def load_board_cache_quad(path: Path) -> Optional[np.ndarray]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        quad = np.asarray(data.get("quad", []), dtype=np.float32).reshape(4, 2)
        if not np.isfinite(quad).all():
            return None
        return quad
    except Exception:
        return None


def validate_board_quad(frame: np.ndarray, quad: np.ndarray, args, source: str = "cache") -> Optional[BoardDetection]:
    h, w = frame.shape[:2]
    q = np.asarray(quad, dtype=np.float32).reshape(4, 2)
    if not np.isfinite(q).all():
        return None
    is_cache = "cache" in str(source).lower()
    margin = float(getattr(args, "board_max_outside_margin", 0.08))
    if is_cache:
        margin = min(margin, float(getattr(args, "board_cache_max_outside_margin", 0.015)))
    if (
        q[:, 0].min() < -w * margin or q[:, 0].max() > w * (1.0 + margin)
        or q[:, 1].min() < -h * margin or q[:, 1].max() > h * (1.0 + margin)
    ):
        return None
    area_ratio = polygon_area(q) / float(max(1, h * w))
    max_area = float(args.board_max_area)
    if is_cache:
        max_area = min(max_area, float(getattr(args, "board_cache_max_area", 0.92)))
    if area_ratio < args.board_min_area or area_ratio > max_area:
        return None

    masks = make_board_masks(frame, args)
    frame_to_board = cv2.getPerspectiveTransform(q, np.array([[0, 0], [CANON_W, 0], [CANON_W, CANON_H], [0, CANON_H]], np.float32))
    primary_warp = cv2.warpPerspective(masks["primary"], frame_to_board, (CANON_W, CANON_H))
    white_warp = cv2.warpPerspective(masks["white"], frame_to_board, (CANON_W, CANON_H))
    primary_ratio = float(np.count_nonzero(primary_warp)) / float(CANON_W * CANON_H)
    white_ratio = float(np.count_nonzero(white_warp)) / float(CANON_W * CANON_H)
    mark_ratio = primary_ratio + min(white_ratio, 0.08) * 0.25
    if mark_ratio < args.board_min_mark_ratio:
        return None
    conf = min(1.0, max(0.0, (mark_ratio / max(1e-6, args.board_expected_mark_ratio)) * 0.70 + min(area_ratio / 0.45, 1.0) * 0.30))
    return BoardDetection(quad=q.copy(), confidence=conf, area_ratio=area_ratio, mark_ratio=mark_ratio, source=source)


def quad_delta_ratio(a: np.ndarray, b: np.ndarray) -> float:
    qa = np.asarray(a, dtype=np.float32).reshape(4, 2)
    qb = np.asarray(b, dtype=np.float32).reshape(4, 2)
    diag = max(1.0, float(np.linalg.norm(qb[0] - qb[2])))
    return float(np.mean(np.linalg.norm(qa - qb, axis=1)) / diag)


def save_slots_template(path: Path, slots: list[dict]) -> None:
    data = {
        "version": 14,
        "note": "ParkingVision V14 9-zone board-plane template. Coordinates are normalized x1,y1,x2,y2 inside the locked board plane.",
        "canonical_size": [CANON_W, CANON_H],
        "slots": slots,
    }
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def normalized_box_to_canon(box: list[float]) -> np.ndarray:
    x1, y1, x2, y2 = [float(v) for v in box]
    return np.array([x1 * CANON_W, y1 * CANON_H, x2 * CANON_W, y2 * CANON_H], dtype=np.float32)


def expand_canon_box(box: np.ndarray, expand_x: float = 0.0, expand_y: float = 0.0) -> np.ndarray:
    x1, y1, x2, y2 = map(float, box.tolist())
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
    dx = bw * max(0.0, float(expand_x))
    dy = bh * max(0.0, float(expand_y))
    return np.array([
        max(0.0, x1 - dx),
        max(0.0, y1 - dy),
        min(float(CANON_W), x2 + dx),
        min(float(CANON_H), y2 + dy),
    ], dtype=np.float32)


def canon_box_polygon(box: np.ndarray) -> np.ndarray:
    x1, y1, x2, y2 = map(float, box.tolist())
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)


def iou_xyxy(a: np.ndarray, b: np.ndarray) -> float:
    ax1, ay1, ax2, ay2 = map(float, a)
    bx1, by1, bx2, by2 = map(float, b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1.0, (bx2 - bx1) * (by2 - by1))
    return float(inter / max(1.0, area_a + area_b - inter))


def overlap_ratio(a: np.ndarray, b: np.ndarray) -> float:
    ax1, ay1, ax2, ay2 = map(float, a)
    bx1, by1, bx2, by2 = map(float, b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    return float(inter / area_a)


def _points_to_frame(points: np.ndarray, shape: tuple[int, int, int]) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2).copy()
    if pts.size == 0:
        return pts
    h, w = shape[:2]
    if float(np.nanmax(np.abs(pts))) <= 1.5:
        pts[:, 0] *= float(w)
        pts[:, 1] *= float(h)
    return pts


def _region_to_polygon(region, shape: tuple[int, int, int]) -> Optional[np.ndarray]:
    if isinstance(region, dict):
        raw = region.get("polygon") or region.get("points") or region.get("pts")
        box = region.get("box") or region.get("bbox") or region.get("roi")
    else:
        raw = region
        box = None
    if raw is None and box is not None and len(box) == 4:
        x1, y1, x2, y2 = [float(v) for v in box]
        raw = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    if raw is None:
        return None
    try:
        pts = _points_to_frame(np.asarray(raw, dtype=np.float32), shape)
    except Exception:
        return None
    if pts.shape[0] < 3:
        return None
    return pts.astype(np.float32)


def load_regions(path: Path) -> dict[str, list[dict]]:
    data_out = {"rois": [], "slots": []}
    if not path.exists():
        return data_out
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] Khong doc duoc regions.json: {e}")
        return data_out

    if isinstance(data, list):
        data_out["rois"] = [{"id": i + 1, "region": r} for i, r in enumerate(data)]
        return data_out
    if not isinstance(data, dict):
        return data_out

    slots = data.get("slots") or data.get("parking_slots") or []
    for i, slot in enumerate(slots, start=1):
        if isinstance(slot, dict):
            data_out["slots"].append({"id": int(slot.get("id", i)), "name": str(slot.get("name", f"slot_{i}")), "region": slot})
        else:
            data_out["slots"].append({"id": i, "name": f"slot_{i}", "region": slot})

    regions = data.get("regions") or data.get("rois") or data.get("parking_regions") or []
    if isinstance(regions, dict):
        regions = [regions]
    elif regions and not isinstance(regions, list):
        regions = [regions]
    roi_val = data.get("roi")
    if roi_val is not None:
        regions.append(roi_val)
    parking_roi_val = data.get("parking_roi")
    if parking_roi_val is not None:
        regions.append(parking_roi_val)
    for i, region in enumerate(regions, start=1):
        data_out["rois"].append({"id": i, "region": region})
    return data_out


def point_in_polygon_xy(point: tuple[float, float], polygon: np.ndarray) -> bool:
    return cv2.pointPolygonTest(np.asarray(polygon, dtype=np.float32), (float(point[0]), float(point[1])), False) >= 0


def det_in_regions(det: dict, frame_shape: tuple[int, int, int], args: argparse.Namespace) -> bool:
    x1, y1, x2, y2 = map(float, det["box"].tolist())
    cx, cy = (x1 + x2) * 0.5, (y1 + y2) * 0.5
    roi = parse_crop_ratio(args.parking_roi) if getattr(args, "parking_roi", "") else None
    if roi is not None:
        h, w = frame_shape[:2]
        l, t, r, b = roi
        if not (l <= cx / w <= r and t <= cy / h <= b):
            return False

    regions = getattr(args, "_regions", None) or {"rois": [], "slots": []}
    rois = regions.get("rois", [])
    slots = regions.get("slots", [])
    if not rois and not slots:
        return True
    for item in rois + slots:
        poly = _region_to_polygon(item.get("region"), frame_shape)
        if poly is not None and point_in_polygon_xy((cx, cy), poly):
            return True
    return False


def normalize_parking_label(model: YOLOModelProtocol, cls_id: int) -> str:
    names_obj = model.names
    if isinstance(names_obj, dict):
        base_name = names_obj.get(cls_id, cls_id)
    elif isinstance(names_obj, list) and 0 <= cls_id < len(names_obj):
        base_name = names_obj[cls_id]
    else:
        base_name = cls_id
    name = str(base_name).lower().strip()
    if "empty" in name or "vacant" in name or "free" in name:
        return "empty"
    if "occup" in name or "busy" in name or "parked" in name:
        return "occupied"
    if any(k in name for k in ("car", "vehicle", "truck", "bus", "motorcycle", "motorbike", "van")):
        return "occupied"
    return "occupied" if cls_id == 1 else "empty"


def nms_dets(dets: list[dict], iou_threshold: float, class_aware: bool = False) -> list[dict]:
    if not dets:
        return []
    out: list[dict] = []
    groups = sorted({d.get("label", "*") for d in dets}) if class_aware else ["*"]
    for g in groups:
        items = dets if g == "*" else [d for d in dets if d.get("label") == g]
        items = sorted(items, key=lambda d: float(d.get("conf", 1.0)), reverse=True)
        while items:
            best = items.pop(0)
            out.append(best)
            items = [d for d in items if iou_xyxy(best["box"], d["box"]) < iou_threshold]
    return out


def detect_with_parking_model(model: Optional[YOLOModelProtocol], frame: np.ndarray, args: argparse.Namespace) -> list[dict]:
    if model is None:
        return []
    inp = enhance_frame(frame) if args.enhance else frame
    results = model.predict(
        inp,
        conf=args.model_conf,
        imgsz=args.model_imgsz,
        iou=args.model_iou,
        max_det=args.model_max_det,
        device=args.device,
        augment=args.tta,
        verbose=False,
    )
    h, w = frame.shape[:2]
    img_area = float(max(1, h * w))
    dets: list[dict] = []
    if not results or results[0].boxes is None:
        return dets
    for b in results[0].boxes:
        cls_id = int(b.cls[0].item())
        conf = float(b.conf[0].item())
        label = normalize_parking_label(model, cls_id)
        if label == "empty" and conf < args.empty_conf:
            continue
        if label == "occupied" and conf < args.occupied_conf:
            continue
        x1, y1, x2, y2 = map(float, b.xyxy[0].tolist())
        bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
        area = (bw * bh) / img_area
        if area < args.det_min_area or area > args.det_max_area:
            continue
        dets.append({"label": label, "conf": conf, "box": np.array([x1, y1, x2, y2], dtype=np.float32), "source": "parking-yolo"})
    return nms_dets(dets, args.det_post_iou, class_aware=True)


def detect_vehicles(vehicle_model: Optional[YOLOModelProtocol], frame: np.ndarray, args: argparse.Namespace) -> list[dict]:
    if vehicle_model is None:
        return []
    inp = enhance_frame(frame) if args.enhance else frame
    results = vehicle_model.predict(
        inp,
        conf=args.vehicle_conf,
        imgsz=args.vehicle_imgsz,
        iou=args.vehicle_iou,
        max_det=args.vehicle_max_det,
        device=args.device,
        augment=False,
        verbose=False,
    )
    h, w = frame.shape[:2]
    img_area = float(max(1, h * w))
    dets: list[dict] = []
    if not results or results[0].boxes is None:
        return dets
    for b in results[0].boxes:
        cls_id = int(b.cls[0].item())
        if cls_id not in COCO_VEHICLE_CLASSES:
            continue
        conf = float(b.conf[0].item())
        x1, y1, x2, y2 = map(float, b.xyxy[0].tolist())
        bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
        area = (bw * bh) / img_area
        aspect = bw / bh
        if area < args.vehicle_min_area or area > args.vehicle_max_area:
            continue
        if aspect < args.vehicle_min_aspect or aspect > args.vehicle_max_aspect:
            continue
        dets.append({"label": "occupied", "conf": conf, "box": np.array([x1, y1, x2, y2], dtype=np.float32), "source": "vehicle-yolo"})
    return nms_dets(dets, args.det_post_iou, class_aware=False)


def frame_det_to_canon_box(det_box: np.ndarray, frame_to_board: np.ndarray) -> np.ndarray:
    x1, y1, x2, y2 = map(float, det_box.tolist())
    pts = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32).reshape(-1, 1, 2)
    dst = cv2.perspectiveTransform(pts, frame_to_board).reshape(-1, 2)
    xs, ys = dst[:, 0], dst[:, 1]
    return np.array([float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())], dtype=np.float32)


def crop_xyxy(img: np.ndarray, box: np.ndarray, pad_ratio: float = 0.0) -> np.ndarray:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = map(float, box.tolist())
    bw, bh = x2 - x1, y2 - y1
    x1 -= bw * pad_ratio
    x2 += bw * pad_ratio
    y1 -= bh * pad_ratio
    y2 += bh * pad_ratio
    x1, y1 = max(0, int(round(x1))), max(0, int(round(y1)))
    x2, y2 = min(w, int(round(x2))), min(h, int(round(y2)))
    if x2 <= x1 or y2 <= y1:
        return img[0:0, 0:0]
    return img[y1:y2, x1:x2]


def zone_override(slot_id: Optional[int], key: str, default: float) -> float:
    if slot_id is None:
        return float(default)
    return float(ZONE_OCCUPANCY_OVERRIDES.get(int(slot_id), {}).get(key, default))


def crop_slot_inner(img: np.ndarray, box: np.ndarray, args, slot_id: Optional[int] = None) -> np.ndarray:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = map(float, box.tolist())
    bw, bh = x2 - x1, y2 - y1
    crop_x = zone_override(slot_id, "inner_crop_x", args.visual_inner_crop)
    crop_y = zone_override(slot_id, "inner_crop_y", args.visual_inner_crop)
    x1 += bw * crop_x
    x2 -= bw * crop_x
    y1 += bh * crop_y
    y2 -= bh * crop_y
    x1, y1 = max(0, int(round(x1))), max(0, int(round(y1)))
    x2, y2 = min(w, int(round(x2))), min(h, int(round(y2)))
    if x2 <= x1 or y2 <= y1:
        return img[0:0, 0:0]
    return img[y1:y2, x1:x2]



def remove_board_marking_pixels(hsv: np.ndarray, candidate: np.ndarray, args, *, remove_red: bool = True) -> np.ndarray:
    """Remove printed parking-board markings from an object mask.

    The previous V12.1 counted yellow parking lines, white arrows/text, and table glare as
    "car evidence". That is how we got five occupied slots from two toy cars. Stunning.
    V13 only trusts thick non-board object blobs inside the inner part of a slot.
    """
    if candidate.size == 0:
        return candidate
    hch, sch, vch = cv2.split(hsv)

    # Printed yellow bay lines and warning stripes.
    yellow = (
        (hch >= args.board_line_yellow_h_min)
        & (hch <= args.board_line_yellow_h_max)
        & (sch >= args.board_line_s_min)
        & (vch >= args.board_line_v_min)
    )
    # Red board markings can exist, but toy vehicles can be red too. Keep red
    # available for visual occupancy when the caller will apply object-blob checks.
    red = (
        (((hch <= args.board_line_red_h_max1) | (hch >= args.board_line_red_h_min2)))
        & (sch >= args.board_line_s_min)
        & (vch >= args.board_line_v_min)
    )
    # White printed arrows, Vietnamese text, DroidCam watermark, paper border.
    white_mark = (sch <= args.board_line_white_s_max) & (vch >= args.board_line_white_v_min)

    out = candidate.copy()
    board_mark = yellow | white_mark
    if remove_red:
        board_mark = board_mark | red
    out[board_mark] = 0
    return out


def filter_object_candidate_mask(candidate: np.ndarray, args, *, white_mode: bool = False) -> tuple[np.ndarray, dict[str, float]]:
    """Keep thick car-like blobs; reject thin parking lines and text fragments."""
    mask = (candidate > 0).astype(np.uint8) * 255
    if mask.size == 0:
        return mask, {
            "max_component": 0.0, "kept_component": 0.0, "kept_count": 0.0,
            "best_thickness": 0.0, "best_min_dim": 0.0, "best_max_dim": 0.0
        }

    h, w = mask.shape[:2]
    area_total = float(max(1, h * w))

    # Join vehicle body pieces but avoid turning slot lines into fake blocks.
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=1)

    num, labels, stats, _cent = cv2.connectedComponentsWithStats(mask, connectivity=8)
    kept = np.zeros_like(mask)
    max_component = 0.0
    kept_component = 0.0
    kept_count = 0
    best_thickness = 0.0
    best_min_dim = 0.0
    best_max_dim = 0.0

    for i in range(1, num):
        x, y, bw, bh, area = stats[i]
        if bw <= 2 or bh <= 2:
            continue
        area_ratio = float(area) / area_total
        max_component = max(max_component, area_ratio)
        thickness = float(min(bw, bh)) / float(max(1, max(bw, bh)))
        min_dim_ratio = float(min(bw / max(1, w), bh / max(1, h)))
        max_dim_ratio = float(max(bw / max(1, w), bh / max(1, h)))

        if white_mode:
            keep = (
                args.allow_white_vehicle
                and area_ratio >= args.visual_white_min_component_area
                and thickness >= args.visual_white_min_thickness
                and min_dim_ratio >= args.visual_white_min_dim_ratio
                and max_dim_ratio >= args.visual_white_min_long_ratio
            )
        else:
            keep = (
                area_ratio >= args.visual_color_min_component_area
                and thickness >= args.visual_color_min_thickness
                and min_dim_ratio >= args.visual_color_min_dim_ratio
                and max_dim_ratio >= args.visual_color_min_long_ratio
            )

        if keep:
            kept[labels == i] = 255
            kept_component = max(kept_component, area_ratio)
            kept_count += 1
            if area_ratio >= kept_component:
                best_thickness = thickness
                best_min_dim = min_dim_ratio
                best_max_dim = max_dim_ratio

    if kept_count:
        kept = cv2.morphologyEx(kept, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=1)
    return kept, {
        "max_component": max_component,
        "kept_component": kept_component,
        "kept_count": float(kept_count),
        "best_thickness": best_thickness,
        "best_min_dim": best_min_dim,
        "best_max_dim": best_max_dim,
    }


def visual_occupancy_score_warped(warped: np.ndarray, slot_box: np.ndarray, args, slot_id: Optional[int] = None) -> tuple[float, dict[str, float]]:
    # Stronger inner crop: ignore borders/labels/slot walls. Cars sit in the body of the slot.
    roi = crop_slot_inner(warped, slot_box, args, slot_id)
    if roi.size == 0 or roi.shape[0] < 8 or roi.shape[1] < 8:
        return 0.0, {"color": 0.0, "blob": 0.0, "dark": 1.0}

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    hch, sch, vch = cv2.split(hsv)

    # Vehicle candidate = saturated, visible, NON-board color.
    # This deliberately excludes yellow lane lines, red board borders, white arrows/text, and DroidCam text.
    color_candidate = ((sch >= args.visual_sat_min) & (vch >= args.visual_val_min)).astype(np.uint8) * 255
    color_candidate = remove_board_marking_pixels(hsv, color_candidate, args, remove_red=args.visual_remove_red_markings)

    # Optional white/silver vehicles. Off by default because this toy board has a lot of white text/glare.
    white_candidate = np.zeros_like(color_candidate)
    if args.allow_white_vehicle:
        white_candidate = ((sch <= args.visual_white_sat_max) & (vch >= args.visual_white_val_min)).astype(np.uint8) * 255
        white_candidate = remove_board_marking_pixels(hsv, white_candidate, args)

    # Hard edge removal after the inner crop. Thin printed lines love living near edges.
    eh, ew = color_candidate.shape[:2]
    by = max(1, int(eh * args.visual_edge_crop_y))
    bx = max(1, int(ew * args.visual_edge_crop_x))
    for mm in (color_candidate, white_candidate):
        mm[:by, :] = 0
        mm[-by:, :] = 0
        mm[:, :bx] = 0
        mm[:, -bx:] = 0

    color_keep, color_meta = filter_object_candidate_mask(color_candidate, args, white_mode=False)
    white_keep, white_meta = filter_object_candidate_mask(white_candidate, args, white_mode=True)
    obj_mask = cv2.bitwise_or(color_keep, white_keep)

    obj_ratio = float(np.count_nonzero(obj_mask)) / float(max(1, obj_mask.size))
    blob_ratio = 0.0
    blob_thickness = 0.0
    min_dim = 0.0
    max_dim = 0.0
    cnts, _ = cv2.findContours(obj_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        largest = max(cnts, key=cv2.contourArea)
        area = float(cv2.contourArea(largest))
        x, y, bw, bh = cv2.boundingRect(largest)
        blob_ratio = area / float(max(1, roi.shape[0] * roi.shape[1]))
        blob_thickness = float(min(bw, bh)) / float(max(1, max(bw, bh)))
        min_dim = float(min(bw / max(1, roi.shape[1]), bh / max(1, roi.shape[0])))
        max_dim = float(max(bw / max(1, roi.shape[1]), bh / max(1, roi.shape[0])))

    mean_v = float(np.mean(np.asarray(vch, dtype=np.float32)))
    std_v = float(np.std(np.asarray(vch, dtype=np.float32)))

    visual_car_blob_min = zone_override(slot_id, "visual_car_blob_min", args.visual_car_blob_min)
    visual_car_color_min = zone_override(slot_id, "visual_car_color_min", args.visual_car_color_min)
    has_car_blob = (
        blob_ratio >= visual_car_blob_min
        and obj_ratio >= visual_car_color_min
        and blob_thickness >= args.visual_min_blob_thickness
        and min_dim >= args.visual_car_min_dim
        and max_dim >= args.visual_car_max_dim
    )
    uniform_board_like = (
        obj_ratio >= args.visual_max_uniform_color_ratio
        and blob_ratio >= args.visual_max_uniform_color_ratio
        and std_v <= args.visual_uniform_max_std
    )
    if uniform_board_like:
        has_car_blob = False

    if not has_car_blob:
        # Tiny specks and parking lines should not accumulate into Occupied.
        score = min(0.22, obj_ratio * 1.6 + blob_ratio * 2.0)
    else:
        score = (
            min(blob_ratio / max(1e-6, args.visual_blob_ref), 1.0) * args.visual_blob_weight
            + min(obj_ratio / max(1e-6, args.visual_color_ref), 1.0) * args.visual_color_weight
            + min(std_v / 95.0, 1.0) * args.visual_std_weight
        )

    # Dark, flat, low-object evidence = empty.
    if mean_v < args.visual_dark_mean and std_v < args.visual_dark_std and obj_ratio < args.visual_dark_color:
        score *= 0.25

    score = float(max(0.0, min(1.0, score)))
    return score, {
        "color": obj_ratio,
        "blob": blob_ratio,
        "thick_blob": blob_ratio if has_car_blob else 0.0,
        "thickness": blob_thickness,
        "mean": mean_v,
        "std": std_v,
        "min_dim": min_dim,
        "max_dim": max_dim,
        "uniform_board_like": 1.0 if uniform_board_like else 0.0,
        "color_kept": color_meta.get("kept_component", 0.0),
        "white_kept": white_meta.get("kept_component", 0.0),
    }


def warp_board_to_canon(frame: np.ndarray, board_det: BoardDetection) -> np.ndarray:
    quad = board_det.quad.astype(np.float32)
    frame_to_board = cv2.getPerspectiveTransform(quad, np.array([[0, 0], [CANON_W, 0], [CANON_W, CANON_H], [0, CANON_H]], np.float32))
    return cv2.warpPerspective(frame, frame_to_board, (CANON_W, CANON_H))


def load_empty_baseline(path: Path) -> Optional[np.ndarray]:
    if not path.exists():
        return None
    img = cv2.imread(str(path))
    if img is None or img.size == 0:
        print(f"[WARN] Empty baseline exists but cannot be read: {path}")
        return None
    if img.shape[1] != CANON_W or img.shape[0] != CANON_H:
        img = cv2.resize(img, (CANON_W, CANON_H), interpolation=cv2.INTER_AREA)
    return img


def save_empty_baseline(path: Path, warped_board: np.ndarray) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(path), warped_board)
    if ok:
        print(f"[OK] Saved empty baseline: {path}")
    else:
        print(f"[ERROR] Could not save empty baseline: {path}")
    return bool(ok)


def baseline_occupancy_score_warped(
    warped: np.ndarray,
    baseline_warped: Optional[np.ndarray],
    slot_box: np.ndarray,
    args,
    slot_id: Optional[int] = None,
) -> tuple[float, dict[str, float]]:
    if baseline_warped is None:
        return 0.0, {
            "present": 0.0,
            "diff_ratio": 0.0,
            "contour": 0.0,
            "color_diff": 0.0,
            "edge_diff": 0.0,
            "strong": 0.0,
        }

    roi = crop_slot_inner(warped, slot_box, args, slot_id)
    base_roi = crop_slot_inner(baseline_warped, slot_box, args, slot_id)
    if roi.size == 0 or base_roi.size == 0 or roi.shape[0] < 8 or roi.shape[1] < 8:
        return 0.0, {
            "present": 1.0,
            "diff_ratio": 0.0,
            "contour": 0.0,
            "color_diff": 0.0,
            "edge_diff": 0.0,
            "strong": 0.0,
        }
    if roi.shape[:2] != base_roi.shape[:2]:
        base_roi = cv2.resize(base_roi, (roi.shape[1], roi.shape[0]), interpolation=cv2.INTER_AREA)

    diff = cv2.absdiff(roi, base_roi)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    hsv_now = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hsv_base = cv2.cvtColor(base_roi, cv2.COLOR_BGR2HSV)

    valid = np.ones(diff_gray.shape, np.uint8) * 255
    valid = remove_board_marking_pixels(hsv_now, valid, args, remove_red=False)
    valid = remove_board_marking_pixels(hsv_base, valid, args, remove_red=False)

    rh, rw = diff_gray.shape[:2]
    by = max(1, int(rh * args.visual_edge_crop_y))
    bx = max(1, int(rw * args.visual_edge_crop_x))
    valid[:by, :] = 0
    valid[-by:, :] = 0
    valid[:, :bx] = 0
    valid[:, -bx:] = 0

    diff_mask = ((diff_gray >= args.baseline_diff_threshold).astype(np.uint8) * 255)
    diff_mask = cv2.bitwise_and(diff_mask, valid)
    diff_mask = cv2.morphologyEx(diff_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    diff_mask = cv2.morphologyEx(diff_mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=1)

    valid_count = max(1, int(np.count_nonzero(valid)))
    diff_ratio = float(np.count_nonzero(diff_mask)) / float(valid_count)
    masked_diff_values = diff_gray[valid > 0]
    color_diff = float(np.mean(np.asarray(masked_diff_values, dtype=np.float32))) if masked_diff_values.size else 0.0

    contour_ratio = 0.0
    edge_diff = 0.0
    contour_thickness = 0.0
    contour_min_dim = 0.0
    contour_max_dim = 0.0
    contour_fill = 0.0
    cnts, _ = cv2.findContours(diff_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        largest = max(cnts, key=cv2.contourArea)
        contour_ratio = float(cv2.contourArea(largest)) / float(max(1, diff_mask.size))
        x, y, bw, bh = cv2.boundingRect(largest)
        contour_thickness = float(min(bw, bh)) / float(max(1, max(bw, bh)))
        contour_min_dim = float(min(bw / max(1, diff_mask.shape[1]), bh / max(1, diff_mask.shape[0])))
        contour_max_dim = float(max(bw / max(1, diff_mask.shape[1]), bh / max(1, diff_mask.shape[0])))
        contour_fill = float(np.count_nonzero(diff_mask[y:y + bh, x:x + bw])) / float(max(1, bw * bh))
        if contour_thickness < args.visual_min_blob_thickness * 0.70:
            contour_ratio *= 0.55

    # Edge difference is diagnostic only. Decisions are based on area + contour + color,
    # so thin yellow slot lines and watermark strokes cannot win by themselves.
    e_now = cv2.Canny(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 70, 150)
    e_base = cv2.Canny(cv2.cvtColor(base_roi, cv2.COLOR_BGR2GRAY), 70, 150)
    e_diff = cv2.bitwise_and(cv2.absdiff(e_now, e_base), valid)
    edge_diff = float(np.count_nonzero(e_diff)) / float(valid_count)

    uniform_lighting_like = (
        diff_ratio >= args.baseline_uniform_diff_max
        and contour_ratio >= args.baseline_uniform_contour_max
        and edge_diff <= args.baseline_uniform_edge_max
    )
    baseline_diff_min_ratio = zone_override(slot_id, "baseline_diff_min_ratio", args.baseline_diff_min_ratio)
    baseline_contour_min_ratio = zone_override(slot_id, "baseline_contour_min_ratio", args.baseline_contour_min_ratio)
    baseline_color_diff_min = zone_override(slot_id, "baseline_color_diff_min", args.baseline_color_diff_min)
    baseline_fill_min = zone_override(slot_id, "baseline_fill_min", args.baseline_fill_min)
    baseline_thickness_min = zone_override(slot_id, "baseline_thickness_min", args.baseline_thickness_min)
    baseline_min_dim = zone_override(slot_id, "baseline_min_dim", args.baseline_min_dim)
    baseline_edge_min = zone_override(slot_id, "baseline_edge_min", args.baseline_edge_min)
    object_shape_ok = (
        contour_fill >= baseline_fill_min
        and contour_thickness >= baseline_thickness_min
        and contour_min_dim >= baseline_min_dim
    )
    strong = (
        diff_ratio >= baseline_diff_min_ratio
        and contour_ratio >= baseline_contour_min_ratio
        and color_diff >= baseline_color_diff_min
        and object_shape_ok
        and edge_diff >= baseline_edge_min
        and not uniform_lighting_like
    )
    score = (
        min(diff_ratio / max(1e-6, args.baseline_diff_ref), 1.0) * 0.46
        + min(contour_ratio / max(1e-6, args.baseline_contour_ref), 1.0) * 0.38
        + min(color_diff / max(1e-6, args.baseline_color_diff_ref), 1.0) * 0.16
    )
    if not strong:
        score = min(score, args.visual_weak_score_cap)

    return float(max(0.0, min(1.0, score))), {
        "present": 1.0,
        "diff_ratio": diff_ratio,
        "contour": contour_ratio,
        "color_diff": color_diff,
        "edge_diff": edge_diff,
        "fill": contour_fill,
        "thickness": contour_thickness,
        "min_dim": contour_min_dim,
        "max_dim": contour_max_dim,
        "uniform_lighting_like": 1.0 if uniform_lighting_like else 0.0,
        "object_shape_ok": 1.0 if object_shape_ok else 0.0,
        "strong": 1.0 if strong else 0.0,
    }

def classify_template_slots(
    frame: np.ndarray,
    board_det: BoardDetection,
    slots_template: list[dict],
    model_dets: list[dict],
    vehicle_dets: list[dict],
    stabilizer: SlotStabilizer,
    args,
    baseline_warped: Optional[np.ndarray] = None,
) -> list[SlotResult]:
    quad = board_det.quad.astype(np.float32)
    board_to_frame = cv2.getPerspectiveTransform(np.array([[0, 0], [CANON_W, 0], [CANON_W, CANON_H], [0, CANON_H]], np.float32), quad)
    frame_to_board = cv2.getPerspectiveTransform(quad, np.array([[0, 0], [CANON_W, 0], [CANON_W, CANON_H], [0, CANON_H]], np.float32))
    warped = cv2.warpPerspective(frame, frame_to_board, (CANON_W, CANON_H))

    occ_dets = [d for d in model_dets if d["label"] == "occupied"] + vehicle_dets
    empty_dets = [d for d in model_dets if d["label"] == "empty"]
    occ_canon = []
    empty_canon = []
    for d in occ_dets:
        try:
            occ_canon.append((frame_det_to_canon_box(d["box"], frame_to_board), float(d.get("conf", 0.5)), d.get("source", "occ")))
        except Exception:
            pass
    for d in empty_dets:
        try:
            empty_canon.append((frame_det_to_canon_box(d["box"], frame_to_board), float(d.get("conf", 0.5)), d.get("source", "empty")))
        except Exception:
            pass

    slot_cboxes = {int(s["id"]): normalized_box_to_canon(s["box"]) for s in slots_template}
    slot_match_cboxes = {
        sid: expand_canon_box(
            cbox,
            zone_override(sid, "match_expand_x", 0.0),
            zone_override(sid, "match_expand_y", 0.0),
        )
        for sid, cbox in slot_cboxes.items()
    }
    assigned_occ: dict[int, list[tuple[np.ndarray, float, str]]] = {sid: [] for sid in slot_cboxes}

    # Assign every occupied/vehicle detection to exactly one fixed slot. Without this,
    # a large or slightly shifted YOLO box can touch two neighboring top-row slots and
    # make both labels flip OCCUPIED. The assignment keeps slot IDs stable.
    for obox, conf, src in occ_canon:
        best_sid: Optional[int] = None
        best_score = -1.0
        for sid_eval, cbox_eval in slot_match_cboxes.items():
            iou = iou_xyxy(cbox_eval, obox)
            cov_slot = overlap_ratio(cbox_eval, obox)
            cov_obj = overlap_ratio(obox, cbox_eval)
            slot_area = max(1.0, float((cbox_eval[2] - cbox_eval[0]) * (cbox_eval[3] - cbox_eval[1])))
            obj_area = max(0.0, float((obox[2] - obox[0]) * (obox[3] - obox[1])))
            obj_slot_area = obj_area / slot_area
            cx, cy = (obox[0] + obox[2]) / 2.0, (obox[1] + obox[3]) / 2.0
            inside = cbox_eval[0] <= cx <= cbox_eval[2] and cbox_eval[1] <= cy <= cbox_eval[3]
            yolo_slot_iou = zone_override(sid_eval, "yolo_slot_iou", args.yolo_slot_iou)
            yolo_cover_slot = zone_override(sid_eval, "yolo_cover_slot", args.yolo_cover_slot)
            yolo_cover_obj = zone_override(sid_eval, "yolo_cover_obj", args.yolo_cover_obj)
            yolo_center_min_cover = zone_override(sid_eval, "yolo_center_min_cover", args.yolo_center_min_cover)
            yolo_min_slot_area = zone_override(sid_eval, "yolo_min_slot_area", args.yolo_min_slot_area)
            center_or_strong_cover = inside or cov_slot >= yolo_cover_slot
            if not (
                obj_slot_area >= yolo_min_slot_area
                and center_or_strong_cover
                and (
                    iou >= yolo_slot_iou
                    or cov_slot >= yolo_cover_slot
                    or cov_obj >= yolo_cover_obj
                    or (inside and cov_obj >= yolo_center_min_cover)
                )
            ):
                continue
            draw_box_eval = slot_cboxes[sid_eval]
            sx = (draw_box_eval[0] + draw_box_eval[2]) * 0.5
            sy = (draw_box_eval[1] + draw_box_eval[3]) * 0.5
            sw = max(1.0, draw_box_eval[2] - draw_box_eval[0])
            sh = max(1.0, draw_box_eval[3] - draw_box_eval[1])
            center_dist = abs(cx - sx) / sw + abs(cy - sy) / sh
            score = (
                float(iou) * 1.20
                + float(cov_slot) * 1.10
                + float(cov_obj) * 0.35
                + min(float(obj_slot_area), 1.0) * 0.15
                + (0.40 if inside else 0.0)
                - float(center_dist) * 0.08
            )
            if score > best_score:
                best_sid = sid_eval
                best_score = score
        if best_sid is not None:
            assigned_occ[best_sid].append((obox, conf, src))

    results: list[SlotResult] = []
    for s in slots_template:
        sid = int(s["id"])
        cbox = slot_cboxes[sid]
        match_cbox = slot_match_cboxes[sid]
        vscore, vst = visual_occupancy_score_warped(warped, cbox, args, slot_id=sid) if args.visual_occupancy else (0.0, {})
        bscore, bst = baseline_occupancy_score_warped(warped, baseline_warped, cbox, args, slot_id=sid)
        baseline_present = bool(bst.get("present", 0.0) > 0.5)
        baseline_strong = bool(bst.get("strong", 0.0) > 0.5)
        visual_car_blob_min = zone_override(sid, "visual_car_blob_min", args.visual_car_blob_min)
        visual_car_color_min = zone_override(sid, "visual_car_color_min", args.visual_car_color_min)
        visual_blob_ok = (
            float(vst.get("thick_blob", 0.0)) >= visual_car_blob_min
            and float(vst.get("color", 0.0)) >= visual_car_color_min
            and float(vst.get("uniform_board_like", 0.0)) < 0.5
        )
        visual_strong = bool(args.visual_occupancy and vscore >= args.visual_occ_min_score and visual_blob_ok)
        if baseline_present:
            raw = bscore if baseline_strong else min(vscore, args.visual_weak_score_cap)
            src_parts = ["baseline"] if baseline_strong else (["baseline-empty"] if bscore > 0.01 else [])
        else:
            raw = vscore if visual_strong else min(vscore, args.visual_weak_score_cap)
            src_parts = ["visual"] if visual_strong else (["visual-weak"] if args.visual_occupancy and vscore > 0.01 else [])

        best_yolo_score = 0.0
        best_yolo_overlap = 0.0
        best_yolo_area_ratio = 0.0
        best_yolo_direct = 0.0
        accepted_yolo_score = 0.0

        for obox, conf, src in assigned_occ.get(sid, []):
            iou = iou_xyxy(match_cbox, obox)
            cov_slot = overlap_ratio(match_cbox, obox)
            cov_obj = overlap_ratio(obox, match_cbox)
            overlap_score = max(float(iou), float(cov_slot), float(cov_obj))
            slot_area = max(1.0, float((match_cbox[2] - match_cbox[0]) * (match_cbox[3] - match_cbox[1])))
            obj_area = max(0.0, float((obox[2] - obox[0]) * (obox[3] - obox[1])))
            obj_slot_area = obj_area / slot_area
            cx, cy = (obox[0] + obox[2]) / 2.0, (obox[1] + obox[3]) / 2.0
            inside = match_cbox[0] <= cx <= match_cbox[2] and match_cbox[1] <= cy <= match_cbox[3]
            yolo_slot_iou = zone_override(sid, "yolo_slot_iou", args.yolo_slot_iou)
            yolo_cover_slot = zone_override(sid, "yolo_cover_slot", args.yolo_cover_slot)
            yolo_cover_obj = zone_override(sid, "yolo_cover_obj", args.yolo_cover_obj)
            yolo_center_min_cover = zone_override(sid, "yolo_center_min_cover", args.yolo_center_min_cover)
            yolo_min_slot_area = zone_override(sid, "yolo_min_slot_area", args.yolo_min_slot_area)
            center_or_strong_cover = inside or cov_slot >= yolo_cover_slot
            overlap_ok = (
                obj_slot_area >= yolo_min_slot_area
                and center_or_strong_cover
                and (
                    iou >= yolo_slot_iou
                    or cov_slot >= yolo_cover_slot
                    or cov_obj >= yolo_cover_obj
                    or (inside and cov_obj >= yolo_center_min_cover)
                )
            )
            if overlap_ok:
                best_yolo_score = max(best_yolo_score, float(conf))
                best_yolo_overlap = max(best_yolo_overlap, overlap_score)
                best_yolo_area_ratio = max(best_yolo_area_ratio, float(obj_slot_area))
                yolo_visual_ok = vscore >= zone_override(sid, "yolo_visual_min", args.yolo_visual_min)
                yolo_baseline_min = zone_override(sid, "yolo_baseline_min", args.yolo_baseline_min)
                yolo_baseline_ok = baseline_present and (baseline_strong or bscore >= yolo_baseline_min)
                direct_yolo_enabled = zone_override(
                    sid,
                    "direct_yolo_no_visual",
                    1.0 if args.allow_yolo_direct_no_visual else 0.0,
                ) > 0.5
                direct_yolo_conf = zone_override(sid, "direct_yolo_conf", args.occupied_direct_no_visual_conf)
                direct_yolo_cover_slot = zone_override(sid, "direct_yolo_cover_slot", yolo_cover_slot)
                direct_yolo_cover_obj = zone_override(sid, "direct_yolo_cover_obj", yolo_center_min_cover)
                direct_yolo_iou = zone_override(sid, "direct_yolo_iou", yolo_slot_iou)
                direct_yolo_min_slot_area = zone_override(sid, "direct_yolo_min_slot_area", yolo_min_slot_area)
                direct_center_or_cover = inside or cov_slot >= direct_yolo_cover_slot
                direct_geometry_ok = (
                    direct_center_or_cover
                    and obj_slot_area >= direct_yolo_min_slot_area
                    and (
                        cov_slot >= direct_yolo_cover_slot
                        or iou >= direct_yolo_iou
                        or (inside and cov_obj >= direct_yolo_cover_obj)
                    )
                )
                direct_no_visual_ok = bool(
                    direct_yolo_enabled
                    and conf >= direct_yolo_conf
                    and direct_geometry_ok
                )
                if args.yolo_require_visual and not (yolo_visual_ok or yolo_baseline_ok):
                    if not direct_no_visual_ok:
                        continue
                yolo_score = min(1.0, conf * args.yolo_occ_weight)
                if direct_no_visual_ok:
                    yolo_score = max(yolo_score, zone_override(sid, "direct_yolo_score", yolo_score))
                    best_yolo_direct = 1.0
                raw = max(raw, yolo_score)
                accepted_yolo_score = max(accepted_yolo_score, float(conf))
                src_parts.append(src)

        if zone_override(sid, "require_yolo_for_occ", 0.0) > 0.5 and accepted_yolo_score <= 0.0:
            allow_strong_visual = zone_override(sid, "allow_strong_visual_without_yolo", 0.0) > 0.5
            visual_no_yolo_min = zone_override(
                sid,
                "strong_visual_no_yolo_min_score",
                max(args.visual_occ_min_score, zone_override(sid, "occ_on", args.occ_on)),
            )
            baseline_no_yolo_min = zone_override(
                sid,
                "strong_baseline_no_yolo_min_score",
                zone_override(sid, "yolo_baseline_min", args.yolo_baseline_min),
            )
            strong_non_yolo_evidence = (
                (visual_strong and vscore >= visual_no_yolo_min)
                or (baseline_present and baseline_strong and bscore >= baseline_no_yolo_min)
            )
            if not (allow_strong_visual and strong_non_yolo_evidence):
                raw = min(raw, zone_override(sid, "no_yolo_score_cap", args.visual_weak_score_cap))

        # Empty model evidence can reduce a weak visual score, but it cannot move the fixed layout.
        for ebox, conf, src in empty_canon:
            iou = iou_xyxy(match_cbox, ebox)
            cov = overlap_ratio(match_cbox, ebox)
            if (iou >= args.empty_yolo_iou or cov >= args.empty_yolo_cover) and raw < args.empty_override_max_score:
                raw = min(raw, max(0.0, args.empty_override_score * (1.0 - conf * 0.35)))
                src_parts.append(src)

        raw_decision = "OCCUPIED" if raw >= zone_override(sid, "occ_on", args.occ_on) else "EMPTY"
        label, stable_score = stabilizer.update(sid, raw)
        poly_canon = canon_box_polygon(cbox).reshape(-1, 1, 2)
        poly_frame = cv2.perspectiveTransform(poly_canon, board_to_frame).reshape(-1, 2)
        x1, y1 = poly_frame[:, 0].min(), poly_frame[:, 1].min()
        x2, y2 = poly_frame[:, 0].max(), poly_frame[:, 1].max()
        debug = {
            "zone_id": float(sid),
            "yolo_score": float(best_yolo_score),
            "overlap": float(best_yolo_overlap),
            "yolo_area_ratio": float(best_yolo_area_ratio),
            "yolo_direct": float(best_yolo_direct),
            "baseline_diff_ratio": float(bst.get("diff_ratio", 0.0)),
            "baseline_contour_area": float(bst.get("contour", 0.0)),
            "baseline_color_diff": float(bst.get("color_diff", 0.0)),
            "baseline_edge_diff": float(bst.get("edge_diff", 0.0)),
            "baseline_fill": float(bst.get("fill", 0.0)),
            "baseline_thickness": float(bst.get("thickness", 0.0)),
            "baseline_uniform": float(bst.get("uniform_lighting_like", 0.0)),
            "visual_score": float(vscore),
            "visual_blob": float(vst.get("blob", 0.0)),
            "raw_decision": raw_decision,
            "stable_state": label.upper(),
        }
        if getattr(args, "debug_slots", False):
            print(
                f"[ZONE {sid}] "
                f"yolo={best_yolo_score:.2f} "
                f"overlap={best_yolo_overlap:.2f} "
                f"area={best_yolo_area_ratio:.2f} "
                f"direct={int(best_yolo_direct)} "
                f"diff={debug['baseline_diff_ratio']:.3f} "
                f"contour={debug['baseline_contour_area']:.3f} "
                f"edge={debug['baseline_edge_diff']:.3f} "
                f"fill={debug['baseline_fill']:.2f} "
                f"visual={vscore:.2f} "
                f"raw={raw_decision} "
                f"stable={label.upper()}"
            )
        results.append(SlotResult(
            id=sid,
            label=label,
            score=float(stable_score),
            raw_score=float(raw),
            polygon=poly_frame.astype(np.float32),
            box=np.array([x1, y1, x2, y2], dtype=np.float32),
            source="+".join(dict.fromkeys(src_parts)) or "template",
            debug=debug,
        ))
    return results



def clip_box_to_frame(box: np.ndarray, shape: tuple[int, int, int]) -> tuple[np.ndarray, float]:
    h, w = shape[:2]
    x1, y1, x2, y2 = map(float, box.tolist())
    raw_area = max(1.0, (x2 - x1) * (y2 - y1))
    cx1, cy1 = max(0.0, min(w - 1.0, x1)), max(0.0, min(h - 1.0, y1))
    cx2, cy2 = max(0.0, min(w - 1.0, x2)), max(0.0, min(h - 1.0, y2))
    if cx2 <= cx1 or cy2 <= cy1:
        return np.array([0, 0, 0, 0], dtype=np.float32), 0.0
    clipped = np.array([cx1, cy1, cx2, cy2], dtype=np.float32)
    return clipped, float(((cx2 - cx1) * (cy2 - cy1)) / raw_area)


def parking_dets_to_slot_results(dets: list[dict], frame_shape: tuple[int, int, int], args: argparse.Namespace) -> list[SlotResult]:
    """Draw trained YOLO empty/occupied slot boxes directly when no toy board is present."""
    h, w = frame_shape[:2]
    out: list[SlotResult] = []
    filtered: list[dict] = []
    for d in dets:
        box, visible = clip_box_to_frame(d["box"], frame_shape)
        if visible < args.global_min_visible_ratio:
            continue
        x1, y1, x2, y2 = map(float, box.tolist())
        bw, bh = x2 - x1, y2 - y1
        area = bw * bh / float(max(1, h * w))
        if area < args.global_min_area or area > args.global_max_area:
            continue
        nd = dict(d)
        nd["box"] = box
        if not det_in_regions(nd, frame_shape, args):
            continue
        filtered.append(nd)

    filtered = sorted(filtered, key=lambda d: (float(d["box"][1]), float(d["box"][0])))
    for idx, d in enumerate(filtered, start=1):
        x1, y1, x2, y2 = map(float, d["box"].tolist())
        poly = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)
        out.append(SlotResult(
            id=idx,
            label=str(d.get("label", "occupied")),
            score=float(d.get("conf", 0.0)),
            raw_score=float(d.get("conf", 0.0)),
            polygon=poly,
            box=d["box"].astype(np.float32),
            source=str(d.get("source", "parking-yolo")),
        ))
    return out


def classify_region_slots(dets: list[dict], frame_shape: tuple[int, int, int], args: argparse.Namespace) -> list[SlotResult]:
    regions = getattr(args, "_regions", None) or {"slots": []}
    slots = regions.get("slots", [])
    if not slots:
        return []

    results: list[SlotResult] = []
    filtered = [d for d in dets if det_in_regions(d, frame_shape, args)]
    for idx, item in enumerate(slots, start=1):
        poly = _region_to_polygon(item.get("region"), frame_shape)
        if poly is None:
            continue
        x1, y1 = float(poly[:, 0].min()), float(poly[:, 1].min())
        x2, y2 = float(poly[:, 0].max()), float(poly[:, 1].max())
        slot_box = np.array([x1, y1, x2, y2], dtype=np.float32)
        best_occ = 0.0
        best_empty = 0.0
        for d in filtered:
            det_box = d["box"].astype(np.float32)
            iou = iou_xyxy(slot_box, det_box)
            cov_slot = overlap_ratio(slot_box, det_box)
            cov_obj = overlap_ratio(det_box, slot_box)
            dx1, dy1, dx2, dy2 = map(float, det_box.tolist())
            center_inside = point_in_polygon_xy(((dx1 + dx2) * 0.5, (dy1 + dy2) * 0.5), poly)
            overlap_ok = iou >= args.outdoor_slot_iou or cov_slot >= args.outdoor_cover_slot or cov_obj >= args.outdoor_cover_obj or center_inside
            if not overlap_ok:
                continue
            conf = float(d.get("conf", 0.0))
            if d.get("label") == "occupied":
                best_occ = max(best_occ, conf)
            elif d.get("label") == "empty":
                best_empty = max(best_empty, conf)
        label = "occupied" if best_occ >= max(args.occupied_conf, best_empty + args.outdoor_occ_margin) else "empty"
        score = best_occ if label == "occupied" else max(best_empty, 1.0 - best_occ)
        results.append(SlotResult(
            id=int(item.get("id", idx)),
            label=label,
            score=float(score),
            raw_score=float(score),
            polygon=poly.astype(np.float32),
            box=slot_box,
            source="regions+parking-yolo",
        ))
    return results


def draw_board_status(frame: np.ndarray, board: Optional[BoardDetection], args: argparse.Namespace) -> None:
    if board is None:
        if args.show_board_status:
            h, w = frame.shape[:2]
            cv2.putText(frame, "BOARD LOST - hide slots", (max(20, int(w * 0.36)), 45), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 80, 255), 2, cv2.LINE_AA)
        return
    if args.show_board:
        q = board.quad.astype(np.int32)
        cv2.polylines(frame, [q], True, (255, 0, 255), 2, cv2.LINE_AA)
        if args.show_board_status:
            cv2.putText(frame, f"BOARD LOCK {board.confidence:.2f}", tuple(q[0].tolist()), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 255), 2, cv2.LINE_AA)


def draw_slot_results(frame: np.ndarray, results: list[SlotResult], args: argparse.Namespace) -> Counter:
    counts = Counter()
    for r in results:
        counts[r.label] += 1
        color = (0, 255, 0) if r.label == "empty" else (0, 165, 255)
        poly = r.polygon.astype(np.int32)
        cv2.polylines(frame, [poly], True, color, 3 if r.label == "occupied" else 2, cv2.LINE_AA)
        if args.show_labels:
            tag = f"{r.label.upper()} {r.id}"
            if args.show_conf:
                tag += f" {r.score:.2f}/{r.raw_score:.2f}"
            if args.show_source:
                tag += f" {r.source[:14]}"

            x1f, y1f, x2f, y2f = map(float, r.box.tolist())
            box_w = max(24.0, x2f - x1f)
            box_h = max(18.0, y2f - y1f)
            scale = float(args.label_scale)
            (tw, th), baseline = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
            pad_x, pad_y = 8, 6
            max_text_w = max(20.0, box_w - pad_x * 2)
            max_text_h = max(12.0, box_h - pad_y * 2)
            if tw > max_text_w or (th + baseline) > max_text_h:
                scale_w = max_text_w / max(1.0, tw)
                scale_h = max_text_h / max(1.0, th + baseline)
                scale = max(0.30, scale * min(scale_w, scale_h, 1.0))
                (tw, th), baseline = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
            cx = (x1f + x2f) * 0.5
            cy = (y1f + y2f) * 0.5
            tx = int(round(cx - tw * 0.5))
            ty = int(round(cy + th * 0.5))
            min_tx = int(round(x1f + 2 + pad_x))
            max_tx = int(round(x2f - 2 - tw - pad_x))
            min_ty = int(round(y1f + 2 + th + pad_y))
            max_ty = int(round(y2f - baseline - pad_y))
            if max_tx >= min_tx:
                tx = max(min_tx, min(max_tx, tx))
            if max_ty >= min_ty:
                ty = max(min_ty, min(max_ty, ty))
            tx = max(6, min(frame.shape[1] - tw - pad_x * 2 - 6, tx))
            ty = max(th + pad_y * 2 + 2, min(frame.shape[0] - baseline - pad_y - 2, ty))

            x1 = max(0, tx - pad_x)
            y1 = max(0, ty - th - pad_y)
            x2 = min(frame.shape[1] - 1, tx + tw + pad_x)
            y2 = min(frame.shape[0] - 1, ty + baseline + pad_y - 2)
            overlay = frame.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (10, 10, 10), -1)
            cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)
            cv2.putText(frame, tag, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)
    return counts


def draw_hud(frame: np.ndarray, counts: Counter, fps: float, mode_text: str, board_visible: bool, board_conf: float, total_override: Optional[int] = None) -> None:
    empty = counts.get("empty", 0)
    occupied = counts.get("occupied", 0)
    total = int(total_override) if total_override is not None else empty + occupied
    if mode_text == "boardlock" and not board_visible:
        empty, occupied, total = 0, 0, 0
    overlay = frame.copy()
    cv2.rectangle(overlay, (12, 38), (430, 190), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)
    cv2.rectangle(frame, (12, 38), (430, 190), (90, 90, 90), 1, cv2.LINE_AA)
    status = "LOCK" if board_visible else "NO-BOARD"
    if mode_text == "boardlock" and not board_visible:
        cv2.putText(frame, "NO_BOARD", (30, 94), cv2.FONT_HERSHEY_SIMPLEX, 1.05, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, "No slot drawing / no fake count", (30, 136), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (220, 220, 220), 1, cv2.LINE_AA)
    else:
        cv2.putText(frame, f"Empty:    {empty}", (30, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.95, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(frame, f"Occupied: {occupied}", (30, 124), cv2.FONT_HERSHEY_SIMPLEX, 0.95, (0, 165, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"Total:    {total}", (30, 164), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, f"FPS {fps:.1f} | {mode_text} | {status} {board_conf:.2f} | slots {total}", (168, 182), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)


def save_board_cache(path: Path, board: BoardDetection, slots_template: list[dict]) -> None:
    data = {
        "version": 14,
        "note": "Last live 9-zone board quadrilateral. Runtime validates this cache and never draws stale zones when board is lost.",
        "quad": [[round(float(x), 2), round(float(y), 2)] for x, y in board.quad.tolist()],
        "confidence": round(float(board.confidence), 3),
        "area_ratio": round(float(board.area_ratio), 4),
        "mark_ratio": round(float(board.mark_ratio), 4),
        "canonical_size": [CANON_W, CANON_H],
        "slots_template": slots_template,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_models(args: argparse.Namespace) -> tuple[Optional[YOLOModelProtocol], Optional[YOLOModelProtocol]]:
    parking_model: Optional[YOLOModelProtocol] = None
    vehicle_model: Optional[YOLOModelProtocol] = None

    fac = _yolo_factory
    if fac is None:
        print("[WARN] ultralytics is not installed. Running visual-only mode; install ultralytics to enable YOLO.")
        return None, None

    if not args.no_parking_model:
        model_text = str(args.model).strip().lower()
        if model_text in {"", "auto"}:
            candidates = [
                TRAINED_MODEL,
                ROOT / "runs" / "train" / "parking_v8s_e15" / "weights" / "best.pt",
                LEGACY_MODEL,
                ROOT / "models" / "best.pt",
                ROOT / "runs" / "train" / "parking_v8s_5epoch" / "weights" / "best.pt",
            ]
            model_path = next((c for c in candidates if c.exists()), None)
        else:
            model_path = resolve_path(args.model)
        if model_path is not None and Path(model_path).exists():
            print(f"[INFO] Loading trained parking model: {model_path}")
            parking_model = fac(str(model_path))
        else:
            print("[WARN] Chua thay models/parking_v8s_e15_best.pt nen YOLO parking chua chay. Chay TRAIN_V8S_5EPOCH_GPU.py truoc.")

    if not args.no_vehicle:
        vpath = resolve_path(args.vehicle_model)
        try:
            if vpath.exists():
                print(f"[INFO] Loading vehicle model: {vpath}")
                vehicle_model = fac(str(vpath))
            else:
                print(f"[INFO] Loading vehicle model by name: {args.vehicle_model}")
                vehicle_model = fac(str(args.vehicle_model))
        except Exception as e:
            print(f"[WARN] Could not load vehicle model ({e}). Continuing with visual heuristic.")
            vehicle_model = None
    return parking_model, vehicle_model


def run(args: argparse.Namespace) -> None:
    args.device = choose_device(args.device)
    crop_ratio = parse_crop_ratio(args.crop_ratio)
    template_path = resolve_path(args.template)
    try:
        slots_template = load_slots_template(template_path, create_if_missing=False)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        print("[ERROR] Boardlock 9-zone mode requires parkingvision_slots_template_9zones.json; no non-canonical template will be used.")
        return
    if args.mode == "boardlock" and len(slots_template) != 9:
        print(f"[WARN] Boardlock template has {len(slots_template)} zones; expected 9. Check {template_path}")

    board_cache_load_path, board_cache_path = resolve_board_cache_paths(args)
    if args.reset_board_cache:
        for pth in {board_cache_load_path, board_cache_path}:
            if pth.exists():
                pth.unlink()
                print(f"[DEL] reset board cache: {pth}")
        board_cache_load_path = board_cache_path
    cached_board_quad = load_board_cache_quad(board_cache_load_path) if args.use_board_cache else None
    if cached_board_quad is not None:
        print(f"[INFO] Loaded board lock cache: {board_cache_load_path.name}")

    baseline_path = resolve_path(args.empty_baseline)
    baseline_warped = None
    if args.mode == "boardlock" and not args.capture_empty_baseline:
        baseline_warped = load_empty_baseline(baseline_path)
        if baseline_warped is not None:
            print(f"[INFO] Loaded empty baseline: {baseline_path.name}")
        else:
            print("[WARN] No empty baseline found. Run --capture-empty-baseline for best accuracy.")

    regions_path = resolve_path(args.regions)
    args._regions = load_regions(regions_path)
    if regions_path.exists():
        print(f"[INFO] Loaded regions: {len(args._regions.get('rois', []))} roi(s), {len(args._regions.get('slots', []))} slot(s)")

    parking_model, vehicle_model = (None, None) if args.capture_empty_baseline else load_models(args)

    source = parse_source(args.source)
    cap = open_capture(source, args.cam_width, args.cam_height, args.cam_fps)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open DroidCam/source: {source}")
        return

    tracker = BoardTracker(args)
    stabilizer = SlotStabilizer([s["id"] for s in slots_template], args)

    print(f"[INFO] mode={args.mode} | device={args.device} | template={template_path.name} | fixed zones={len(slots_template)} | crop={args.crop_ratio or 'none'}")
    if args.capture_empty_baseline:
        print(f"[INFO] Capture mode: wait for visible board, then save {baseline_path.name} and exit.")
    print("[OK] Running V8S BoardLock FINAL. Press Q to quit, R to relock board.")

    window_name = "Parking Vision V8S STRICT Occupancy FIX"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    last_results: list[SlotResult] = []
    last_results_frame_id: Optional[int] = None
    last_board: Optional[BoardDetection] = None
    frame_id = 0
    fps = 0.0
    t_last = time.time()
    last_cache_save = 0.0

    try:
        while not STOP_REQUESTED:
            ok, frame = cap.read()
            if not ok or frame is None or frame.size == 0:
                blank = np.zeros((480, 720, 3), np.uint8)
                cv2.putText(blank, "Waiting for DroidCam frame...", (35, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.imshow(window_name, blank)
                key = cv2.waitKey(30) & 0xFF
                if key == ord("q"):
                    break
                continue

            frame = rotate_frame(frame, args.rotate)
            if args.flip:
                frame = cv2.flip(frame, 1)
            display = frame.copy()
            crop, ox, oy = apply_crop_ratio(frame, crop_ratio)

            now = time.time()
            dt = max(1e-6, now - t_last)
            fps = fps * 0.90 + (1.0 / dt) * 0.10 if fps else 1.0 / dt
            t_last = now
            frame_id += 1

            if frame_id % max(1, args.process_every) == 0:
                offset = np.array([ox, oy], dtype=np.float32)
                box_offset = np.array([ox, oy, ox, oy], dtype=np.float32)

                if args.mode == "outdoor":
                    last_board = None
                    if (parking_model is not None or (not args.no_vehicle and vehicle_model is not None)) and should_run_inference(frame_id, args.yolo_every):
                        model_dets = detect_with_parking_model(parking_model, crop, args)
                        vehicle_dets = [] if args.no_vehicle else detect_vehicles(vehicle_model, crop, args)
                        all_dets = model_dets + vehicle_dets
                        if args._regions.get("slots"):
                            local_results = classify_region_slots(all_dets, crop.shape, args) # type: ignore
                        else:
                            local_results = parking_dets_to_slot_results(all_dets, crop.shape, args) # pyright: ignore[reportArgumentType]
                        last_results = [SlotResult(
                            id=r.id,
                            label=r.label,
                            score=r.score,
                            raw_score=r.raw_score,
                            polygon=r.polygon + offset,
                            box=r.box + box_offset,
                            source=r.source,
                        ) for r in local_results]
                        last_results_frame_id = frame_id
                    else:
                        last_results = []
                        last_results_frame_id = None
                else:
                    raw_board = detect_board_quad(crop, args)
                    if raw_board is None and cached_board_quad is not None and args.use_board_cache:
                        cache_local = cached_board_quad - offset
                        raw_board = validate_board_quad(crop, cache_local, args, source="board-cache")
                    elif raw_board is not None and cached_board_quad is not None and args.use_board_cache and args.strict_board_cache:
                        cache_local = cached_board_quad - offset
                        delta = quad_delta_ratio(raw_board.quad, cache_local)
                        if delta > args.board_cache_max_delta:
                            raw_board = validate_board_quad(crop, cache_local, args, source="board-cache")

                    locked_board = tracker.update(raw_board)
                    if locked_board is not None:
                        board_for_full = BoardDetection(
                            quad=locked_board.quad + offset,
                            confidence=locked_board.confidence,
                            area_ratio=locked_board.area_ratio,
                            mark_ratio=locked_board.mark_ratio,
                            source=locked_board.source,
                        )
                        if args.capture_empty_baseline:
                            warped_empty = warp_board_to_canon(crop, locked_board)
                            save_empty_baseline(baseline_path, warped_empty)
                            save_board_cache(board_cache_path, board_for_full, slots_template)
                            break
                        if should_run_inference(frame_id, args.yolo_every):
                            model_dets = detect_with_parking_model(parking_model, crop, args)
                            vehicle_dets = [] if args.no_vehicle else detect_vehicles(vehicle_model, crop, args)
                            local_results = classify_template_slots(crop, locked_board, slots_template, model_dets, vehicle_dets, stabilizer, args, baseline_warped=baseline_warped)
                            last_results = [SlotResult(
                                id=r.id,
                                label=r.label,
                                score=r.score,
                                raw_score=r.raw_score,
                                polygon=r.polygon + offset,
                                box=r.box + box_offset,
                                source=r.source,
                            ) for r in local_results]
                            last_results_frame_id = frame_id
                        last_board = board_for_full
                        if now - last_cache_save > args.cache_save_interval:
                            save_board_cache(board_cache_path, board_for_full, slots_template)
                            cached_board_quad = board_for_full.quad.copy()
                            last_cache_save = now
                    else:
                        last_board = None
                        last_results = []
                        last_results_frame_id = None
                        if tracker.missed > args.board_reset_after:
                            stabilizer.reset()

            draw_board_status(display, last_board, args)
            counts = draw_slot_results(display, results_for_frame(last_results, last_results_frame_id, frame_id, args.yolo_every), args)
            total_override = len(slots_template) if args.mode == "boardlock" and last_board is not None else (len(args._regions.get("slots", [])) or None)
            draw_hud(display, counts, fps, args.mode, last_board is not None, last_board.confidence if last_board else 0.0, total_override=total_override)
            if args.show_crop and crop_ratio is not None:
                ch, cw = crop.shape[:2]
                cv2.rectangle(display, (ox, oy), (ox + cw, oy + ch), (255, 255, 0), 2)

            cv2.imshow(window_name, display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                tracker.reset()
                stabilizer.reset()
                last_results = []
                last_results_frame_id = None
                last_board = None
                print("[OK] Reset board lock + slot smoothing.")
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if _torch_module is not None:
            try:
                _torch_module.cuda.empty_cache()
            except Exception:
                pass
        print("[OK] Stopped cleanly.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Parking Vision V8S STRICT Occupancy FIX fixed-template runner")
    p.add_argument("--source", type=str, default="1")
    p.add_argument("--mode", type=str, choices=["boardlock", "outdoor"], default="boardlock")
    p.add_argument("--model", type=str, default="auto")
    p.add_argument("--vehicle-model", type=str, default=str(FALLBACK_MODEL))
    p.add_argument("--device", type=str, default="auto")
    p.add_argument("--cam-width", type=int, default=1280)
    p.add_argument("--cam-height", type=int, default=720)
    p.add_argument("--cam-fps", type=int, default=30)
    p.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270])
    p.add_argument("--flip", action="store_true")
    p.add_argument("--crop-ratio", type=str, default="")
    p.add_argument("--show-crop", action="store_true")

    p.add_argument("--template", type=str, default=str(DEFAULT_TEMPLATE))
    p.add_argument("--board-cache", type=str, default=str(DEFAULT_BOARD_CACHE))
    p.add_argument("--empty-baseline", type=str, default=str(DEFAULT_EMPTY_BASELINE))
    p.add_argument("--capture-empty-baseline", action="store_true")
    p.add_argument("--regions", type=str, default=str(DEFAULT_REGIONS))
    p.add_argument("--reset-board-cache", action="store_true")
    p.add_argument("--use-board-cache", action="store_true", default=True)
    p.add_argument("--no-board-cache", action="store_false", dest="use_board_cache")
    p.add_argument("--strict-board-cache", action="store_true", default=False)
    p.add_argument("--board-cache-max-delta", type=float, default=0.45)
    p.add_argument("--board-cache-max-area", type=float, default=0.92)
    p.add_argument("--board-cache-max-outside-margin", type=float, default=0.015)
    p.add_argument("--cache-save-interval", type=float, default=2.5)

    # Board detector / lock settings
    p.add_argument("--board-min-conf", type=float, default=BOARD_CONF_THRES)
    p.add_argument("--board-warmup-frames", type=int, default=BOARD_VISIBLE_CONFIRM_FRAMES)
    p.add_argument("--board-max-missed", type=int, default=2)
    p.add_argument("--board-reset-after", type=int, default=BOARD_LOST_CONFIRM_FRAMES)
    p.add_argument("--board-smooth-alpha", type=float, default=0.12)
    p.add_argument("--board-locked-smooth-alpha", type=float, default=0.012)
    p.add_argument("--board-locked-deadband", type=float, default=0.024)
    p.add_argument("--board-max-jump", type=float, default=0.28)
    p.add_argument("--board-connect-kernel", type=int, default=31)
    p.add_argument("--board-dilate-iter", type=int, default=2)
    p.add_argument("--board-min-component-area", type=float, default=0.010)
    p.add_argument("--board-min-width", type=float, default=0.35)
    p.add_argument("--board-min-height", type=float, default=0.22)
    p.add_argument("--board-min-pixels", type=int, default=900)
    p.add_argument("--board-min-area", type=float, default=0.15)
    p.add_argument("--board-max-area", type=float, default=0.98)
    p.add_argument("--board-min-aspect", type=float, default=1.10)
    p.add_argument("--board-max-aspect", type=float, default=3.20)
    p.add_argument("--board-max-outside-margin", type=float, default=0.08)
    p.add_argument("--board-expand-x", type=float, default=1.045)
    p.add_argument("--board-expand-y", type=float, default=1.055)
    p.add_argument("--board-expected-mark-ratio", type=float, default=0.060)
    p.add_argument("--board-min-mark-ratio", type=float, default=0.018)
    p.add_argument("--red-strip-board", action="store_true", default=True)
    p.add_argument("--no-red-strip-board", action="store_false", dest="red_strip_board")
    p.add_argument("--red-strip-ignore-top", type=float, default=0.04)
    p.add_argument("--red-strip-ignore-left", type=float, default=0.00)
    p.add_argument("--red-strip-kernel", type=int, default=17)
    p.add_argument("--red-strip-min-area", type=float, default=0.010)
    p.add_argument("--red-strip-min-center-y", type=float, default=0.45)
    p.add_argument("--red-strip-min-aspect", type=float, default=3.2)
    p.add_argument("--red-strip-min-width", type=float, default=0.42)
    p.add_argument("--red-strip-min-height", type=float, default=0.05)
    p.add_argument("--red-strip-max-height", type=float, default=0.45)
    p.add_argument("--board-red-up-factor", type=float, default=4.0)
    p.add_argument("--board-red-min-up-factor", type=float, default=2.6)
    p.add_argument("--board-red-top-margin", type=float, default=0.075)
    p.add_argument("--board-red-expand-x", type=float, default=1.01)
    p.add_argument("--board-red-expand-y", type=float, default=1.01)
    p.add_argument("--red-strip-axis-board", action="store_true", default=True)
    p.add_argument("--no-red-strip-axis-board", action="store_false", dest="red_strip_axis_board")
    p.add_argument("--board-red-axis-h-factor", type=float, default=4.0)
    p.add_argument("--board-red-axis-aspect", type=float, default=1.65)
    p.add_argument("--ignore-hud-area", action="store_true", default=False)

    # Color threshold settings for board detection
    p.add_argument("--yellow-h-min", type=int, default=12)
    p.add_argument("--yellow-h-max", type=int, default=48)
    p.add_argument("--yellow-s-min", type=int, default=40)
    p.add_argument("--yellow-v-min", type=int, default=45)
    p.add_argument("--red-s-min", type=int, default=45)
    p.add_argument("--red-v-min", type=int, default=35)
    p.add_argument("--white-v-min", type=int, default=150)
    p.add_argument("--white-s-max", type=int, default=90)

    # Occupancy visual heuristic and hysteresis
    p.add_argument("--visual-occupancy", action="store_true", default=True)
    p.add_argument("--no-visual-occupancy", action="store_false", dest="visual_occupancy")
    p.add_argument("--visual-sat-min", type=int, default=58)
    p.add_argument("--visual-val-min", type=int, default=45)
    p.add_argument("--visual-bright-min", type=int, default=72)
    p.add_argument("--visual-bright-sat-min", type=int, default=28)
    p.add_argument("--visual-white-sat-max", type=int, default=85)
    p.add_argument("--visual-white-val-min", type=int, default=145)
    p.add_argument("--visual-inner-crop", type=float, default=0.18)
    p.add_argument("--visual-edge-crop-x", type=float, default=0.10)
    p.add_argument("--visual-edge-crop-y", type=float, default=0.12)
    p.add_argument("--visual-min-blob-thickness", type=float, default=0.28)
    p.add_argument("--visual-line-noise-floor", type=float, default=0.04)
    p.add_argument("--visual-color-weight", type=float, default=0.30)
    p.add_argument("--visual-blob-weight", type=float, default=0.62)
    p.add_argument("--visual-edge-weight", type=float, default=VISUAL_EDGE_THRES)
    p.add_argument("--visual-std-weight", type=float, default=0.08)
    p.add_argument("--visual-mean-weight", type=float, default=0.00)
    p.add_argument("--visual-blob-ref", type=float, default=0.13)
    p.add_argument("--visual-edge-ref", type=float, default=0.18)
    p.add_argument("--visual-dark-mean", type=float, default=42.0)
    p.add_argument("--visual-dark-std", type=float, default=22.0)
    p.add_argument("--visual-dark-color", type=float, default=0.035)
    p.add_argument("--visual-color-ref", type=float, default=0.18)
    p.add_argument("--visual-car-blob-min", type=float, default=VISUAL_CONTOUR_THRES)
    p.add_argument("--visual-car-color-min", type=float, default=VISUAL_AREA_THRES)
    p.add_argument("--visual-car-min-dim", type=float, default=0.17)
    p.add_argument("--visual-car-max-dim", type=float, default=0.28)
    p.add_argument("--visual-occ-min-score", type=float, default=0.50)
    p.add_argument("--visual-weak-score-cap", type=float, default=0.18)
    p.add_argument("--visual-max-uniform-color-ratio", type=float, default=VISUAL_MAX_UNIFORM_COLOR_RATIO)
    p.add_argument("--visual-uniform-max-std", type=float, default=VISUAL_UNIFORM_MAX_STD)
    p.add_argument("--allow-white-vehicle", action="store_true", default=False)
    p.add_argument("--visual-remove-red-markings", action="store_true", default=False)
    p.add_argument("--board-line-yellow-h-min", type=int, default=12)
    p.add_argument("--board-line-yellow-h-max", type=int, default=65)
    p.add_argument("--board-line-red-h-max1", type=int, default=12)
    p.add_argument("--board-line-red-h-min2", type=int, default=168)
    p.add_argument("--board-line-s-min", type=int, default=30)
    p.add_argument("--board-line-v-min", type=int, default=35)
    p.add_argument("--board-line-white-s-max", type=int, default=95)
    p.add_argument("--board-line-white-v-min", type=int, default=130)
    p.add_argument("--visual-color-min-component-area", type=float, default=0.045)
    p.add_argument("--visual-color-min-thickness", type=float, default=0.28)
    p.add_argument("--visual-color-min-dim-ratio", type=float, default=0.15)
    p.add_argument("--visual-color-min-long-ratio", type=float, default=0.25)
    p.add_argument("--visual-white-min-component-area", type=float, default=0.070)
    p.add_argument("--visual-white-min-thickness", type=float, default=0.18)
    p.add_argument("--visual-white-min-dim-ratio", type=float, default=0.12)
    p.add_argument("--visual-white-min-long-ratio", type=float, default=0.28)

    # Empty-board baseline difference. This is the main false-positive guard:
    # empty slots must look different from the captured empty board before visual evidence can win.
    p.add_argument("--baseline-diff-threshold", type=int, default=BASELINE_DIFF_THRES)
    p.add_argument("--baseline-diff-min-ratio", type=float, default=BASELINE_DIFF_RATIO_THRES)
    p.add_argument("--baseline-contour-min-ratio", type=float, default=BASELINE_CONTOUR_RATIO_THRES)
    p.add_argument("--baseline-color-diff-min", type=float, default=BASELINE_COLOR_DIFF_THRES)
    p.add_argument("--baseline-fill-min", type=float, default=0.18)
    p.add_argument("--baseline-thickness-min", type=float, default=0.24)
    p.add_argument("--baseline-min-dim", type=float, default=0.14)
    p.add_argument("--baseline-edge-min", type=float, default=0.012)
    p.add_argument("--baseline-diff-ref", type=float, default=0.18)
    p.add_argument("--baseline-contour-ref", type=float, default=0.10)
    p.add_argument("--baseline-color-diff-ref", type=float, default=45.0)
    p.add_argument("--baseline-uniform-diff-max", type=float, default=BASELINE_UNIFORM_DIFF_MAX)
    p.add_argument("--baseline-uniform-contour-max", type=float, default=BASELINE_UNIFORM_CONTOUR_MAX)
    p.add_argument("--baseline-uniform-edge-max", type=float, default=BASELINE_UNIFORM_EDGE_MAX)
    p.add_argument("--yolo-baseline-min", type=float, default=0.46)

    p.add_argument("--smooth-alpha", type=float, default=0.40)
    p.add_argument("--occ-on", type=float, default=0.58)
    p.add_argument("--empty-off", type=float, default=0.24)
    p.add_argument("--occ-confirm-frames", type=int, default=OCCUPIED_CONFIRM_FRAMES)
    p.add_argument("--empty-confirm-frames", type=int, default=EMPTY_CONFIRM_FRAMES)

    # YOLO evidence is optional only. Default is visual-only because the old slot YOLO
    # hallucinated Occupied on empty toy slots. Truly, a machine saw a line and called it a car.
    p.set_defaults(no_parking_model=False)
    p.add_argument("--use-parking-model", action="store_false", dest="no_parking_model")
    p.add_argument("--no-parking-model", action="store_true", dest="no_parking_model")
    p.add_argument("--no-vehicle", action="store_true", default=False)
    p.add_argument("--use-vehicle", action="store_false", dest="no_vehicle")
    p.add_argument("--enhance", action="store_true")
    p.add_argument("--tta", action="store_true")
    p.add_argument("--yolo-every", type=int, default=1)
    p.add_argument("--model-conf", type=float, default=0.16)
    p.add_argument("--empty-conf", type=float, default=0.18)
    p.add_argument("--occupied-conf", type=float, default=YOLO_CONF_THRES)
    p.add_argument("--occupied-direct-conf", type=float, default=0.70)
    p.add_argument("--occupied-direct-no-visual-conf", type=float, default=0.82)
    p.add_argument("--model-imgsz", type=int, default=960)
    p.add_argument("--model-iou", type=float, default=0.42)
    p.add_argument("--model-max-det", type=int, default=80)
    p.add_argument("--det-post-iou", type=float, default=0.22)
    p.add_argument("--det-min-area", type=float, default=0.00005)
    p.add_argument("--det-max-area", type=float, default=0.40)
    p.add_argument("--vehicle-conf", type=float, default=0.20)
    p.add_argument("--vehicle-imgsz", type=int, default=960)
    p.add_argument("--vehicle-iou", type=float, default=0.42)
    p.add_argument("--vehicle-max-det", type=int, default=60)
    p.add_argument("--vehicle-min-area", type=float, default=0.00008)
    p.add_argument("--vehicle-max-area", type=float, default=0.22)
    p.add_argument("--vehicle-min-aspect", type=float, default=0.18)
    p.add_argument("--vehicle-max-aspect", type=float, default=6.8)
    p.add_argument("--yolo-slot-iou", type=float, default=0.10)
    p.add_argument("--yolo-cover-slot", type=float, default=YOLO_OVERLAP_THRES)
    p.add_argument("--yolo-cover-obj", type=float, default=0.35)
    p.add_argument("--yolo-center-min-cover", type=float, default=0.12)
    p.add_argument("--yolo-min-slot-area", type=float, default=0.08)
    p.add_argument("--yolo-occ-weight", type=float, default=1.0)
    p.add_argument("--yolo-require-visual", action="store_true", default=True)
    p.add_argument("--no-yolo-require-visual", action="store_false", dest="yolo_require_visual")
    p.add_argument("--allow-yolo-direct-no-visual", action="store_true", default=False)
    p.add_argument("--yolo-visual-min", type=float, default=0.34)
    p.add_argument("--empty-yolo-iou", type=float, default=0.26)
    p.add_argument("--empty-yolo-cover", type=float, default=0.45)
    p.add_argument("--empty-override-max-score", type=float, default=0.42)
    p.add_argument("--empty-override-score", type=float, default=0.12)

    p.add_argument("--global-yolo-fallback", action="store_true", default=False)
    p.add_argument("--no-global-yolo-fallback", action="store_false", dest="global_yolo_fallback")
    p.add_argument("--global-min-visible-ratio", type=float, default=0.96)
    p.add_argument("--global-min-area", type=float, default=0.00025)
    p.add_argument("--global-max-area", type=float, default=0.18)
    p.add_argument("--parking-roi", type=str, default="")
    p.add_argument("--outdoor-slot-iou", type=float, default=0.10)
    p.add_argument("--outdoor-cover-slot", type=float, default=0.18)
    p.add_argument("--outdoor-cover-obj", type=float, default=0.35)
    p.add_argument("--outdoor-occ-margin", type=float, default=0.05)

    p.add_argument("--process-every", type=int, default=1)
    p.add_argument("--show-labels", action="store_true", default=True)
    p.add_argument("--show-conf", action="store_true")
    p.add_argument("--show-source", action="store_true")
    p.add_argument("--show-board", action="store_true", default=False)
    p.add_argument("--hide-board", action="store_false", dest="show_board")
    p.add_argument("--show-board-status", action="store_true", default=False)
    p.add_argument("--debug-slots", action="store_true")
    p.add_argument("--label-scale", type=float, default=0.70)
    return p


if __name__ == "__main__":
    run(build_parser().parse_args())

