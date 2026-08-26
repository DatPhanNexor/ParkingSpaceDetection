# -*- coding: utf-8 -*-
"""Train YOLOv8s 15 epochs if needed, then open the realtime detector."""
from pathlib import Path
import argparse
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
BEST = ROOT / "models" / "parking_v8s_e15_best.pt"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="1")
    ap.add_argument("--mode", choices=["boardlock", "outdoor"], default="boardlock")
    ap.add_argument("--skip-train", action="store_true")
    ap.add_argument("--force-train", action="store_true")
    ap.add_argument("--no-vehicle", action="store_true")
    ap.add_argument("--show-conf", action="store_true")
    ap.add_argument("extra", nargs="*")
    args = ap.parse_args()

    if args.force_train or (not args.skip_train and not BEST.exists()):
        code = subprocess.call([sys.executable, str(ROOT / "TRAIN_V8S_5EPOCH_GPU.py")], cwd=str(ROOT))
        if code != 0:
            return code
    else:
        print(f"[INFO] Skip train, using model: {BEST if BEST.exists() else 'visual-only boardlock'}")

    cmd = [
        sys.executable,
        str(ROOT / "run_droidcam_v8s_boardlock.py"),
        "--source",
        str(args.source),
        "--mode",
        args.mode,
    ]
    if args.no_vehicle:
        cmd.append("--no-vehicle")
    if args.show_conf:
        cmd.append("--show-conf")
    cmd.extend(args.extra)
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
