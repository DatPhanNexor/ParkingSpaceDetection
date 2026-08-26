import sys
import os
import hashlib
from pathlib import Path
import json
import csv
import ultralytics
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = PROJECT_ROOT / "yolov8s.pt"
DATASET_YAML = PROJECT_ROOT / "dataset_roboflow" / "data.yaml"

def calculate_checksum(file_path):
    if not file_path.exists():
        return None
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def run_evaluation():
    if not MODEL_PATH.exists():
        print(f"Model not found at {MODEL_PATH}")
        return
        
    model_checksum = calculate_checksum(MODEL_PATH)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    print(f"Running evaluation on {device}...")
    
    model = ultralytics.YOLO(str(MODEL_PATH))
    
    # We attempt validation if dataset exists
    metrics = None
    if DATASET_YAML.exists():
        dataset_checksum = calculate_checksum(DATASET_YAML)
        print("Dataset found. Running validation...")
        results = model.val(data=str(DATASET_YAML), split="test", device=device, plots=True)
        metrics = {
            "mAP50": results.box.map50,
            "mAP50-95": results.box.map,
            "precision": results.box.p.mean() if len(results.box.p) > 0 else 0,
            "recall": results.box.r.mean() if len(results.box.r) > 0 else 0,
            "f1": results.box.f1.mean() if len(results.box.f1) > 0 else 0,
        }
    else:
        dataset_checksum = None
        print("Dataset YAML not found. Cannot run full validation.")
        
    report = {
        "model": "yolov8s.pt",
        "model_checksum": model_checksum,
        "dataset_yaml_checksum": dataset_checksum,
        "device": device,
        "metrics": metrics
    }
    
    out_dir = PROJECT_ROOT / "backend_microservices" / "evaluation"
    out_dir.mkdir(exist_ok=True)
    
    # Write JSON
    with open(out_dir / "report.json", "w") as f:
        json.dump(report, f, indent=4)
        
    # Write CSV
    with open(out_dir / "report.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Model", report["model"]])
        writer.writerow(["Device", report["device"]])
        if metrics:
            for k, v in metrics.items():
                writer.writerow([k, v])
                
    # Write Markdown
    with open(out_dir / "report.md", "w") as f:
        f.write(f"# AI Evaluation Report\n\n")
        f.write(f"- **Model**: {report['model']}\n")
        f.write(f"- **Device**: {report['device']}\n")
        f.write(f"- **Model Checksum**: {report['model_checksum']}\n")
        f.write(f"- **Dataset Checksum**: {report['dataset_yaml_checksum']}\n\n")
        if metrics:
            f.write("## Metrics\n")
            for k, v in metrics.items():
                f.write(f"- **{k}**: {v:.4f}\n")
        else:
            f.write("Dataset not found. Metrics not generated.\n")
            
    print("Evaluation script completed.")

if __name__ == "__main__":
    run_evaluation()
