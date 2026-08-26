# Parking Space Detection

## 1. Giới thiệu
Dự án Parking Space Detection là một hệ thống nhận diện và giám sát bãi đỗ xe thông minh. Hệ thống bao gồm một ứng dụng Desktop (Desktop App) để trực tiếp xử lý hình ảnh, video hoặc luồng camera nhằm nhận diện xe, và một trang quản trị (Dashboard) để theo dõi thống kê, quản lý dữ liệu bãi đỗ xe một cách trực quan.

## 2. Chức năng chính
- Đăng nhập và quản lý phiên làm việc.
- Nhận dạng vị trí đỗ xe từ hình ảnh tĩnh (Image).
- Nhận dạng vị trí đỗ xe từ video (Video).
- Nhận dạng thời gian thực từ Webcam máy tính hoặc DroidCam qua điện thoại.
- Xác định và cập nhật trạng thái từng vị trí (trống - EMPTY, hoặc có xe - OCCUPIED).
- Theo dõi thời gian đỗ xe thực tế của từng phương tiện.
- Tính phí đỗ xe tự động dựa trên thời gian.
- Lưu trữ lịch sử đỗ xe vào cơ sở dữ liệu.
- Dashboard quản trị nền web hiển thị số liệu tổng quan, xe đang đỗ, xe đã rời và lịch sử hoạt động.

## 3. Kiến trúc và luồng hoạt động
Hệ thống hoạt động theo mô hình xử lý tập trung vào Desktop App kết hợp hiển thị qua Dashboard:
- **Desktop App**: 
  - Người dùng chọn nguồn đầu vào (Image, Video, Webcam/DroidCam).
  - Chọn model AI tương ứng (YOLO11 cho Image/Video, YOLOv8s cho Webcam/DroidCam).
  - Hệ thống xử lý khung hình, xác định trạng thái từng vị trí dựa trên cấu hình cho trước.
  - Tính toán thời gian đỗ, phí đỗ xe và lưu toàn bộ dữ liệu vào cơ sở dữ liệu MySQL.
- **Dashboard**:
  - Đọc dữ liệu từ cơ sở dữ liệu và hiển thị giao diện thống kê quản trị.
  - Theo dõi danh sách xe đang đỗ, xe đã rời, doanh thu và lịch sử nhận dạng.

## 4. Cấu trúc thư mục
- `Assets/`: Chứa các hình ảnh, video và tài nguyên giao diện của dự án.
- `database/`: Chứa script khởi tạo cơ sở dữ liệu (`ai_parking_system.sql`).
- `ParkingSpaceDesktopApp/`: Chứa mã nguồn chính của ứng dụng Desktop và luồng xử lý nhận dạng tĩnh.
- `ParkingVisionV8/`: Chứa luồng xử lý nhận dạng thời gian thực bằng Webcam/DroidCam và các script huấn luyện.
- `src/`, `scripts/`: Chứa mã nguồn nền tảng, kịch bản phụ trợ.
- `tests/`, `performance_tests/`: Chứa mã kiểm thử.
- `README.md`: Tài liệu hướng dẫn sử dụng dự án.
- `requirements.txt`, `requirements-gpu.txt`: Danh sách các thư viện cần cài đặt.

## 5. Tài nguyên không có trong bản nộp
Do giới hạn dung lượng bản nộp (tối đa 100 MB), các tệp có dung lượng lớn dưới đây đã được loại khỏi bản nộp:
- `yolo11n-seg.pt` (Mô hình YOLO11 Nano Segmentation)
- `yolo11x-seg.pt` (Mô hình YOLO11 Extra Large Segmentation)
- `yolov8s.pt` (Mô hình YOLOv8 Small gốc)
- Thư mục `Assets/` (Chứa tài nguyên giao diện, video/ảnh mẫu)
- Thư mục `ParkingVisionV8/dataset_roboflow/` (Dữ liệu huấn luyện mô hình)
- Thư mục `ParkingVisionV8/models/` (Các mô hình YOLOv8s đã huấn luyện)

## 6. Khôi phục đầy đủ dự án
Để hệ thống có thể hoạt động đầy đủ, người dùng phải tải và khôi phục các tệp tin bị thiếu:
1. Tải toàn bộ tài nguyên từ link Drive: [Tải đầy đủ model, dataset và Assets từ Google Drive](https://drive.google.com/drive/folders/1z-igzkGXup0rTt-_ibrZ0U7bTO-X37VW?usp=sharing)
2. Giải nén các tệp nếu chúng ở định dạng nén.
3. Chép `yolo11n-seg.pt`, `yolo11x-seg.pt`, `yolov8s.pt` vào thư mục gốc của dự án.
4. Chép thư mục `Assets` vào thư mục gốc của dự án.
5. Chép `dataset_roboflow` và `models` vào trong thư mục `ParkingVisionV8/`.
6. Kiểm tra lại cấu trúc sau khi sao chép. Tuyệt đối không đặt lồng thêm một thư mục cùng tên, ví dụ `ParkingVisionV8/ParkingVisionV8/models` là sai.

Cấu trúc chuẩn sau khi khôi phục:
```text
ParkingSpaceDetection/
├── Assets/
├── yolo11n-seg.pt
├── yolo11x-seg.pt
├── yolov8s.pt
└── ParkingVisionV8/
    ├── dataset_roboflow/
    └── models/
```

## 7. Yêu cầu hệ thống
- **Hệ điều hành**: Windows 10/11.
- **Python**: Phiên bản 3.9 đến 3.11.
- **Cơ sở dữ liệu**: MySQL (khuyến nghị dùng Laragon hoặc XAMPP).
- **Phần cứng**: Khuyến nghị có GPU NVIDIA (hỗ trợ CUDA) để tăng tốc độ nhận dạng, RAM từ 8GB trở lên.
- **Phần mềm khác**: Ứng dụng DroidCam (nếu dùng điện thoại làm Webcam).

## 8. Cài đặt môi trường
Sử dụng PowerShell để thiết lập môi trường và cài đặt thư viện:

```powershell
cd D:\Project\ParkingSpaceDetection
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```
Nếu máy tính của bạn có GPU NVIDIA, hãy cài đặt thêm các thư viện hỗ trợ GPU bằng tệp `requirements-gpu.txt`:
```powershell
pip install -r requirements-gpu.txt
```

## 9. Cấu hình database
Hệ thống sử dụng MySQL làm cơ sở dữ liệu mặc định.
- **Tên cơ sở dữ liệu**: `ai_parking_system`
- **Import CSDL**: Bạn cần tạo database trong MySQL và import tệp `database/ai_parking_system.sql`.
- **Cấu hình kết nối**: Ứng dụng kết nối database thông qua các biến môi trường hoặc tài khoản mặc định. Các thông số cấu hình mặc định trong mã nguồn (có thể thay đổi bằng biến môi trường như `AI_PARKING_DB_HOST`):
  - `host = 127.0.0.1` (localhost)
  - `port = 3306`
  - `user = root`
  - `password = ` (để trống)
  - `database = ai_parking_system`

## 10. Chạy Desktop App
Đây là ứng dụng chính để bạn nhận dạng bãi đỗ xe.
Lệnh chạy ứng dụng (đảm bảo đã kích hoạt môi trường ảo `.venv`):
```powershell
python ParkingSpaceDesktopApp\run_desktop_app.py
```
Các bước sử dụng:
1. Đăng nhập hệ thống bằng tài khoản.
2. Chọn nguồn đầu vào (Image, Video hoặc Webcam).
3. Chọn model phù hợp cho thiết lập.
4. Chọn tệp ảnh/video hoặc thiết bị camera tương ứng.
5. Nhấn RUN để hệ thống bắt đầu.
6. Theo dõi thống kê trạng thái các vị trí trên màn hình.
7. Nhấn STOP khi muốn dừng.
8. Xem kết quả xuất ra (nếu có).
9. Đăng xuất khỏi hệ thống.

## 11. Sử dụng chế độ Image
- Chế độ này dùng để phân tích một ảnh tĩnh từ bãi đỗ xe.
- Cần chọn ảnh đầu vào và sử dụng model YOLO11 Segmentation (`yolo11n-seg.pt` hoặc `yolo11x-seg.pt`).
- Khi nhấn RUN, kết quả phân tích từng vị trí sẽ xuất hiện và có thể được tự động lưu trạng thái vào cơ sở dữ liệu (tùy thuộc vào thiết lập xử lý).

## 12. Sử dụng chế độ Video
- Dùng để phân tích trạng thái bãi đỗ xe liên tục từ một tệp video quay sẵn.
- Nên chọn model YOLO11 để xử lý.
- Trạng thái các ô đỗ sẽ cập nhật liên tục, thời gian xe vào/ra sẽ được tính toán ngay trong thời gian thực (realtime), sau đó phí cũng sẽ được đồng bộ.

## 13. Sử dụng Webcam/DroidCam
Chế độ phân tích bằng luồng hình ảnh trực tiếp từ camera.
- **Hướng dẫn kết nối**: Bạn cần mở ứng dụng DroidCam trên cả điện thoại và máy tính, tiến hành kết nối. Trên Desktop App, chọn thiết bị camera có chỉ số phù hợp (thường là 0 hoặc 1) qua nút kiểm tra DroidCam.
- Chọn model dòng YOLOv8s từ `ParkingVisionV8` để tối ưu FPS. Nhấn RUN để xử lý.
- Ngoài ra, bạn cũng có thể chạy lệnh phân tích DroidCam thời gian thực độc lập thông qua script của dự án:
```powershell
python ParkingVisionV8\run_droidcam_v8s_boardlock.py --source 0
```
*(Lưu ý: Không viết `--source = 0`, cú pháp đúng là `--source 0`)*

## 14. Chạy Dashboard quản trị
Dashboard quản trị dùng để theo dõi, xem báo cáo tổng quan tình trạng bãi đỗ.
Chạy bằng lệnh:
```powershell
streamlit run ParkingSpaceDesktopApp\streamlit_dashboard.py
```
Sau đó mở trình duyệt và truy cập vào: `http://localhost:8501`

Các màn hình có trong Dashboard:
- **Tổng quan**: Số liệu chung.
- **Xe đang đỗ**: Các xe đang nằm trong bãi.
- **Xe đã rời**: Các xe đã hoàn thành phiên đỗ và thanh toán.
- **Lịch giám sát** (hoặc Lịch sử): Lịch sử nhận dạng đầy đủ các phiên làm việc.

## 15. Model và chế độ sử dụng

| Chế độ | Model | Mục đích |
|---|---|---|
| **Image / Video** | YOLO11 Segmentation (`yolo11n-seg.pt`, `yolo11x-seg.pt`) | Phân tích ảnh và video với độ chính xác cao. |
| **Webcam / DroidCam** | YOLOv8s gốc hoặc đã huấn luyện (`yolov8s.pt`, mô hình trong `ParkingVisionV8/models/`) | Nhận dạng luồng trực tiếp với hiệu năng tốt. |

## 16. Dữ liệu đầu ra
- **Hình ảnh/Video kết quả**: Nằm trong thư mục `ParkingSpaceDesktopApp/desktop_outputs/` hoặc tương tự.
- **Lịch sử đỗ xe & thông tin phí**: Được đồng bộ liên tục vào các bảng trong MySQL (database).

## 17. Cách tính trạng thái và thanh toán
- **Trạng thái**: Thuật toán đánh giá và gán vị trí là `EMPTY` (trống) hoặc `OCCUPIED` (có xe đỗ).
- **Thời gian**: Hệ thống lưu lại thời gian vào bãi (Check-in). Khi xe rời vị trí, ghi nhận thời gian ra (Check-out) để ra tổng thời gian đỗ.
- **Thanh toán**: Tạm tính và làm tròn mức phí đỗ xe theo cấu hình nội bộ. Phí đã thu sẽ hiển thị trong lịch sử.

## 18. Các lỗi thường gặp
- **Lỗi thiếu file model (.pt)**: Do chưa sao chép model vào đúng thư mục sau khi tải từ Drive. Xác minh lại với cây thư mục mẫu.
- **Lỗi thiếu thư viện**: Gây ra lỗi import như `ultralytics`. Khắc phục bằng cách chạy lệnh `pip install -r requirements.txt`.
- **Không mở được Camera / DroidCam**: Camera index không tồn tại hoặc ứng dụng DroidCam chưa kết nối. Khắc phục bằng cách kiểm tra cáp mạng/WiFi, đổi `--source 0` thành chỉ số camera đúng.
- **Chọn nhầm model**: Lỗi xảy ra nếu dùng YOLOv8 cho tiến trình yêu cầu YOLO11 Segmentation (hoặc ngược lại). Đảm bảo chọn model đúng tính năng.
- **Lỗi không kết nối được database (MySQL)**: Triệu chứng là lỗi ứng dụng không chạy hoặc không đăng nhập được. Khắc phục bằng cách bật MySQL và kiểm tra CSDL `ai_parking_system`.
- **Dashboard không có dữ liệu**: Khắc phục bằng cách mở Desktop App và phân tích video/hình ảnh để nạp dữ liệu vào database.
- **Sai cấu trúc folder sau khi giải nén**: Tạo ra các thư mục lồng nhau như `Assets/Assets` khiến mã nguồn không đọc được. Cần di chuyển lại cho đúng.
- **Cổng 8501 đang được sử dụng**: Do phiên Streamlit trước chưa đóng, dùng Task Manager tắt ứng dụng Python đang chạy ngầm rồi mở lại.

## 19. Lưu ý khi nộp course
- Bản nộp này tuân thủ quy định dưới 100 MB, do đó không bao gồm tài nguyên lớn.
- Người chấm/kiểm tra mã nguồn bắt buộc phải tải dữ liệu từ Google Drive đã cung cấp.
- Phải khôi phục đúng cấu trúc thư mục trước khi chạy, mã nguồn hệ thống vẫn nằm nguyên vẹn trong bản nộp.
- Không được đổi tên model hoặc folder vì các thành phần trong mã nguồn đã tham chiếu trực tiếp.

## 20. Giấy phép
Dự án này được phân phối dưới giấy phép Apache License 2.0.
