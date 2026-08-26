from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "ParkingSpaceDesktopApp"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from detection_engine import (  # noqa: E402
    IMAGE_VIDEO_MODEL_NAME,
    PARKINGVISION_DEFAULT_MODEL_NAME,
    DetectionEngine,
)


def make_engine() -> DetectionEngine:
    return DetectionEngine(PROJECT_ROOT, APP_DIR)


def test_required_model_files_exist():
    assert (PROJECT_ROOT / IMAGE_VIDEO_MODEL_NAME).exists()
    assert (PROJECT_ROOT / "ParkingVisionV8" / "models" / PARKINGVISION_DEFAULT_MODEL_NAME).exists()


def test_parkingvision_config_exists_and_has_9_valid_zones():
    pv8 = PROJECT_ROOT / "ParkingVisionV8"
    board_lock = pv8 / "parkingvision_board_lock_9zones.json"
    slots_template = pv8 / "parkingvision_slots_template_9zones.json"
    assert board_lock.exists()
    assert slots_template.exists()
    slots = json.loads(slots_template.read_text(encoding="utf-8"))["slots"]
    board = json.loads(board_lock.read_text(encoding="utf-8"))

    assert len(slots) == 9
    assert len({slot["id"] for slot in slots}) == len(slots)
    for slot in slots:
        x1, y1, x2, y2 = slot["box"]
        assert 0 <= x1 < x2 <= 1
        assert 0 <= y1 < y2 <= 1
        polygon = np.asarray([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], dtype="float32")
        assert cv2.contourArea(polygon) > 0

    quad = board["quad"]
    assert len(quad) == 4
    assert len({tuple(point) for point in quad}) == 4
    assert cv2.contourArea(np.asarray(quad, dtype="float32")) > 0
    assert [slot["id"] for slot in board["slots_template"]] == [slot["id"] for slot in slots]


def test_desktop_bridge_can_read_parkingvision_config():
    from parkingvision_v8_bridge import _import_parkingvision_module

    pv8_dir = PROJECT_ROOT / "ParkingVisionV8"
    pv8 = _import_parkingvision_module(pv8_dir)
    slots = pv8.load_slots_template(pv8_dir / "parkingvision_slots_template_9zones.json")
    board = pv8.load_board_cache_quad(pv8_dir / "parkingvision_board_lock_9zones.json")
    assert len(slots) == 9
    assert len({slot["id"] for slot in slots}) == 9
    assert board is not None


def test_default_models_are_mode_specific():
    engine = make_engine()
    assert engine.default_model_for_mode("Image") == IMAGE_VIDEO_MODEL_NAME
    assert engine.default_model_for_mode("Video") == IMAGE_VIDEO_MODEL_NAME
    assert engine.default_model_for_mode("Webcam") == PARKINGVISION_DEFAULT_MODEL_NAME
    assert engine.list_models_for_mode("Image") == [IMAGE_VIDEO_MODEL_NAME]
    assert PARKINGVISION_DEFAULT_MODEL_NAME in engine.list_models_for_mode("Webcam")


def test_wrong_model_is_corrected_for_mode():
    engine = make_engine()
    corrected, warning = engine.normalize_model_for_mode("Image", PARKINGVISION_DEFAULT_MODEL_NAME)
    assert corrected == IMAGE_VIDEO_MODEL_NAME
    assert "Image mode uses" in warning

    corrected, warning = engine.normalize_model_for_mode("Webcam", IMAGE_VIDEO_MODEL_NAME)
    assert corrected == PARKINGVISION_DEFAULT_MODEL_NAME
    assert "Webcam/DroidCam mode uses" in warning


def test_preview_letterbox_math_no_crop():
    import pytest

    pytest.importorskip("customtkinter")
    from app_gui import fit_letterbox_size

    new_w, new_h, x, y = fit_letterbox_size((1920, 1080), (1000, 500))
    assert (new_w, new_h) == (888, 500)
    assert x >= 0 and y == 0
    assert new_w <= 1000 and new_h <= 500

    new_w, new_h, x, y = fit_letterbox_size((640, 480), (1920, 600))
    assert (new_w, new_h) == (800, 600)
    assert x >= 0 and y == 0
    assert new_w <= 1920 and new_h <= 600


def test_scan_camera_failure_returns_empty(monkeypatch):
    class FakeCapture:
        def __init__(self, *args, **kwargs):
            pass

        def isOpened(self):
            return False

        def read(self):
            return False, None

        def release(self):
            pass

    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    assert make_engine().scan_cameras(2) == []
