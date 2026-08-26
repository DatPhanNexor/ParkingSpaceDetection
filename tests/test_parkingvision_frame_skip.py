from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "ParkingVisionV8" / "run_droidcam_v8s_boardlock.py"
SPEC = importlib.util.spec_from_file_location("parkingvision_frame_skip", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
PV8 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PV8
SPEC.loader.exec_module(PV8)


@pytest.mark.parametrize(
    ("yolo_every", "expected_frames"),
    [(1, [1, 2, 3, 4, 5, 6]), (2, [2, 4, 6]), (3, [3, 6])],
)
def test_skipped_frames_do_not_produce_or_reuse_results(yolo_every, expected_frames):
    updates = []
    cached_result = []
    cached_frame_id = None

    for frame_id in range(1, 7):
        if PV8.should_run_inference(frame_id, yolo_every):
            updates.append(frame_id)
            cached_result = [frame_id]
            cached_frame_id = frame_id

        visible = PV8.results_for_frame(cached_result, cached_frame_id, frame_id, yolo_every)
        expected_visible = []
        if cached_frame_id is not None and frame_id - cached_frame_id <= max(1, yolo_every):
            expected_visible = [cached_frame_id]
        
        assert visible == expected_visible

    assert updates == expected_frames


def test_invalid_yolo_interval_is_clamped_without_division_by_zero():
    assert PV8.should_run_inference(1, 0)
