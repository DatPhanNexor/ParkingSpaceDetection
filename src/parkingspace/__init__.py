"""Public API for the legacy :mod:`parkingspace` pipeline.

Heavy computer-vision dependencies are imported lazily so package metadata and
configuration remain inspectable before the optional runtime is provisioned.
"""

from importlib import import_module

__version__ = "1.0.0"
__author__ = "Python Apex"
__email__ = "pythonapex01@gmail.com"
__license__ = "Apache-2.0"

_LAZY_EXPORTS = {
    "main": (".main", "main"),
    "process_frame": (".pipeline", "process_frame"),
    "load_regions_from_file": (".regions", "load_regions_from_file"),
    "save_regions_to_file": (".regions", "save_regions_to_file"),
    "get_thresholds": (".regions", "get_thresholds"),
    "get_contour_center": (".utils", "get_contour_center"),
    "get_config": (".config", "get_config"),
    "Config": (".config", "Config"),
    "setup_logging": (".logger", "setup_logging"),
    "get_logger": (".logger", "get_logger"),
    "get_performance_monitor": (".performance", "get_performance_monitor"),
    "get_capability_detector": (".capabilities", "get_capability_detector"),
    "get_startup_optimizer": (".capabilities", "get_startup_optimizer"),
    "SystemCapabilities": (".capabilities", "SystemCapabilities"),
    "OptimizationProfile": (".capabilities", "OptimizationProfile"),
    "CapabilityDetector": (".capabilities", "CapabilityDetector"),
    "StartupOptimizer": (".capabilities", "StartupOptimizer"),
    "ParkingSpaceService": (".services", "ParkingSpaceService"),
    "ModelService": (".services", "ModelService"),
    "RegionService": (".services", "RegionService"),
    "ProcessingService": (".services", "ProcessingService"),
    "VideoService": (".services", "VideoService"),
    "DetectionResult": (".services", "DetectionResult"),
    "FrameProcessingResult": (".services", "FrameProcessingResult"),
    "ParkingSpaceError": (".exceptions", "ParkingSpaceError"),
    "ModelLoadError": (".exceptions", "ModelLoadError"),
    "RegionLoadError": (".exceptions", "RegionLoadError"),
    "ProcessingError": (".exceptions", "ProcessingError"),
    "ConfigurationError": (".exceptions", "ConfigurationError"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    """Load public runtime objects on first access."""
    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value
