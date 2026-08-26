# Traceability Matrix

| Yêu cầu PDF | Thành phần triển khai | Bằng chứng | Trạng thái |
|---|---|---|---|
| Core Flow 1. Đăng nhập và phân quyền | Auth Service, JWT_RBAC, MySQL | `services/auth_service/main.py`, `shared/security/jwt_rbac.py` | PASS |
| Core Flow 2. Nhận dạng Image | AI Detection Service, YOLO11, Adapter | `services/ai_detection_service/main.py`, `adapters/legacy_ai_adapter/adapter.py` | PASS |
| Core Flow 3. Nhận dạng Video | AI Detection Service (Video mock job) | `services/ai_detection_service/main.py` | PARTIAL |
| Core Flow 4. Nhận dạng Webcam | AI Detection Service stream endpoint | `services/ai_detection_service/main.py` | PASS |
| Core Flow 5. Quản lý phiên đỗ và tính phí | Parking & Billing Service, MySQL | `services/parking_billing_service/main.py` | PASS |
| Core Flow 6. Dashboard và báo cáo | Reporting Service, Streamlit Admin | `services/reporting_service/main.py`, `streamlit_admin/app.py` | PASS |
| Core Flow 7. Mobile Monitoring | Flutter App, API, WebSocket | `flutter_mobile_app/lib/screens/dashboard.dart` | PASS |
| Core Flow 8. Quản lý tài khoản và cấu hình | Auth Service Admin API | `services/auth_service/main.py` | PASS |
| Core Flow 9. Truyền và xử lý sự kiện | RabbitMQ Publisher, Parking Consumer | `shared/events/publisher.py`, `services/parking_billing_service/main.py` | PASS |
| Core Flow 10. Xuất dữ liệu | Reporting Service CSV Export | `services/reporting_service/main.py` | PASS |
| Mỗi vị trí S01-S09 chỉ có 1 phiên | Slot Mapper, Redis Locks, MySQL Locks | `adapters/slot_id_mapper/mapper.py`, `shared/database/redis_cache.py` | PASS |
| Chống xử lý trùng sự kiện | Idempotency Check in MySQL | `services/parking_billing_service/main.py` (processed_events logic) | PASS |
| Không kết thúc phiên sai do mất camera | Parking Logic Hysteresis | Evaluated in legacy adapter. Service only ends if event is 'EMPTY' | PASS |
