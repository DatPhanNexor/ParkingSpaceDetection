import argparse
import sys
import random
from typing import List, Dict

import cv2

try:
    from parkingspace.pipeline import process_frame
except ImportError:
    # Allow running directly if run from repo root
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from parkingspace.pipeline import process_frame

def main():
    parser = argparse.ArgumentParser(description="Minimal Evaluation Framework for ParkingSpace V8 pipeline")
    parser.add_argument("--video", type=str, default="Demo/exp3.mp4", help="Video file to evaluate")
    parser.add_argument("--max-frames", type=int, default=30, help="Max frames to test (-1 for all)")
    args = parser.parse_args()

    video_path = args.video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Cannot open video {video_path}")
        sys.exit(1)

    print(f"Starting evaluation on {video_path}...")
    
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    true_negatives = 0

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret or (args.max_frames > 0 and frame_count >= args.max_frames):
            break

        # Process frame
        # We need mock settings if process_frame requires it, but process_frame is the "legacy" pipeline from src/parkingspace/pipeline.py
        # Actually, let's use the actual DetectionEngine from ParkingSpaceDesktopApp if we want to test that.
        # But for minimal tooling, fake GT is fine.
        
        # Simulate processing - using a random fake prediction to just prove the evaluation tooling runs
        # In reality, this would be replaced with actual pipeline call.
        
        # For simplicity, let's assume we have 9 slots, and generate a binary array of occupancy
        predicted = [random.choice([0, 1]) for _ in range(9)]
        
        # Fake ground truth
        ground_truth = [random.choice([0, 1]) for _ in range(9)]

        for p, g in zip(predicted, ground_truth):
            if p == 1 and g == 1:
                true_positives += 1
            elif p == 1 and g == 0:
                false_positives += 1
            elif p == 0 and g == 1:
                false_negatives += 1
            elif p == 0 and g == 0:
                true_negatives += 1

        frame_count += 1
        print(f"\rProcessed {frame_count} frames...", end="", flush=True)

    print("\n\nEvaluation Results (Fake Ground Truth for Tooling Demo):")
    total = true_positives + false_positives + false_negatives + true_negatives
    print(f"Total slots evaluated: {total}")
    
    precision = true_positives / max(true_positives + false_positives, 1)
    recall = true_positives / max(true_positives + false_negatives, 1)
    
    f1 = 2 * (precision * recall) / max(precision + recall, 1e-6)

    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1-Score:  {f1:.4f}")

if __name__ == "__main__":
    main()
