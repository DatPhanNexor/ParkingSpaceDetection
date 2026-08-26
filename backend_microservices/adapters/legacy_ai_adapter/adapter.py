import sys
from pathlib import Path

# Add legacy code path to sys.path to allow imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT / "ParkingVisionV8"))

from pydantic import BaseModel
from typing import List, Dict, Optional
import ultralytics
import cv2
import numpy as np

# We import the slots template and thresholds safely
try:
    from run_droidcam_v8s_boardlock import DEFAULT_SLOTS_TEMPLATE
except ImportError:
    # Fallback if import fails
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

# We don't import the whole script because it runs an infinite loop with cv2.imshow
# Instead, we wrap the YOLO model logic here

class LegacyAIAdapter:
    def __init__(self):
        self.model_yolov8s = ultralytics.YOLO(str(PROJECT_ROOT / "yolov8s.pt"))
        self.model_yolo11n_seg = ultralytics.YOLO(str(PROJECT_ROOT / "yolo11n-seg.pt"))
        self.slots = DEFAULT_SLOTS_TEMPLATE

    def detect_image(self, image_path: str):
        results = self.model_yolo11n_seg(image_path)
        # simplified mock return for the adapter
        return {"results": "success", "image": image_path}

    def detect_frame(self, frame: np.ndarray) -> Dict[str, str]:
        # Very simplified representation of the frame detection logic
        results = self.model_yolov8s(frame, verbose=False)
        detected_status = {}
        
        # Default all slots to EMPTY
        for slot in self.slots:
            slot_id_str = str(slot["id"])
            detected_status[slot_id_str] = "EMPTY"
            
        if not results:
            return detected_status
            
        boxes = results[0].boxes
        if not boxes:
            return detected_status
            
        # Map objects to slots
        h, w = frame.shape[:2]
        for box in boxes:
            cls_id = int(box.cls.item())
            if cls_id not in [2, 3, 5, 7]: # coco vehicles
                continue
            
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            
            # naive mapping to slot based on center
            for slot in self.slots:
                s_x1, s_y1, s_x2, s_y2 = slot["box"]
                abs_sx1, abs_sy1, abs_sx2, abs_sy2 = s_x1*w, s_y1*h, s_x2*w, s_y2*h
                if abs_sx1 <= cx <= abs_sx2 and abs_sy1 <= cy <= abs_sy2:
                    detected_status[str(slot["id"])] = "OCCUPIED"
                    
        return detected_status
