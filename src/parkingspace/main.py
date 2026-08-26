"""Entrypoint for the original regions/probability-map pipeline.

The CustomTkinter desktop dashboard remains a repository application launched
with ``ParkingSpaceDesktopApp/run_desktop_app.py``; it is not packaged here.
"""

from __future__ import annotations

import sys
import time
from typing import Optional, Sequence, Tuple

from .config import get_config
from .exceptions import ConfigurationError, ParkingSpaceError
from .logger import setup_logging


def legacy_main(config_file: Optional[str] = None, video_file: Optional[str] = None) -> int:
    """Run the legacy regions pipeline and return a process-style exit code."""
    startup_start = time.time()
    logger = setup_logging()
    logger.info("Starting legacy ParkingSpace regions pipeline")

    try:
        config = get_config(config_file)
        if video_file:
            config.video.input_file = video_file
        config.validate_legacy_runtime()

        try:
            from .capabilities import get_capability_detector, get_startup_optimizer
            from .services import ParkingSpaceService
        except ImportError as exc:
            dependency = getattr(exc, "name", None) or str(exc)
            raise ConfigurationError(
                f"Legacy runtime dependency is unavailable: {dependency}. "
                "Install the project dependencies before running detection."
            ) from exc

        detector = get_capability_detector()
        capabilities = detector.detect_system_capabilities()
        _apply_capability_optimizations(config, capabilities)
        logger.info(
            "Performance level: %s",
            capabilities.estimated_performance_level.upper(),
        )

        optimizer = get_startup_optimizer()
        optimizer.optimize_torch_settings(capabilities)
        logger.info("Using device: %s", config.device)

        parking_service = ParkingSpaceService(config)
        parking_service.initialize()
        logger.info("System ready in %.3fs", time.time() - startup_start)
        logger.info("Starting video processing")
        parking_service.process_video(video_file)
        logger.info("Legacy pipeline completed successfully")
        return 0
    except ParkingSpaceError as exc:
        logger.error("Application error: %s", exc)
        return 1
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 130
    except Exception as exc:
        logger.error("Unexpected application error: %s", exc)
        return 1


# Backward-compatible Python API; packaging exposes the explicit legacy name.
main = legacy_main


def _apply_capability_optimizations(config, capabilities) -> None:
    """Apply supported capability recommendations to configuration."""
    if not capabilities:
        return

    recommendations = capabilities.recommended_settings
    if recommendations.get("device") and hasattr(config, "device"):
        config.device = recommendations["device"]
    if hasattr(config, "processing") and recommendations.get("processing_interval"):
        config.processing.interval_seconds = recommendations["processing_interval"]
    if hasattr(config, "detection") and recommendations.get("image_size"):
        config.detection.image_size = recommendations["image_size"]
    if hasattr(config, "performance"):
        cuda_benchmark = recommendations.get("enable_cuda_benchmark")
        if cuda_benchmark is not None:
            config.performance.enable_cuda_benchmark = cuda_benchmark


def _parse_legacy_args(args: Sequence[str]) -> Tuple[Optional[str], Optional[str]]:
    """Parse the two optional legacy file arguments without side effects."""
    config_file = None
    video_file = None
    for value in args[:2]:
        suffix = value.lower()
        if suffix.endswith(".json"):
            config_file = value
        elif suffix.endswith((".mp4", ".avi", ".mov")):
            video_file = value
    return config_file, video_file


if __name__ == "__main__":
    raise SystemExit(legacy_main(*_parse_legacy_args(sys.argv[1:])))
