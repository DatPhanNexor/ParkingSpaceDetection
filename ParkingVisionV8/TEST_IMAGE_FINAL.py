# -*- coding: utf-8 -*-
"""Static image test for ParkingVisionV8."""
from pathlib import Path
import argparse
from collections import Counter
import cv2
import numpy as np
from typing import Optional
import run_droidcam_v8s_boardlock as pv


ROOT = Path(__file__).resolve().parent


def find_sample_image() -> Optional[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    for split in ("test", "valid", "train"):
        img_dir = ROOT / "dataset_roboflow" / split / "images"
        if img_dir.exists():
            for p in sorted(img_dir.iterdir()):
                if p.suffix.lower() in exts:
                    return p
    return None


def offset_results(results, ox: int, oy: int):
    offset = np.array([ox, oy], dtype=np.float32)
    box_offset = np.array([ox, oy, ox, oy], dtype=np.float32)
    return [
        pv.SlotResult(
            id=r.id,
            label=r.label,
            score=r.score,
            raw_score=r.raw_score,
            polygon=r.polygon + offset,
            box=r.box + box_offset,
            source=r.source,
            debug=r.debug,
        )
        for r in results
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?")
    ap.add_argument("--out", default="parkingvision_test_output.png")
    ap.add_argument("--mode", choices=["auto", "boardlock", "outdoor"], default="auto")
    ap.add_argument("--model", default="auto")
    ap.add_argument("--no-yolo", action="store_true")
    ap.add_argument("--no-vehicle", action="store_true")
    ap.add_argument("--no-visual", action="store_true")
    ap.add_argument("--no-yolo-require-visual", action="store_true")
    ap.add_argument("--show-conf", action="store_true")
    ap.add_argument("--empty-baseline", default=str(pv.DEFAULT_EMPTY_BASELINE))
    ap.add_argument("--debug-slots", action="store_true")
    args0 = ap.parse_args()

    image_path = Path(args0.image) if args0.image else find_sample_image()
    if image_path is None:
        print("[ERROR] Khong tim thay anh mau. Truyen duong dan anh: python TEST_IMAGE_FINAL.py path/to/image.jpg")
        return 1
    image_path = image_path.resolve()

    img = cv2.imread(str(image_path))
    if img is None:
        print(f"[ERROR] Khong doc duoc anh: {image_path}")
        return 1

    args = pv.build_parser().parse_args([])
    args.device = pv.choose_device(args.device)
    args.board_warmup_frames = 1
    args.occ_confirm_frames = 1
    args.empty_confirm_frames = 1
    args.show_conf = args0.show_conf
    args.debug_slots = args0.debug_slots
    args.empty_baseline = args0.empty_baseline
    args.model = args0.model
    args.no_vehicle = args0.no_vehicle
    args.visual_occupancy = not args0.no_visual
    if args0.no_yolo_require_visual:
        args.yolo_require_visual = False
    args.mode = "outdoor" if args0.mode == "auto" and "dataset_roboflow" in str(image_path) else ("boardlock" if args0.mode == "auto" else args0.mode)
    if args0.no_yolo:
        args.no_parking_model = True
        args.no_vehicle = True

    regions_path = pv.resolve_path(args.regions)
    args._regions = pv.load_regions(regions_path)
    parking_model, vehicle_model = (None, None) if args0.no_yolo else pv.load_models(args)

    out = img.copy()
    results = []
    board = None
    mode = args.mode
    conf = 0.0

    total_override = None
    if args.mode == "boardlock":
        board = pv.detect_board_quad(img, args)
        if board is None and args.use_board_cache:
            cached = pv.load_board_cache_quad(pv.resolve_path(args.board_cache))
            if cached is not None:
                board = pv.validate_board_quad(img, cached, args, source="board-cache")
        try:
            slots = pv.load_slots_template(pv.DEFAULT_TEMPLATE, create_if_missing=False)
        except FileNotFoundError as e:
            print(f"[ERROR] {e}")
            return 1
        total_override = len(slots)
        baseline = pv.load_empty_baseline(pv.resolve_path(args.empty_baseline))
        if baseline is None:
            print("[WARN] No empty baseline found. Static boardlock test will use strict no-baseline logic.")
        if board is not None:
            stabilizer = pv.SlotStabilizer([s["id"] for s in slots], args)
            model_dets = pv.detect_with_parking_model(parking_model, img, args) if parking_model else []
            vehicle_dets = [] if args.no_vehicle else pv.detect_vehicles(vehicle_model, img, args)
            results = pv.classify_template_slots(img, board, slots, model_dets, vehicle_dets, stabilizer, args, baseline_warped=baseline)
            pv.draw_board_status(out, board, args)
            conf = board.confidence
    else:
        model_dets = pv.detect_with_parking_model(parking_model, img, args) if parking_model else []
        vehicle_dets = [] if args.no_vehicle else pv.detect_vehicles(vehicle_model, img, args)
        all_dets = model_dets + vehicle_dets
        results = pv.classify_region_slots(all_dets, img.shape, args) if args._regions.get("slots") else pv.parking_dets_to_slot_results(all_dets, img.shape, args)

    counts = pv.draw_slot_results(out, results, args)
    total_override = total_override if args.mode == "boardlock" and board is not None else (len(args._regions.get("slots", [])) or None)
    pv.draw_hud(out, counts, 0.0, mode, board is not None, conf, total_override=total_override)
    cv2.imwrite(args0.out, out)
    counts = Counter(r.label for r in results)
    print(f"[INFO] image={image_path}")
    print([(r.id, r.label, round(r.raw_score, 3)) for r in results])
    print(f"[SUMMARY] empty={counts.get('empty', 0)} occupied={counts.get('occupied', 0)} total={len(results)} board={'yes' if board is not None else 'no'}")
    print(f"[OK] Saved: {Path(args0.out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
