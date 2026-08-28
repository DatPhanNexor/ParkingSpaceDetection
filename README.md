# AI-Powered Smart Parking Monitoring and Management System

> **Xây dựng hệ thống giám sát và quản lý bãi đỗ xe thông minh ứng dụng trí tuệ nhân tạo**

`ParkingSpaceDetection` là hệ thống Smart Parking tích hợp **Computer Vision, Desktop Application, Web Dashboard, Flutter Mobile Application, Backend Microservices, MySQL, Redis, RabbitMQ, Docker và CI/CD**.

Hệ thống sử dụng các mô hình **YOLO kết hợp OpenCV** để xử lý Image, Video và Camera thời gian thực; xác định trạng thái 9 vị trí đỗ xe từ `S01` đến `S09`; quản lý vòng đời phiên đỗ; tính thời gian và chi phí; lưu trữ lịch sử; thống kê doanh thu; đồng thời cung cấp dữ liệu cho Desktop App, Streamlit Dashboard và Flutter Mobile App.

---

## 1. Mục lục

- [1. Tổng quan](#2-tổng-quan)
- [2. Mục tiêu dự án](#3-mục-tiêu-dự-án)
- [3. Phạm vi hệ thống](#4-phạm-vi-hệ-thống)
- [4. Kiến trúc tổng thể](#5-kiến-trúc-tổng-thể)
- [5. Công nghệ sử dụng](#6-công-nghệ-sử-dụng)
- [6. Luồng nghiệp vụ chính](#7-luồng-nghiệp-vụ-chính)
- [7. AI và Computer Vision](#8-ai-và-computer-vision)
- [8. Parking Session và Billing](#9-parking-session-và-billing)
- [9. Backend và Microservices](#10-backend-và-microservices)
- [10. MySQL](#11-mysql)
- [11. Redis](#12-redis)
- [12. RabbitMQ](#13-rabbitmq)
- [13. Authentication và RBAC](#14-authentication-và-rbac)
- [14. Streamlit Dashboard](#15-streamlit-dashboard)
- [15. Flutter Mobile App](#16-flutter-mobile-app)
- [16. Cấu trúc thư mục](#17-cấu-trúc-thư-mục)
- [17. Model và Dataset](#18-model-và-dataset)
- [18. Tài nguyên dung lượng lớn](#19-tài-nguyên-dung-lượng-lớn)
- [19. Yêu cầu hệ thống](#20-yêu-cầu-hệ-thống)
- [20. Cài đặt Python](#21-cài-đặt-python)
- [21. Cấu hình MySQL](#22-cấu-hình-mysql)
- [22. Chạy Desktop App](#23-chạy-desktop-app)
- [23. Image Mode](#24-image-mode)
- [24. Video Mode](#25-video-mode)
- [25. Webcam / DroidCam](#26-webcam--droidcam)
- [26. Chạy Dashboard](#27-chạy-dashboard)
- [27. Chạy Flutter Android](#28-chạy-flutter-android)
- [28. Android Emulator](#29-android-emulator)
- [29. Backend từ Android Emulator](#30-backend-từ-android-emulator)
- [30. Testing](#31-testing)
- [31. Docker và CI/CD](#32-docker-và-cicd)
- [32. Logging và Security](#33-logging-và-security)
- [33. Troubleshooting](#34-troubleshooting)
- [34. Quy trình Demo](#35-quy-trình-demo)
- [35. Phạm vi mở rộng](#36-phạm-vi-mở-rộng)
- [36. Lưu ý khi nộp Course / GitHub](#37-lưu-ý-khi-nộp-course--github)
- [37. Quick Start](#38-quick-start)
- [38. License](#39-license)

---

# 2. Tổng quan

Ở nhiều bãi đỗ xe, nhân viên vẫn phải quan sát trực tiếp để xác định vị trí còn trống, ghi nhận thời gian xe vào/ra và tính phí.

Cách quản lý thủ công có một số hạn chế:

- phụ thuộc vào người vận hành;
- tốn thời gian;
- dễ xảy ra sai sót;
- khó thống kê chính xác;
- khó theo dõi lịch sử;
- khó giám sát từ xa;
- chưa tận dụng hiệu quả hệ thống camera có sẵn.

Dự án `ParkingSpaceDetection` giải quyết bài toán trên bằng cách kết hợp:

```text
Computer Vision
      +
Parking Management
      +
Automatic Billing
      +
Desktop Application
      +
Web Dashboard
      +
Flutter Mobile
      +
Backend API
      +
Realtime WebSocket
      +
MySQL / Redis / RabbitMQ
      +
Docker / CI/CD
```

---

# 3. Mục tiêu dự án

Mục tiêu của hệ thống là xây dựng một nền tảng Smart Parking có khả năng:

- nhận dạng phương tiện từ ảnh;
- nhận dạng phương tiện từ video;
- nhận dạng trạng thái vị trí đỗ xe từ Webcam/DroidCam;
- quản lý 9 vị trí từ `S01` đến `S09`;
- phân loại `EMPTY` và `OCCUPIED`;
- tạo và kết thúc phiên đỗ;
- tính thời gian đỗ;
- tính phí tự động;
- lưu lịch sử;
- thống kê doanh thu;
- cung cấp Dashboard quản trị;
- theo dõi từ xa bằng Flutter Mobile;
- cung cấp RESTful API;
- cập nhật realtime bằng WebSocket;
- xác thực JWT;
- phân quyền `admin` và `staff`;
- sử dụng Redis cho dữ liệu truy cập nhanh;
- truyền sự kiện bằng RabbitMQ;
- hỗ trợ Docker;
- tự động kiểm thử bằng GitHub Actions.

---

# 4. Phạm vi hệ thống

Trong phạm vi đồ án, hệ thống quản lý cố định:

```text
S01
S02
S03
S04
S05
S06
S07
S08
S09
```

Mỗi vị trí có hai trạng thái chính:

| Trạng thái | Ý nghĩa           |
| ---------- | ----------------- |
| `EMPTY`    | Vị trí đang trống |
| `OCCUPIED` | Vị trí đang có xe |

Hệ thống ưu tiên độ chính xác và tính ổn định của trạng thái hơn việc phản ứng với một frame đơn lẻ.

---

# 5. Kiến trúc tổng thể

```text
                         ┌──────────────────────┐
                         │ Image / Video / Cam  │
                         │ Webcam / DroidCam    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │  AI Detection Layer  │
                         │ YOLO11 / YOLOv8s     │
                         │ OpenCV               │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Parking State Engine │
                         │ S01 ... S09          │
                         │ Board Lock           │
                         │ Smoothing/Hysteresis │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Parking & Billing    │
                         │ Session / Time / Fee │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
                ┌───────┐       ┌───────┐      ┌─────────┐
                │ MySQL │       │ Redis │      │RabbitMQ │
                └───┬───┘       └───┬───┘      └────┬────┘
                    │               │                │
                    └───────────────┼────────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       FastAPI        │
                         │ REST + WebSocket     │
                         │ JWT + RBAC           │
                         └──────────┬───────────┘
                                    │
                   ┌────────────────┼─────────────────┐
                   │                │                 │
                   ▼                ▼                 ▼
             Desktop App       Streamlit         Flutter
                               Dashboard          Mobile
```

---

# 6. Công nghệ sử dụng

## AI / Computer Vision

- Python
- OpenCV
- PyTorch
- Ultralytics YOLO
- YOLO11 Segmentation
- YOLOv8s
- NumPy
- Roboflow
- ROI
- Perspective Transformation
- Board Lock
- Object Tracking
- Temporal Smoothing
- Hysteresis

## Desktop Application

- Python
- CustomTkinter
- Pillow
- OpenCV VideoCapture

## Dashboard

- Streamlit
- Pandas
- Plotly

## Mobile

- Flutter
- Dart
- REST API Client
- WebSocket Client
- Secure Storage
- JWT Authentication
- Android SDK 36

## Backend

- Python
- FastAPI
- Pydantic
- Uvicorn
- RESTful API
- WebSocket
- JWT
- RBAC

## Database & Messaging

- MySQL
- Laragon
- phpMyAdmin
- Redis
- RabbitMQ
- Pika hoặc aio-pika
- Retry Queue
- Dead Letter Queue

## DevOps & Testing

- Docker
- Docker Compose
- GitHub
- GitHub Actions
- Pytest
- Unit Test
- Integration Test
- API Test
- Performance Test

---

# 7. Luồng nghiệp vụ chính

Luồng demo đầy đủ của hệ thống:

```text
Đăng nhập
    │
    ▼
Chọn Image / Video / Webcam / DroidCam
    │
    ▼
AI nhận dạng
    │
    ▼
Xác định trạng thái S01 - S09
    │
    ▼
EMPTY / OCCUPIED
    │
    ▼
Parking Session
    │
    ▼
Tính thời gian và phí
    │
    ▼
MySQL
    │
    ├────────► Redis
    │
    └────────► RabbitMQ
                 │
                 ▼
              FastAPI
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
    Desktop   Dashboard   Flutter
```

---

# 8. AI và Computer Vision

Hệ thống hỗ trợ ba chế độ xử lý.

## 8.1 Image

Image Mode sử dụng **YOLO11 Segmentation**.

Kết quả có thể bao gồm:

- vị trí phương tiện;
- segmentation mask;
- class label;
- confidence;
- số lượng phương tiện;
- ảnh đã annotate.

> **Quan trọng:** Image Mode chỉ phân tích trạng thái tại một thời điểm. Nó không tự động tạo Parking Session và không tự động tính phí.

Model:

```text
yolo11n-seg.pt
yolo11x-seg.pt
```

---

## 8.2 Video

Video Mode sử dụng YOLO11 Segmentation để xử lý từng frame.

Hỗ trợ:

- phát hiện phương tiện;
- phân vùng phương tiện;
- theo dõi thay đổi theo thời gian;
- cập nhật trạng thái slot;
- tạo Parking Session;
- kết thúc Parking Session;
- tính duration;
- tính fee;
- xuất video;
- xuất CSV;
- lưu lịch sử.

---

## 8.3 Webcam / DroidCam

Realtime Mode sử dụng YOLOv8s đã huấn luyện để phân loại:

```text
EMPTY
OCCUPIED
```

Hệ thống sử dụng Board Lock để cố định 9 vùng `S01`–`S09`.

Các cơ chế ổn định bao gồm:

- confidence threshold;
- confirmation frames;
- Temporal Smoothing;
- Hysteresis;
- Board Lock validation.

Trạng thái không được thay đổi chỉ vì một frame nhận dạng bất thường.

Nếu:

- camera mất tín hiệu;
- frame không hợp lệ;
- Board Lock tạm thời không xác định được;

hệ thống không được tự động xem đó là sự kiện xe đã rời vị trí.

---

# 9. Parking Session và Billing

## 9.1 EMPTY → OCCUPIED

Khi trạng thái ổn định chuyển:

```text
EMPTY
  ↓
OCCUPIED
```

hệ thống:

1. kiểm tra slot đã có active session chưa;
2. sinh session ID duy nhất;
3. ghi nhận slot ID;
4. ghi nhận `start_time`;
5. tạo active Parking Session;
6. cập nhật Redis;
7. lưu dữ liệu cần thiết vào MySQL.

Một slot chỉ được có **một active Parking Session** tại cùng một thời điểm.

---

## 9.2 Khi xe đang đỗ

Hệ thống cập nhật:

- elapsed time;
- estimated fee;
- current status;
- last update time.

---

## 9.3 OCCUPIED → EMPTY

Khi trạng thái chuyển ổn định:

```text
OCCUPIED
    ↓
 EMPTY
```

hệ thống:

1. ghi nhận `end_time`;
2. tính parking duration;
3. áp dụng quy tắc làm tròn;
4. tính phí;
5. áp dụng minimum fee nếu có;
6. kết thúc session;
7. cập nhật doanh thu;
8. lưu lịch sử;
9. cập nhật Redis;
10. phát event cần thiết.

---

# 10. Backend và Microservices

Kiến trúc logic gồm các service chính.

## Authentication Service

Chịu trách nhiệm:

- login;
- password verification;
- Access Token;
- Refresh Token;
- JWT;
- user role;
- authorization.

## AI Detection Service

Chịu trách nhiệm:

- xử lý/tiếp nhận detection;
- chuẩn hóa kết quả AI;
- phát event;
- truyền trạng thái mới đến hệ thống nghiệp vụ.

## Parking and Billing Service

Chịu trách nhiệm:

- parking slot;
- Parking Session;
- state transition;
- duration;
- fee;
- duplicate prevention;
- MySQL;
- Redis;
- RabbitMQ events.

## Dashboard and Reporting Service

Chịu trách nhiệm:

- dashboard data;
- history;
- revenue;
- slot statistics;
- utilization;
- reports.

---

# 11. MySQL

MySQL là **Source of Truth** của hệ thống.

Database:

```text
ai_parking_system
```

Script khởi tạo:

```text
database/ai_parking_system.sql
```

Dữ liệu gồm:

- users;
- roles;
- parking slots;
- slot states;
- active sessions;
- completed sessions;
- check-in/check-out;
- parking duration;
- fee;
- revenue;
- billing configuration;
- activity history;
- system/error logs cần thiết.

Thông số development mặc định:

```text
Host     : 127.0.0.1
Port     : 3306
User     : root
Password :
Database : ai_parking_system
```

Nên sử dụng environment variables thay cho hard-code.

Ví dụ:

```env
AI_PARKING_DB_HOST=127.0.0.1
AI_PARKING_DB_PORT=3306
AI_PARKING_DB_USER=root
AI_PARKING_DB_PASSWORD=
AI_PARKING_DB_NAME=ai_parking_system
```

---

# 12. Redis

Redis được dùng cho dữ liệu truy cập nhanh:

- trạng thái S01–S09;
- tổng EMPTY/OCCUPIED;
- active sessions;
- elapsed time;
- estimated fee;
- last update;
- processed event IDs;
- temporary locks;
- session/refresh state khi cần.

Redis không thay thế MySQL.

```text
MySQL = Source of Truth
Redis = Cache / Realtime State
```

Khi Redis restart, hệ thống phải có khả năng khôi phục trạng thái cần thiết từ MySQL.

---

# 13. RabbitMQ

RabbitMQ dùng để truyền sự kiện giữa các service.

Các event chính:

```text
detection.completed
detection.failed
parking.slot.updated
parking.session.started
parking.session.completed
billing.completed
```

Mỗi event cần có ID duy nhất để hỗ trợ idempotency.

Luồng:

```text
AI Detection
     │
     ▼
 RabbitMQ
     │
     ▼
Parking/Billing
     │
     ├──► Redis
     └──► MySQL
             │
             ▼
      Dashboard / Mobile
```

Cơ chế lỗi:

```text
Message
   │
   ▼
Processing
   │
   ├── Success ──► ACK
   │
   └── Failure
          │
          ▼
        Retry
          │
          ▼
   Retry exhausted
          │
          ▼
 Dead Letter Queue
```

---

# 14. Authentication và RBAC

Hệ thống có hai role chính.

## Admin

Có thể:

- quản lý tài khoản;
- tạo tài khoản nhân viên;
- khóa/mở tài khoản;
- phân quyền;
- xem trạng thái;
- xem lịch sử;
- xem doanh thu;
- quản lý billing configuration;
- xuất báo cáo;
- xem cảnh báo/lỗi;
- theo dõi từ Mobile.

## Staff

Có thể:

- đăng nhập;
- chọn Image/Video/Webcam;
- chọn model;
- chọn processing device;
- RUN/STOP detection;
- xem trạng thái S01–S09;
- xem duration;
- xem estimated fee;
- lưu Image/Video/CSV;
- theo dõi từ Mobile.

Mật khẩu phải được hash trước khi lưu vào MySQL.

Luồng login:

```text
Username + Password
        │
        ▼
Authentication Service
        │
        ▼
Password Verification
        │
        ▼
Role Validation
        │
        ▼
Access Token + Refresh Token
```

REST API và WebSocket cần được bảo vệ bằng JWT.

---

# 15. Streamlit Dashboard

Dashboard dành cho quản trị viên.

Có thể hiển thị:

- trạng thái 9 slot;
- tổng EMPTY;
- tổng OCCUPIED;
- tổng lượt xe;
- active sessions;
- completed sessions;
- duration;
- estimated fee;
- total revenue;
- revenue by day;
- revenue by slot;
- utilization;
- check-in/check-out history;
- alerts;
- errors.

Có thể lọc theo:

- ngày;
- khoảng thời gian;
- slot;
- trạng thái;
- nguồn detection.

Hỗ trợ xuất CSV theo chức năng được triển khai.

---

# 16. Flutter Mobile App

Flutter Mobile App dành cho Android và có thể mở rộng sang iOS trong tương lai.

Các chức năng thuộc phạm vi đồ án:

- Login;
- Dashboard;
- trạng thái `S01`–`S09`;
- tổng EMPTY/OCCUPIED;
- active sessions;
- parking duration;
- estimated fee;
- completed sessions;
- history;
- revenue;
- slot utilization;
- realtime WebSocket;
- warning/error theo quyền.

Mobile sử dụng:

```text
Flutter
Dart
REST API
WebSocket
JWT
Secure Storage
```

> Mobile App không kết nối trực tiếp MySQL, Redis hoặc RabbitMQ.

Luồng đúng:

```text
Flutter
   │
   ▼
FastAPI
   │
   ├──► MySQL
   ├──► Redis
   └──► RabbitMQ
```

YOLO không chạy trực tiếp trên Mobile.

---

# 17. Cấu trúc thư mục

```text
ParkingSpaceDetection/
│
├── .github/
│   └── workflows/                 # GitHub Actions / CI
│
├── Assets/                        # Image, video, UI resources
│
├── backend_microservices/         # FastAPI / Backend services
│
├── database/
│   └── ai_parking_system.sql      # MySQL schema/init
│
├── Demo/                          # Demo assets / outputs
│
├── docs_tttn/                     # Tài liệu đồ án
│
├── flutter_mobile_app/            # Flutter Android application
│
├── infrastructure/                # Docker / deployment
│
├── ParkingSpaceDesktopApp/        # CustomTkinter Desktop App
│
├── ParkingVisionV8/               # YOLOv8 realtime pipeline
│   ├── dataset_roboflow/
│   └── models/
│
├── performance_tests/             # Performance tests
├── scripts/                       # Utility scripts
├── src/                           # Core/shared source
├── tests/                         # Automated tests
│
├── .gitignore
├── LICENSE
├── pyproject.toml
├── pytest.ini
├── README.md
├── regions.json
├── requirements.txt
├── requirements-gpu.txt
├── run_optimized.py
├── yolo11n-seg.pt
├── yolo11x-seg.pt
└── yolov8s.pt
```

Một số model/dataset có thể không tồn tại trong bản GitHub/course do giới hạn dung lượng.

---

# 18. Model và Dataset

## Model

| Mode            | Model               | Mục đích                 |
| --------------- | ------------------- | ------------------------ |
| Image           | YOLO11 Segmentation | Detection + segmentation |
| Video           | YOLO11 Segmentation | Detection theo frame     |
| Webcam/DroidCam | YOLOv8s trained     | EMPTY/OCCUPIED realtime  |

Model chính:

```text
yolo11n-seg.pt
yolo11x-seg.pt
yolov8s.pt
ParkingVisionV8/models/
```

## Dataset

Dataset YOLOv8s gồm hai class:

```text
empty
occupied
```

Phân chia:

| Dataset    | Số ảnh |
| ---------- | -----: |
| Training   |  2,304 |
| Validation |    334 |
| Test       |    215 |

Các metric đánh giá:

- Precision;
- Recall;
- F1-score;
- mAP@0.5;
- mAP@0.5:0.95;
- empty accuracy;
- occupied accuracy;
- FPS;
- frame processing time;
- CPU usage;
- GPU usage;
- RAM usage;
- false state transitions;
- false session start/end.

---

# 19. Tài nguyên dung lượng lớn

Do giới hạn bản nộp/GitHub, các file lớn có thể không được commit trực tiếp:

```text
yolo11n-seg.pt
yolo11x-seg.pt
yolov8s.pt
Assets/
ParkingVisionV8/dataset_roboflow/
ParkingVisionV8/models/
```

Tải tài nguyên tại:

**Google Drive**

https://drive.google.com/drive/folders/1io11dPbSUOSuhem_q5KYHkGF5cCyGUQ2?usp=sharing

Sau khi tải:

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

Không tạo cấu trúc sai:

```text
Assets/Assets/
```

hoặc:

```text
ParkingVisionV8/ParkingVisionV8/models/
```

---

# 20. Yêu cầu hệ thống

## Hệ điều hành

```text
Windows 10
Windows 11
```

## Python

```text
Python 3.9 - 3.11
```

## RAM

Tối thiểu khuyến nghị:

```text
8 GB
```

Khuyến nghị:

```text
16 GB+
```

## GPU

GPU NVIDIA hỗ trợ CUDA được khuyến nghị.

CPU vẫn có thể được sử dụng với các pipeline hỗ trợ fallback.

## Database

- MySQL;
- Laragon/XAMPP;
- phpMyAdmin.

## Mobile

- Flutter SDK;
- Android SDK 36;
- Android Emulator API 36 hoặc Android device.

## Optional

- DroidCam;
- Docker Desktop;
- Redis;
- RabbitMQ.

---

# 21. Cài đặt Python

Clone repository:

```powershell
git clone https://github.com/DatPhanNexor/ParkingSpaceDetection.git
cd ParkingSpaceDetection
```

Tạo môi trường:

```powershell
python -m venv .venv
```

Kích hoạt:

```powershell
.\.venv\Scripts\Activate.ps1
```

Nâng pip:

```powershell
python -m pip install --upgrade pip
```

Cài dependencies:

```powershell
pip install -r requirements.txt
```

Nếu sử dụng GPU NVIDIA:

```powershell
pip install -r requirements-gpu.txt
```

Kiểm tra:

```powershell
python --version
pip --version
```

---

# 22. Cấu hình MySQL

Khởi động MySQL bằng Laragon/XAMPP.

Tạo database:

```sql
CREATE DATABASE ai_parking_system;
```

Import:

```text
database/ai_parking_system.sql
```

Ví dụ MySQL CLI:

```powershell
mysql -u root -p ai_parking_system < database\ai_parking_system.sql
```

Có thể sử dụng phpMyAdmin để import thủ công.

---

# 23. Chạy Desktop App

Từ project root:

```powershell
cd D:\Project\ParkingSpaceDetection
.\.venv\Scripts\Activate.ps1
python ParkingSpaceDesktopApp\run_desktop_app.py
```

Luồng sử dụng:

1. đăng nhập;
2. chọn source;
3. chọn Image/Video/Webcam;
4. chọn model;
5. chọn processing device;
6. nhấn `RUN`;
7. theo dõi kết quả;
8. nhấn `STOP`;
9. kiểm tra output;
10. đăng xuất.

---

# 24. Image Mode

1. chọn `Image`;
2. chọn ảnh;
3. chọn YOLO11 Segmentation;
4. nhấn `RUN`;
5. xem detection/segmentation;
6. lưu kết quả nếu cần.

Model:

```text
yolo11n-seg.pt
```

hoặc:

```text
yolo11x-seg.pt
```

> Image Mode không tự tạo Parking Session và không tính phí tự động.

---

# 25. Video Mode

1. chọn `Video`;
2. chọn file;
3. chọn YOLO11;
4. nhấn `RUN`;
5. theo dõi slot;
6. theo dõi session;
7. theo dõi duration;
8. theo dõi fee;
9. lưu Video/CSV nếu cần.

Video Mode có thể tham gia đầy đủ lifecycle của Parking Session.

---

# 26. Webcam / DroidCam

Thông qua Desktop App hoặc script:

```powershell
python ParkingVisionV8\run_droidcam_v8s_boardlock.py --source 0
```

Cú pháp đúng:

```text
--source 0
```

Không sử dụng:

```text
--source = 0
```

Nếu camera index `0` không đúng:

```powershell
python ParkingVisionV8\run_droidcam_v8s_boardlock.py --source 1
```

hoặc thử index khác.

---

# 27. Chạy Dashboard

```powershell
streamlit run ParkingSpaceDesktopApp\streamlit_dashboard.py
```

URL mặc định:

```text
http://localhost:8501
```

---

# 28. Chạy Flutter Android

Di chuyển vào project:

```powershell
cd D:\Project\ParkingSpaceDetection\flutter_mobile_app
```

Kiểm tra:

```powershell
flutter doctor
```

Lấy dependencies:

```powershell
flutter pub get
```

Kiểm tra emulator:

```powershell
flutter emulators
```

Khởi động:

```powershell
flutter emulators --launch flutter_emulator
```

Kiểm tra device:

```powershell
flutter devices
```

Ví dụ:

```text
sdk gphone64 x86 64
emulator-5554
Android 16 (API 36)
```

Chạy app:

```powershell
flutter run -d emulator-5554
```

Flutter command:

```text
r = Hot Reload
R = Hot Restart
d = Detach
q = Quit
```

---

# 29. Android Emulator

Cấu hình nhẹ cho máy RAM 16 GB:

```text
RAM   : 2048 MB
CPU   : 2 cores
API   : 36
```

Ví dụ:

```powershell
$SDK="D:\Android\Sdk"

Start-Process "$SDK\emulator\emulator.exe" `
    -ArgumentList "-avd flutter_emulator -memory 2048 -cores 2 -no-boot-anim"
```

Sau khi boot:

```powershell
flutter devices
flutter run -d emulator-5554
```

---

# 30. Backend từ Android Emulator

Trong Android Emulator:

```text
localhost
127.0.0.1
```

trỏ về emulator, không phải Windows host.

Nếu FastAPI chạy ở Windows:

```text
http://127.0.0.1:8000
```

Android Emulator thường truy cập bằng:

```text
http://10.0.2.2:8000
```

Tương tự với WebSocket:

```text
ws://10.0.2.2:<PORT>
```

Port phải khớp cấu hình backend thực tế.

---

# 31. Testing

## Python tests

```powershell
pytest
```

Verbose:

```powershell
pytest -v
```

Các lớp kiểm thử cần bao gồm:

- unit test;
- integration test;
- API test;
- performance test.

Các khu vực quan trọng:

- authentication;
- state transition;
- session management;
- billing;
- MySQL;
- Redis;
- RabbitMQ;
- duplicate-event protection;
- retry/DLQ;
- REST API;
- WebSocket.

## Flutter

Analyze:

```powershell
cd flutter_mobile_app
flutter analyze
```

Test:

```powershell
flutter test
```

Build APK:

```powershell
flutter build apk --debug
```

Output:

```text
flutter_mobile_app/build/app/outputs/flutter-apk/app-debug.apk
```

---

# 32. Docker và CI/CD

Kiểm tra Docker:

```powershell
docker --version
docker compose version
```

Kiến trúc yêu cầu mỗi microservice có Dockerfile tương ứng.

Docker Compose chịu trách nhiệm điều phối các service cần thiết như:

```text
Backend Services
MySQL
Redis
RabbitMQ
```

GitHub Actions được sử dụng để tự động hóa:

```text
Checkout
   ↓
Setup environment
   ↓
Install dependencies
   ↓
Static analysis
   ↓
Unit / Integration Tests
   ↓
Docker validation/build
```

Flutter pipeline có thể kiểm tra:

```text
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

---

# 33. Logging và Security

Không commit:

```text
.env
password
JWT secret
private key
production DB credentials
API secrets
```

Không log:

- plaintext password;
- JWT secret;
- private key;
- sensitive access token.

Service cần log đầy đủ các lỗi:

- authentication;
- database;
- Redis;
- RabbitMQ;
- detection;
- invalid event;
- parking session conflict;
- billing;
- REST;
- WebSocket.

---

# 34. Troubleshooting

## Thiếu `ultralytics`

```powershell
pip install -r requirements.txt
```

---

## Thiếu model

Kiểm tra:

```text
yolo11n-seg.pt
yolo11x-seg.pt
yolov8s.pt
ParkingVisionV8/models/
```

---

## MySQL không kết nối

Kiểm tra:

```text
MySQL đang chạy?
Port 3306?
Database tồn tại?
Username đúng?
Password đúng?
```

---

## Camera không mở

Thử:

```text
source 0
source 1
source 2
```

Đảm bảo ứng dụng khác không chiếm camera.

---

## Dashboard không có dữ liệu

Kiểm tra:

```text
MySQL
Detection pipeline
Parking Session
Backend
```

---

## Port 8501 bị chiếm

```powershell
netstat -ano | findstr :8501
```

---

## Flutter không thấy emulator

```powershell
flutter devices
flutter emulators
```

Sau đó:

```powershell
flutter emulators --launch flutter_emulator
```

---

## Emulator offline

```powershell
D:\Android\Sdk\platform-tools\adb.exe devices
```

Reset:

```powershell
D:\Android\Sdk\platform-tools\adb.exe kill-server
D:\Android\Sdk\platform-tools\adb.exe start-server
```

---

## Flutter không gọi được Backend

Không dùng:

```text
127.0.0.1
```

nếu backend nằm trên Windows host.

Dùng:

```text
10.0.2.2
```

với Android Emulator.

---

# 35. Quy trình Demo

Một quy trình demo đồ án hoàn chỉnh:

```text
1. Start MySQL
2. Start Redis
3. Start RabbitMQ
4. Start Backend
5. Login
6. Start Desktop App
7. Chọn Video/Webcam/DroidCam
8. AI xử lý dữ liệu
9. Xác định S01-S09
10. EMPTY → OCCUPIED
11. Tạo Parking Session
12. Cập nhật duration
13. Cập nhật estimated fee
14. OCCUPIED → EMPTY
15. Hoàn tất Parking Session
16. Lưu MySQL
17. Cập nhật Redis
18. RabbitMQ truyền event
19. Dashboard cập nhật
20. Flutter cập nhật qua REST/WebSocket
```

---

# 36. Phạm vi mở rộng

Các chức năng sau được xem là hướng phát triển tiếp theo:

- License Plate Recognition;
- Push Notification;
- Mobile upload Image;
- iOS;
- cloud deployment;
- multiple parking lots;
- multiple cameras;
- parking reservation;
- online payment;
- automatic gate;
- Kubernetes.

Core flow phải ổn định trước khi phát triển các tính năng mở rộng.

---

# 37. Lưu ý khi nộp Course / GitHub

Do giới hạn dung lượng bản nộp, các model/dataset/video lớn có thể không nằm trong repository.

Người kiểm tra cần:

1. clone source;
2. tải Large Assets;
3. đặt đúng cấu trúc;
4. cài Python dependencies;
5. import database;
6. khởi động service cần thiết;
7. chạy ứng dụng.

Không đổi tên model hoặc folder nếu mã nguồn đang tham chiếu trực tiếp.

Các thư mục phát sinh không nên commit:

```text
.venv/
__pycache__/
.pytest_cache/
build/
.dart_tool/
.gradle/
.idea/
.vscode/
ParkingSpaceDesktopApp/desktop_outputs/
```

Điều chỉnh `.gitignore` theo nhu cầu repository.

---

# 38. Quick Start

## Python

```powershell
cd D:\Project\ParkingSpaceDetection
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Desktop

```powershell
python ParkingSpaceDesktopApp\run_desktop_app.py
```

## Dashboard

```powershell
streamlit run ParkingSpaceDesktopApp\streamlit_dashboard.py
```

## DroidCam / Webcam

```powershell
python ParkingVisionV8\run_droidcam_v8s_boardlock.py --source 0
```

## Flutter

```powershell
cd flutter_mobile_app
flutter pub get
flutter devices
flutter run -d emulator-5554
```

## Python Tests

```powershell
cd D:\Project\ParkingSpaceDetection
pytest
```

## Flutter Tests

```powershell
cd flutter_mobile_app
flutter analyze
flutter test
flutter build apk --debug
```

---

# 39. License

Dự án được phân phối theo **Apache License 2.0**.

Xem file:

```text
LICENSE
```

để biết đầy đủ điều khoản sử dụng.

---

## Project Summary

`ParkingSpaceDetection` là một hệ thống Smart Parking end-to-end kết hợp:

```text
YOLO11 Segmentation
        +
YOLOv8s
        +
OpenCV
        +
Board Lock
        +
Temporal Smoothing / Hysteresis
        +
Parking Session Management
        +
Automatic Billing
        +
CustomTkinter Desktop App
        +
Streamlit Dashboard
        +
Flutter Android
        +
FastAPI
        +
REST / WebSocket
        +
JWT / RBAC
        +
MySQL
        +
Redis
        +
RabbitMQ
        +
Docker
        +
Automated Testing
        +
GitHub Actions
```

Trọng tâm của dự án là xây dựng một hệ thống có thể nhận dạng trạng thái bãi đỗ xe, quản lý vòng đời phiên đỗ, tính phí, lưu dữ liệu và cung cấp khả năng giám sát từ nhiều nền tảng trong một kiến trúc thống nhất, có khả năng kiểm thử và triển khai theo quy trình kỹ thuật phần mềm.
