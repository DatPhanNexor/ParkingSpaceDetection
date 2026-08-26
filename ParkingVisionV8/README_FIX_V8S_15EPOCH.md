# ParkingVisionV8 - 9-Zone DroidCam Boardlock

## Trang thai hien tai

- He thong DroidCam/board mini hien dung **9 vung do xe** theo `reference_9zones_board.jpg`.
- Khong con dung 11 slot lam mac dinh.
- `Total = 9` khi board visible.
- Khi camera roi khoi board: hien `NO_BOARD`, khong ve vung, khong ve EMPTY/OCCUPIED va khong dem gia.
- Lan cap nhat nay khong train lai; loi chinh la false OCCUPIED do visual fallback qua de dai.

## File JSON chinh

- Board lock production:
  - `parkingvision_board_lock_9zones.json`
- Slot template production:
  - `parkingvision_slots_template_9zones.json`
- Cau hinh V12 cu chi la lich su, khong con duoc runtime doc hoac yeu cau.
- File legacy 9-zone neu con ton tai chi dung de doc fallback mot lan:
  - `board_lock_9zones.json`
  - `slots_template_9zones.json`

Runtime mac dinh doc `parkingvision_board_lock_9zones.json` va `parkingvision_slots_template_9zones.json`.
Neu `parkingvision_board_lock_9zones.json` chua co, code co the doc fallback 9-zone `board_lock_9zones.json` mot lan va sau do ghi cache moi ve `parkingvision_board_lock_9zones.json`.
Neu `parkingvision_slots_template_9zones.json` mat, code chi duoc fallback sang template 9-zone cu `slots_template_9zones.json` neu file do con ton tai; khong fallback ve cau hinh V12.

## Thu tu 9 vung

- Vung 1, 2, 3, 4: 4 o xe hoi hang tren.
- Vung 5, 6, 7: 3 o xe hoi hang duoi.
- Vung 8, 9: 2 o ngang ben phai.

Bo qua:

- Khu "Bai 2 banh".
- Vung gach cheo vang cam do.
- Slot 10/11 cu.
- Vung ngoai board.

## Empty baseline calibration

De chong false OCCUPIED tren bai trong, nen tao baseline khi board dang trong hoan toan.

Dat camera nhin dung board trong, sau do chay:

```powershell
python run_droidcam_v8s_boardlock.py --source 0 --capture-empty-baseline
```

File baseline se duoc luu tai:

```text
empty_baseline_9zones.jpg
```

Khi chay realtime binh thuong, neu file nay ton tai, moi vung se duoc so sanh voi baseline trong inner ROI. Vung chi duoc OCCUPIED khi khac baseline du lon va co contour vat the ro. Neu chua co baseline, code van chay nhung se canh bao:

```text
[WARN] No empty baseline found. Run --capture-empty-baseline for best accuracy.
```

## Model

- Model production mac dinh:
  - `models/parking_v8s_e15_best.pt`
- Model base / fallback train:
  - `models/yolov8s.pt`
- Model cu giu lai de doi chieu:
  - `models/parking_v8s_best.pt`

Dataset hien tai:

```text
dataset_roboflow/data.yaml
0: empty
1: occupied
```

Khong archive/xoa model trong lan nay.

## Logic nhan dang

1. Board visibility / NO_BOARD
   - Dung `parkingvision_board_lock_9zones.json` lam cache board.
   - Cache luon duoc validate lai tren frame hien tai.
   - Board area, mark ratio va confidence khong dat thi vao `NO_BOARD`.
   - Mat board lien tiep 2 frame thi clear slot state.

2. YOLO evidence
   - Detection phai dung class, confidence du cao.
   - Detection phai overlap voi vung hoac center nam trong vung.
   - Detection ngoai 9 vung bi bo qua.
   - Mac dinh YOLO khong tu quyet OCCUPIED neu khong co bang chung visual/baseline di kem.

3. Empty baseline diff
   - Warp board ve mat phang chuan `1000x650`.
   - So sanh tung vung hien tai voi `empty_baseline_9zones.jpg`.
   - Chi tinh inner ROI, cat bot vien/vach o.
   - Mask vang/trang de vachtang, chu, watermark khong thanh xe.
   - Yeu cau diff area, contour area va color diff deu du lon.
   - Thay doi sang/toi dong deu ca ROI se bi xem la thay doi anh sang, khong tinh la xe.

4. Visual fallback khong baseline
   - Rat than trong.
   - Loai vach vang, chu trang, mui ten, watermark, nen den phang.
   - Can blob vat the day/du lon moi tang diem.
   - Tin hieu yeu bi cap diem thap nen khong the tu bien slot trong thanh OCCUPIED.
   - Zone 6/7 dung inner ROI hep hon va nguong baseline/edge cao hon de tranh false positive tu vach vang doc va bong sang.

5. Hysteresis
   - EMPTY -> OCCUPIED can 3 frame lien tiep.
   - OCCUPIED -> EMPTY can 4 frame lien tiep.
   - NO_BOARD clear state nhanh, khong giu ghost occupied.

Threshold chinh trong `run_droidcam_v8s_boardlock.py`:

```text
BOARD_CONF_THRES
BOARD_LOST_CONFIRM_FRAMES
YOLO_CONF_THRES
YOLO_OVERLAP_THRES
VISUAL_AREA_THRES
VISUAL_CONTOUR_THRES
BASELINE_DIFF_THRES
BASELINE_DIFF_RATIO_THRES
BASELINE_CONTOUR_RATIO_THRES
BASELINE_COLOR_DIFF_THRES
OCCUPIED_CONFIRM_FRAMES
EMPTY_CONFIRM_FRAMES
```

## Chay realtime

Camera index:

```powershell
python run_droidcam_v8s_boardlock.py --source 0
python run_droidcam_v8s_boardlock.py --source 1
```

DroidCam URL:

```powershell
python run_droidcam_v8s_boardlock.py --source http://192.168.1.11:4747/video
```

RTSP:

```powershell
python run_droidcam_v8s_boardlock.py --source rtsp://username:password@ip:port/path
```

Debug tung vung:

```powershell
python run_droidcam_v8s_boardlock.py --source 0 --debug-slots
```

Debug se in:

```text
[ZONE 2] yolo=0.00 overlap=0.00 diff=0.030 contour=0.012 visual=0.10 raw=EMPTY stable=EMPTY
```

Trong cua so realtime:

- `Q`: thoat.
- `R`: reset board lock + smoothing.

## Test anh tinh

Anh dataset mac dinh:

```powershell
python TEST_IMAGE_FINAL.py
```

Anh board 9 vung:

```powershell
python TEST_IMAGE_FINAL.py .\reference_9zones_board.jpg --mode boardlock --out parkingvision_test_output.png
```

Debug anh tinh:

```powershell
python TEST_IMAGE_FINAL.py .\reference_9zones_board.jpg --mode boardlock --debug-slots --show-conf
```

## Train 15 epoch GPU neu that su can

Chi train sau khi da:

- Kiem tra template 9 vung dung.
- Tao `empty_baseline_9zones.jpg`.
- Xac nhan NO_BOARD dung.
- Xac nhan false OCCUPIED khong do threshold/logic.

Lenh:

```powershell
python TRAIN_V8S_5EPOCH_GPU.py
```

Lenh YOLO tuong duong:

```powershell
yolo detect train model=models/parking_v8s_e15_best.pt data=dataset_roboflow/data.yaml epochs=15 imgsz=640 batch=-1 device=0 workers=4 name=parking_v8s_e15 exist_ok=True
```

Script backup truoc khi ghi de:

```text
models/parking_v8s_e15_best.pt -> models/parking_v8s_e15_best.backup.pt
runs/detect/parking_v8s_e15/weights/best.pt -> models/parking_v8s_e15_best.pt
```

## Checklist demo

- Bai trong: `Empty = 9`, `Occupied = 0`, `Total = 9`.
- Xe o vung 1: chi vung 1 la `OCCUPIED`.
- Xe o vung 2: chi vung 2 la `OCCUPIED`.
- Xe o bat ky vung nao: vung do la `OCCUPIED`.
- Vung trong luon la `EMPTY`.
- Dua camera ra khoi bai: hien `NO_BOARD`, khong ve nhan dang.

## Tham khao DATN zip

Da doc `DATN-ParkingYolo-main.zip` chi de tham khao y tuong:

- Tach luong image/camera.
- Confidence threshold va NMS.
- Dem Empty/Occupied/Total tu ket qua cuoi.
- Overlay thong tin len frame.

Khong dung YOLOv3/Darknet, khong copy code cu, khong sua file zip goc.

