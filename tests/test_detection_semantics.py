from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

import pytest

pytest.importorskip("cv2")
pytest.importorskip("numpy")

APP_DIR = Path(__file__).resolve().parents[1] / "ParkingSpaceDesktopApp"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from detection_engine import DetectionEngine, EngineSettings, parse_camera_source  # noqa: E402
from parkingvision_v8_bridge import summarize_slot_measurement  # noqa: E402


@pytest.mark.parametrize("raw, expected", [("0", 0), (" 1 ", 1), (2, 2)])
def test_parse_camera_index(raw, expected):
    assert parse_camera_source(raw) == expected


@pytest.mark.parametrize("url", ["http://camera/video", "https://camera/video", "rtsp://camera/live"])
def test_parse_camera_url_preserved(url):
    assert parse_camera_source(f" {url} ") == url


@pytest.mark.parametrize("raw", ["", "   ", "-1", -1, "camera-name", "ftp://camera/live"])
def test_invalid_camera_source_is_rejected(raw):
    with pytest.raises(ValueError, match="Camera"):
        parse_camera_source(raw)


def test_canonical_slot_measurement_and_no_board():
    valid = summarize_slot_measurement(9, Counter(empty=4, occupied=5), True)
    assert valid == {"empty": 4, "occupied": 5, "total": 9, "measurement_valid": True, "reason": "ok"}

    missing = summarize_slot_measurement(9, Counter(), False)
    assert missing["total"] == 9
    assert missing["measurement_valid"] is False
    assert missing["reason"] == "no_board"


def test_slot_count_mismatch_is_invalid():
    result = summarize_slot_measurement(9, Counter(empty=3, occupied=5), True)
    assert result["measurement_valid"] is False
    assert result["reason"] == "slot_count_mismatch"


def test_webcam_inference_error_returns_invalid_measurement(monkeypatch):
    import numpy as np

    class FailingBoardlock:
        def process_frame(self, *args, **kwargs):
            raise RuntimeError("synthetic failure")

    engine = object.__new__(DetectionEngine)
    engine._last_error = ""
    monkeypatch.setattr(engine, "enforce_model_for_mode", lambda *args: None)
    monkeypatch.setattr(engine, "_get_boardlock_engine", lambda settings: FailingBoardlock())
    monkeypatch.setattr(engine, "boardlock_total_hint", lambda: 9)
    monkeypatch.setattr(engine, "pick_device", lambda requested: "cpu")

    visual = engine.analyze_frame(np.zeros((8, 8, 3), dtype=np.uint8), EngineSettings(), "Webcam", "0")
    assert visual.stats.measurement_valid is False
    assert visual.stats.reason == "inference_error:RuntimeError"
    assert visual.stats.total == 9


def test_csv_formula_values_are_escaped():
    row = DetectionEngine._safe_csv_row({"source": "=1+1", "model": "safe.pt", "number": 1})
    assert row == {"source": "'=1+1", "model": "safe.pt", "number": 1}


def test_output_tokens_are_unique():
    assert DetectionEngine._output_token() != DetectionEngine._output_token()
