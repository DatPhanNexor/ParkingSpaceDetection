# -*- coding: utf-8 -*-
"""Train YOLOv8s for ParkingVisionV8 with 15 epochs on GPU only."""
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "dataset_roboflow"
MODELS = ROOT / "models"
DATA_YAML = DATASET / "data.yaml"
OUT_MODEL = MODELS / "parking_v8s_e15_best.pt"
BACKUP_MODEL = MODELS / "parking_v8s_e15_best.backup.pt"
BASE_MODEL = OUT_MODEL if OUT_MODEL.exists() else MODELS / "yolov8s.pt"
RUN_NAME = "parking_v8s_e15"


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def print_manual_command(data_yaml: Path) -> None:
    model_arg = rel(BASE_MODEL) if BASE_MODEL.exists() else "yolov8s.pt"
    print("[MANUAL] Run this on a CUDA machine:")
    print(
        "yolo detect train "
        f"model={model_arg} "
        f"data={rel(data_yaml)} "
        "epochs=15 imgsz=640 batch=-1 device=0 workers=4 "
        f"name={RUN_NAME} exist_ok=True"
    )


def ensure_data_yaml() -> Path:
    if DATA_YAML.exists():
        return DATA_YAML
    train_images = DATASET / "train" / "images"
    valid_images = DATASET / "valid" / "images"
    test_images = DATASET / "test" / "images"
    if not train_images.exists() or not valid_images.exists():
        raise FileNotFoundError("dataset_roboflow must contain train/images and valid/images")
    DATA_YAML.write_text(
        "path: ./dataset_roboflow\n"
        "train: train/images\n"
        "val: valid/images\n"
        f"test: {'test/images' if test_images.exists() else 'valid/images'}\n"
        "nc: 2\n"
        "names:\n"
        "  0: empty\n"
        "  1: occupied\n",
        encoding="utf-8",
    )
    print(f"[OK] Created data.yaml: {DATA_YAML}")
    return DATA_YAML


def check_gpu() -> bool:
    smi = subprocess.run(["nvidia-smi"], cwd=str(ROOT), text=True, capture_output=True)
    if smi.returncode != 0:
        print("[ERROR] nvidia-smi failed or NVIDIA driver is not available.")
        if smi.stderr.strip():
            print(smi.stderr.strip())
        return False
    print("[OK] nvidia-smi detected CUDA GPU.")

    try:
        import torch
    except Exception as e:
        print(f"[ERROR] Cannot import torch: {e}")
        return False
    cuda_ok = bool(torch.cuda.is_available())
    print(f"[INFO] torch.cuda.is_available()={cuda_ok}")
    if cuda_ok:
        try:
            print(f"[INFO] GPU 0: {torch.cuda.get_device_name(0)}")
        except Exception:
            pass
    return cuda_ok


def run_train_cli(data_yaml: Path) -> int:
    model_arg = rel(BASE_MODEL) if BASE_MODEL.exists() else "yolov8s.pt"
    cmd = [
        "yolo",
        "detect",
        "train",
        f"model={model_arg}",
        f"data={rel(data_yaml)}",
        "epochs=15",
        "imgsz=640",
        "batch=-1",
        "device=0",
        "workers=4",
        f"name={RUN_NAME}",
        "exist_ok=True",
    ]
    print("[INFO] " + " ".join(cmd))
    try:
        return subprocess.call(cmd, cwd=str(ROOT))
    except FileNotFoundError:
        print("[WARN] yolo command not found, falling back to ultralytics Python API.")
        return run_train_python(data_yaml, model_arg)


def run_train_python(data_yaml: Path, model_arg: str) -> int:
    try:
        from ultralytics import YOLO
    except Exception as e:
        print(f"[ERROR] Cannot import ultralytics: {e}")
        return 1
    model = YOLO(model_arg)
    model.train(
        data=rel(data_yaml),
        epochs=15,
        imgsz=640,
        batch=-1,
        device=0,
        workers=4,
        name=RUN_NAME,
        exist_ok=True,
    )
    return 0


def find_best_pt() -> Optional[Path]:
    candidates = [
        ROOT / "runs" / "detect" / RUN_NAME / "weights" / "best.pt",
        ROOT / "runs" / "train" / RUN_NAME / "weights" / "best.pt",
    ]
    candidates.extend(ROOT.glob(f"runs/**/{RUN_NAME}/weights/best.pt"))
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def backup_existing_model() -> None:
    if OUT_MODEL.exists():
        shutil.copy2(OUT_MODEL, BACKUP_MODEL)
        print(f"[OK] Backup existing production model: {BACKUP_MODEL}")


def main() -> int:
    if not DATASET.exists():
        print(f"[ERROR] Dataset not found: {DATASET}")
        return 1
    MODELS.mkdir(exist_ok=True)
    data_yaml = ensure_data_yaml()

    if not check_gpu():
        print("[ERROR] CUDA GPU is not available. CPU training is intentionally skipped.")
        print_manual_command(data_yaml)
        return 1

    if not BASE_MODEL.exists():
        print(f"[WARN] Base model not found at {BASE_MODEL}; Ultralytics will try yolov8s.pt by name.")

    code = run_train_cli(data_yaml)
    if code != 0:
        return code

    best = find_best_pt()
    if best is None:
        print("[ERROR] Training finished but best.pt was not found.")
        return 1
    backup_existing_model()
    shutil.copy2(best, OUT_MODEL)
    print(f"[OK] Copied best model: {OUT_MODEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
