from __future__ import annotations

import importlib
import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pytest


pytest.importorskip("cv2")
pytest.importorskip("customtkinter")

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "ParkingSpaceDesktopApp"
)

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

app_gui: ModuleType = importlib.import_module("app_gui")
detection_engine: ModuleType = importlib.import_module(
    "detection_engine"
)

ParkingSpaceDesktopApp = app_gui.ParkingSpaceDesktopApp
TaggedInferenceResult = app_gui.TaggedInferenceResult
inference_result_is_current = (
    app_gui.inference_result_is_current
)
normalize_camera_source = app_gui.normalize_camera_source
should_submit_inference = app_gui.should_submit_inference

CameraOpenResult = detection_engine.CameraOpenResult
EngineSettings = detection_engine.EngineSettings

CameraSource = int | str


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", 0),
        (" 1 ", 1),
        (2, 2),
        (
            "http://127.0.0.1:4747/video",
            "http://127.0.0.1:4747/video",
        ),
        (
            "https://camera.example/live",
            "https://camera.example/live",
        ),
        (
            "rtsp://camera.example/live",
            "rtsp://camera.example/live",
        ),
    ],
)
def test_normalize_camera_source(
    raw: object,
    expected: CameraSource,
) -> None:
    assert normalize_camera_source(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        -1,
        True,
        "camera",
        "ftp://camera/live",
        "http:///video",
        "http://:4747/video",
        "rtsp://bad host/live",
    ],
)
def test_normalize_camera_source_rejects_invalid_values(
    raw: object,
) -> None:
    with pytest.raises(ValueError, match="Camera"):
        normalize_camera_source(raw)


class FakeCapture:
    def __init__(self) -> None:
        self.released = False

    def isOpened(self) -> bool:
        return not self.released

    def release(self) -> None:
        self.released = True


class FakeEngineCapture:
    def __init__(self) -> None:
        self.received: CameraSource | None = None
        self.capture = FakeCapture()

    def open_camera_source(
        self,
        source: CameraSource,
    ) -> Any:
        self.received = source

        return CameraOpenResult(
            source=str(source),
            cap=self.capture,
            first_frame=np.zeros(
                (10, 10, 3),
                dtype=np.uint8,
            ),
            label="fake",
        )


def no_operation(
    *args: object,
    **kwargs: object,
) -> None:
    return None


def test_open_capture_passes_selected_source_without_real_camera() -> None:
    engine = FakeEngineCapture()

    app = SimpleNamespace(
        engine=engine,
        _post_ui=no_operation,
        _log=no_operation,
        _set_webcam_status=no_operation,
        _capture_lock=threading.Lock(),
        _active_capture_session=None,
        _active_capture=None,
    )

    opened_capture, opened_frame = (
        ParkingSpaceDesktopApp._open_capture(
            app,
            "Webcam",
            1,
            7,
        )
    )

    assert engine.received == 1
    assert opened_capture is engine.capture
    assert isinstance(opened_frame, np.ndarray)


@pytest.mark.parametrize(
    ("every", "expected"),
    [
        (1, [1, 2, 3, 4, 5, 6]),
        (2, [1, 2, 4, 6]),
        (3, [1, 3, 6]),
    ],
)
def test_frame_skip_schedule_never_creates_placeholder_results(
    every: int,
    expected: list[int],
) -> None:
    submitted = [
        frame_id
        for frame_id in range(1, 7)
        if should_submit_inference(
            frame_id,
            every,
            False,
        )
    ]

    assert submitted == expected
    assert not should_submit_inference(
        3,
        every,
        True,
    )


def test_tagged_result_keeps_frame_and_session_identity() -> None:
    visual = object()

    rendered_frame = np.zeros(
        (10, 10, 3),
        dtype=np.uint8,
    )

    result = TaggedInferenceResult(
        session_id=4,
        frame_id=23,
        visual=visual,
        rendered_frame=rendered_frame,
    )

    assert inference_result_is_current(result, 4)
    assert not inference_result_is_current(result, 5)
    assert result.frame_id == 23
    assert result.rendered_frame is rendered_frame


class FakeEngineAnalyze:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, int, str]] = []

    def analyze_frame(
        self,
        frame: np.ndarray,
        settings: Any,
        input_mode: str,
        input_source: str,
        displayed_frames: int = 1,
        detected_batches: int = 1,
        fps: float = 0.0,
    ) -> Any:
        self.calls.append(
            (
                frame.tobytes(),
                displayed_frames,
                input_source,
            )
        )

        return object()

    def draw_overlay(
        self,
        frame: np.ndarray,
        visual: object | None,
        settings: object | None = None,
    ) -> np.ndarray:
        return np.ones_like(frame)


def test_fake_worker_returns_overlay_for_the_same_frame_id() -> None:
    engine = FakeEngineAnalyze()

    app = SimpleNamespace(
        engine=engine,
    )

    settings = EngineSettings()

    frame = np.zeros(
        (10, 10, 3),
        dtype=np.uint8,
    )

    result = ParkingSpaceDesktopApp._analyze_tagged_frame(
        app,
        3,
        12,
        frame,
        settings,
        "Video",
        "demo.mp4",
        4,
        20.0,
    )

    assert engine.calls == [
        (
            frame.tobytes(),
            12,
            "demo.mp4",
        )
    ]

    assert result.session_id == 3
    assert result.frame_id == 12
    assert isinstance(result.rendered_frame, np.ndarray)
    assert result.rendered_frame.shape == frame.shape


def test_stop_cleanup_releases_only_current_session_capture() -> None:
    capture = FakeCapture()

    app = SimpleNamespace(
        _capture_lock=threading.Lock(),
        _active_capture_session=8,
        _active_capture=capture,
        _post_ui=no_operation,
        _log=no_operation,
    )

    ParkingSpaceDesktopApp._release_active_capture(
        app,
        7,
    )

    assert not capture.released
    assert app._active_capture is capture

    ParkingSpaceDesktopApp._release_active_capture(
        app,
        8,
    )

    assert capture.released
    assert app._active_capture is None

def test_bridge_conversion_no_tuple_error(monkeypatch) -> None:
    # Test that extracting the box and polygon in bridge's process_frame
    # does not throw "tuple expected at most 1 argument, got 2"
    from parkingvision_v8_bridge import ParkingVisionV8BoardlockEngine
    from types import SimpleNamespace
    import numpy as np
    
    # Mock ParkingVisionV8 dependency loading
    monkeypatch.setattr("parkingvision_v8_bridge._import_parkingvision_module", lambda p: SimpleNamespace(
        YOLO_IMPORT_ERROR="",
        _yolo_factory=lambda p: None,
        build_parser=lambda: SimpleNamespace(parse_args=lambda x: SimpleNamespace(no_vehicle=True, board_reset_after=30)),
        load_slots_template=lambda p, create_if_missing: [{"id": str(i)} for i in range(1, 10)],
        load_board_cache_quad=lambda p: None,
        load_empty_baseline=lambda p: None,
        choose_device=lambda p: "cpu",
        BoardTracker=lambda args: SimpleNamespace(update=lambda b: SimpleNamespace(source="mock")),
        SlotStabilizer=lambda ids, args: SimpleNamespace(reset=lambda: None),
        detect_board_quad=lambda frame, args: None,
        validate_board_quad=lambda frame, cache, args, source: None,
        detect_with_parking_model=lambda model, frame, args: [],
        detect_vehicles=lambda model, frame, args: [],
        classify_template_slots=lambda frame, board, template, md, vd, stab, args, baseline_warped: [
            SimpleNamespace(id=str(i), label="occupied" if i==1 else "empty", score=0.9, box=[0,0,10,10], polygon=[[0,0], [10,0], [10,10], [0,10]])
            for i in range(1, 10)
        ],
        draw_board_status=lambda frame, board, args: None,
        draw_slot_results=lambda frame, results, args: {},
        draw_hud=lambda frame, counts, fps, mode, bv, bc, total_override: None,
    ))
    import sys
    ultralytics_mock = SimpleNamespace(YOLO=lambda path: SimpleNamespace())
    # pyrefly: ignore [unsupported-operation]
    sys.modules["ultralytics"] = ultralytics_mock

    # Create bridge instance
    import os
    real_dir = os.path.abspath("ParkingVisionV8")
    real_model = os.path.abspath("yolov8s.pt")
    bridge = ParkingVisionV8BoardlockEngine(real_model, real_dir, "cpu")
    
    # Run process_frame and check if it handles the mock output (which includes box and polygon)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    res = bridge.process_frame(frame, show_boxes=False, show_labels=False)
    
    # Verification: should have 9 slots, no TypeError raised
    assert res["measurement_valid"] is True
    assert res["total"] == 9
    assert len(res["slot_states"]) == 9
    
    # Check that tuple conversion worked correctly
    slot_1 = res["slot_states"][0]
    assert isinstance(slot_1["box"], tuple)
    assert len(slot_1["box"]) == 4
    assert isinstance(slot_1["polygon"], tuple)
    assert len(slot_1["polygon"]) == 4
    assert isinstance(slot_1["polygon"][0], tuple)
    assert len(slot_1["polygon"][0]) == 2