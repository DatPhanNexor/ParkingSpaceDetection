import os
import numpy as np
import pytest

# pyrefly: ignore [missing-import]
from src.parkingspace.utils import get_contour_center
from src.parkingspace.pipeline import process_frame
from src.parkingspace.regions import load_regions_from_file, get_thresholds
from src.parkingspace.performance import PerformanceMonitor
from src.parkingspace.capabilities import CapabilityDetector


def test_get_contour_center():
    # Make a simple rectangle contour
    contour = np.array([[[0,0]], [[10,0]], [[10,5]], [[0,5]]], dtype=np.int32)
    center = get_contour_center(contour)
    assert center == (5,2), f"Expected center (5,2), got {center}"


def test_process_frame_probability_map_cache_and_mask_scaling():
    regions = load_regions_from_file("regions.json")
    thresholds = get_thresholds()
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    mask_01 = np.zeros((1080, 1920), dtype=np.uint8)
    mask_01[100:300, 100:300] = 1
    mask_255 = (mask_01 * 255).astype(np.uint8)

    out1, count1 = process_frame(frame.copy(), mask_01, "Demo/probability_map.png", thresholds, *regions)
    out2, count2 = process_frame(frame.copy(), mask_01, "Demo/probability_map.png", thresholds, *regions)
    out3, count3 = process_frame(frame.copy(), mask_255, "Demo/probability_map.png", thresholds, *regions)

    assert count1 == count2 == count3
    assert np.array_equal(out1, out2)
    assert np.array_equal(out1, out3)


def test_performance_monitor_bounds_history():
    monitor = PerformanceMonitor(max_history=5)
    for i in range(12):
        monitor.start_frame_processing()
        monitor.end_frame_processing(detection_time=0.01 * i)
    assert len(monitor.metrics_history) == 5
    avg = monitor.get_average_metrics(last_n=5)
    assert avg is not None


def test_capability_detector_handles_none_physical_cpu_count(monkeypatch):
    monkeypatch.setattr("psutil.cpu_count", lambda logical=True: None if not logical else 4)
    detector = CapabilityDetector()
    caps = detector.detect_system_capabilities()
    assert caps.cpu_count == 4
    assert caps.estimated_performance_level in {"low", "medium", "high", "ultra"}
