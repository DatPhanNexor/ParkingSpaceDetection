# Desktop App Demo Guide

`ParkingSpaceDesktopApp` la dashboard chinh de demo do an. App co 3 mode va moi mode bi khoa dung loai model de tranh chon nham.

## Model theo mode

| Mode | Model mac dinh | Vi tri |
| --- | --- | --- |
| Image | `yolo11n-seg.pt` | Root project |
| Video | `yolo11n-seg.pt` | Root project |
| Webcam/DroidCam | `parking_v8s_e15_best.pt` | `ParkingVisionV8/models/` |

Khi doi `Input`, dropdown model se tu loc:

- `Image`/`Video`: chi hien `yolo11n-seg.pt`.
- `Webcam`: hien cac model V8 hop le, uu tien `parking_v8s_e15_best.pt`.

Neu mot mode nhan model sai, app tu chuyen ve model dung va ghi log.

## ParkingVisionV8 boardlock

Webcam/DroidCam khong spawn cua so OpenCV rieng. App chi doc logic/config tu `ParkingVisionV8`:

```text
ParkingVisionV8/run_droidcam_v8s_boardlock.py
ParkingVisionV8/parkingvision_board_lock_9zones.json
ParkingVisionV8/parkingvision_slots_template_9zones.json
ParkingVisionV8/empty_baseline_9zones.jpg
ParkingVisionV8/models/parking_v8s_e15_best.pt
```

Board mini hien dung `Total = 9`, lay truc tiep tu `parkingvision_slots_template_9zones.json` la cau hinh canonical. Empty/Occupied/Total duoc tra ve dashboard. Neu board khong visible, app hien frame nhung ket qua duoc danh dau khong hop le thay vi tinh nhu mot phep do occupancy.

## Chay app

**Ứng dụng nhận diện AI Desktop:**
```powershell
cd D:\Project\ParkingSpaceDetection
.\.venv\Scripts\Activate.ps1
& ".\.venv\Scripts\python.exe" ParkingSpaceDesktopApp\run_desktop_app.py
```

**Dashboard quản lý Streamlit:**
```powershell
& ".\.venv\Scripts\python.exe" -m streamlit run ParkingSpaceDesktopApp\streamlit_dashboard.py
```

**Database:**
- Mở Laragon.
- Start MySQL.
- Import `database\ai_parking_system.sql` bằng phpMyAdmin.

## Demo nhanh

### Image

1. Chon `Input = Image`.
2. Model tu dong la `yolo11n-seg.pt`.
3. Bam `Choose file`.
4. Bam `RUN`.

### Video

1. Chon `Input = Video`.
2. Model tu dong la `yolo11n-seg.pt`.
3. Chon video demo hoac `Choose file`.
4. Bam `RUN`, bam `STOP` neu can.

### Webcam/DroidCam

1. Chon `Input = Webcam`.
2. Chon camera `0/1/2` hoac nhap URL DroidCam/RTSP, vi du `http://192.168.1.11:4747/video`.
3. Model tu dong la `parking_v8s_e15_best.pt`.
4. Bam `Scan camera` de app thu `0`, `1`, `2`, `/video`, `/mjpegfeed` va RTSP pho bien.
5. Bam `RUN`.

DroidCam/RTSP co the nhap truc tiep:

```text
http://192.168.1.11:4747/video
http://192.168.1.11:4747/mjpegfeed
rtsp://192.168.1.11:4747/video
rtsp://192.168.1.11:8554/live
```

Neu chon `cuda` nhung may khong co CUDA kha dung, app tu fallback sang `cpu` va ghi log tren UI.

## Output

```text
ParkingSpaceDesktopApp/desktop_outputs/
  images/
  videos/
  csv/
  app.log
```

Nut `Open outputs` mo dung thu muc nay.

## Tinh phi do xe

- Billing chi hoat dong trong `Video` va `Webcam/DroidCam`; `Image` giu preview toan chieu ngang va khong tinh phi.
- Webcam dung ID vat ly `S01`-`S09` tu template 9 vung va dong ho monotonic. Video chi theo doi `parked_vehicle_boxes` trong parking map, gan track tam thoi `V01`, `V02`, ... va dung timeline cua video.
- Mac dinh 20.000 VND/gio, lam tron len boi 5.000 VND, toi thieu 5.000 VND. Doanh thu chi tang sau chuyen trang thai on dinh `OCCUPIED -> EMPTY`; STOP, mat board, frame invalid hay video ket thuc khong tu dong thu phi xe con dang do.
- Khi bat `History`, giao dich da hoan thanh duoc append UTF-8 vao `desktop_outputs/csv/billing_transactions.csv`. Active session chi hien tam tinh va khong duoc ghi CSV.

## Loi thuong gap

- Thieu `yolo11n-seg.pt`: Image/Video se bao loi model.
- Thieu `parking_v8s_e15_best.pt`: Webcam/DroidCam se bao loi model V8.
- Camera khong mo duoc: thu camera `0/1/2`, dong app khac dang giu camera, hoac dung DroidCam URL co duoi `/video`.
- Board mini khong thay: kiem tra goc camera, anh sang, va `parkingvision_board_lock_9zones.json`.
