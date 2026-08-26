# src/parkingspace/config.py

import os
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from .exceptions import ConfigurationError


_SOURCE_ROOT = Path(__file__).resolve().parents[2]
if not (_SOURCE_ROOT / "pyproject.toml").is_file():
    _SOURCE_ROOT = None


def _default_asset_path(relative_path: str) -> str:
    """Resolve repository assets without requiring the process CWD."""
    candidates = [Path.cwd() / relative_path]
    if _SOURCE_ROOT is not None:
        candidates.append(_SOURCE_ROOT / relative_path)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return str(candidates[0].resolve())


@dataclass
class DetectionConfig:
    """Configuration for YOLO detection"""
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.7
    max_detections: int = 300
    classes: list = field(default_factory=lambda: [2, 3, 5, 7])  # car, motorcycle, bus, truck
    image_size: tuple = (1088, 1920)


@dataclass  
class ProcessingConfig:
    """Configuration for image processing"""
    interval_seconds: float = 3.0
    blur_kernel_size: tuple = (5, 5)
    morphology_kernel_size: tuple = (3, 3)
    contour_min_area: int = 100
    binary_threshold: int = 50
    morph_kernel_size: int = 5


@dataclass
class VideoConfig:
    """Configuration for video processing"""
    input_file: str = "Demo/exp3.mp4"
    probability_map: str = "Demo/probability_map.png"
    show_display: bool = True
    quit_key: str = 'q'


@dataclass
class PerformanceConfig:
    """Configuration for performance monitoring"""
    log_interval: int = 10  # frames
    enable_cuda_benchmark: bool = True
    

class Config:
    """Main configuration management for ParkingSpace application"""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration
        
        Args:
            config_file: Optional path to JSON configuration file
        """
        self.device = 'cuda' if self._is_cuda_available() else 'cpu'
        self.model_path = self._get_model_path()
        self.regions_file = _default_asset_path('regions.json')
        self.log_level = logging.INFO
        
        # Initialize sub-configurations
        self.detection = DetectionConfig()
        self.processing = ProcessingConfig()
        self.video = VideoConfig(
            input_file=_default_asset_path("Demo/exp3.mp4"),
            probability_map=_default_asset_path("Demo/probability_map.png"),
        )
        self.performance = PerformanceConfig()
        
        # Load from config file if provided
        if config_file:
            if not os.path.isfile(config_file):
                raise ConfigurationError(f"Configuration file not found: {config_file}")
            self._load_from_file(config_file)
            
        # Override with environment variables
        self._load_from_env()
        
    def _is_cuda_available(self) -> bool:
        """Check if CUDA is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def _get_model_path(self) -> str:
        """Get the path to the YOLO model"""
        # The legacy processing service consumes ``result.masks`` and therefore
        # must never fall back to a detection-only checkpoint.
        possible_paths = ['yolo11x-seg.pt', 'yolo11n-seg.pt']
        for path in possible_paths:
            resolved = _default_asset_path(path)
            if Path(resolved).is_file():
                return resolved
        return _default_asset_path('yolo11x-seg.pt')
    
    def _load_from_file(self, config_file: str) -> None:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            if not isinstance(config_data, dict):
                raise ConfigurationError("Configuration root must be a JSON object")
                
            # Update configurations from file
            if 'detection' in config_data:
                for key, value in config_data['detection'].items():
                    if hasattr(self.detection, key):
                        setattr(self.detection, key, value)
                        
            if 'processing' in config_data:
                for key, value in config_data['processing'].items():
                    if hasattr(self.processing, key):
                        setattr(self.processing, key, value)
                        
            if 'video' in config_data:
                for key, value in config_data['video'].items():
                    if hasattr(self.video, key):
                        setattr(self.video, key, value)
                        
            # Update main config
            for key in ['model_path', 'regions_file', 'device']:
                if key in config_data:
                    setattr(self, key, config_data[key])
                    
        except ConfigurationError:
            raise
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise ConfigurationError(
                f"Failed to load configuration from {config_file}: {exc}"
            ) from exc
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables"""
        # Device configuration
        if os.getenv('PARKINGSPACE_DEVICE'):
            self.device = os.getenv('PARKINGSPACE_DEVICE')
            
        # Model path
        if os.getenv('PARKINGSPACE_MODEL_PATH'):
            self.model_path = os.getenv('PARKINGSPACE_MODEL_PATH')
            
        # Video file
        if os.getenv('PARKINGSPACE_VIDEO_FILE'):
            self.video.input_file = os.getenv('PARKINGSPACE_VIDEO_FILE')
            
        # Detection confidence
        if os.getenv('PARKINGSPACE_CONFIDENCE'):
            try:
                self.detection.confidence_threshold = float(os.getenv('PARKINGSPACE_CONFIDENCE'))
            except ValueError:
                pass
    
    def save_to_file(self, config_file: str) -> None:
        """Save current configuration to JSON file"""
        config_data = {
            'device': self.device,
            'model_path': self.model_path,
            'regions_file': self.regions_file,
            'detection': {
                'confidence_threshold': self.detection.confidence_threshold,
                'iou_threshold': self.detection.iou_threshold,
                'max_detections': self.detection.max_detections,
                'classes': self.detection.classes,
                'image_size': self.detection.image_size
            },
            'processing': {
                'interval_seconds': self.processing.interval_seconds,
                'blur_kernel_size': self.processing.blur_kernel_size,
                'morphology_kernel_size': self.processing.morphology_kernel_size,
                'contour_min_area': self.processing.contour_min_area,
                'binary_threshold': self.processing.binary_threshold,
                'morph_kernel_size': self.processing.morph_kernel_size
            },
            'video': {
                'input_file': self.video.input_file,
                'probability_map': self.video.probability_map,
                'show_display': self.video.show_display,
                'quit_key': self.video.quit_key
            },
            'performance': {
                'log_interval': self.performance.log_interval,
                'enable_cuda_benchmark': self.performance.enable_cuda_benchmark
            }
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)

    def validate_legacy_runtime(self) -> None:
        """Fail clearly when external assets for the legacy pipeline are absent."""
        required = {
            "model": self.model_path,
            "regions": self.regions_file,
            "probability_map": self.video.probability_map,
            "video": self.video.input_file,
        }
        missing = [f"{name}={path}" for name, path in required.items() if not Path(path).is_file()]
        if missing:
            details = "; ".join(missing)
            raise ConfigurationError(
                "Missing required external asset(s) for the legacy pipeline: " + details
            )
    
    def get_detection_config(self) -> Dict[str, Any]:
        """Get detection configuration parameters (legacy compatibility)"""
        return {
            'confidence_threshold': self.detection.confidence_threshold,
            'iou_threshold': self.detection.iou_threshold,
            'max_detections': self.detection.max_detections,
            'classes': self.detection.classes
        }
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get image processing configuration (legacy compatibility)"""
        return {
            'blur_kernel_size': self.processing.blur_kernel_size,
            'morphology_kernel_size': self.processing.morphology_kernel_size,
            'contour_min_area': self.processing.contour_min_area
        }


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config(config_file: Optional[str] = None) -> Config:
    """Get application configuration instance (singleton pattern)"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_file)
    return _config_instance


def reset_config() -> None:
    """Reset configuration instance (useful for testing)"""
    global _config_instance
    _config_instance = None
