# Smart Parking AI Mobile

Ứng dụng Flutter Android để giám sát từ xa hệ thống ParkingSpaceDetection.

## Backend contract

- Auth: `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me` trên port `8001`.
- Reporting: `/api/v1/slots`, `/api/v1/sessions/active`, `/api/v1/sessions/history`, `/api/v1/alerts`, `/api/v1/reports/*` trên port `8004`.
- WebSocket: `/ws/parking?token=<JWT>` trên port `8004`.

Backend hiện trả REST snapshot chính xác cho mobile. WebSocket endpoint xác thực được kết nối, nhưng service hiện chưa broadcast sự kiện chủ động, nên app giữ snapshot gần nhất và đồng bộ REST định kỳ 15 giây.

## Chạy trên Android Emulator

Mặc định app dùng host emulator:

```powershell
flutter run -d <device-id>
```

Override bằng `--dart-define` khi chạy trên Windows/web hoặc thiết bị thật:

```powershell
flutter run `
  --dart-define=AUTH_BASE_URL=http://10.0.2.2:8001/api/v1 `
  --dart-define=REPORTING_BASE_URL=http://10.0.2.2:8004/api/v1 `
  --dart-define=WEBSOCKET_URL=ws://10.0.2.2:8004/ws/parking
```

## Màn hình

- Đăng nhập JWT với access token và refresh token.
- Tổng quan với KPI, trạng thái kết nối và bản đồ 9 vị trí S01-S09.
- Đang đỗ với duration live từ dữ liệu `started_at`.
- Lịch sử vào-ra từ 50 giao dịch mới nhất backend trả về.
- Báo cáo admin hoặc Cảnh báo cho staff.

App không chạy YOLO trên điện thoại, không kết nối trực tiếp MySQL/Redis/RabbitMQ và không tạo dữ liệu runtime giả.
