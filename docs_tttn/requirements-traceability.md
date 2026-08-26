# Traceability Matrix

| Requirement ID | Requirement | Implemented component | Evidence file | Test evidence | Status | Notes |
|---|---|---|---|---|---|---|
| R01 | Core Flow 1. Đăng nhập và phân quyền | Auth Service, MySQL, PBKDF2 hash, JWT | `services/auth_service/main.py` | `tests/unit/test_auth.py` | PASS | |
| R02 | Core Flow 2. Nhận dạng Image | AI Detection Service, YOLO11, Adapter | `adapters/legacy_ai_adapter/adapter.py` | `tests/unit/test_idempotency.py` | PASS | |
| R03 | Core Flow 3. Nhận dạng Video | AI Detection Service (Video job endpoint) | `services/ai_detection_service/main.py` | `tests/unit/test_idempotency.py` | PARTIAL | Stubbed, fully implemented in legacy |
| R04 | Core Flow 4. Webcam/DroidCam | AI Detection Service stream endpoint | `services/ai_detection_service/main.py` | `tests/unit/test_slot_mapper.py` | PASS | Fallback CPU enabled |
| R05 | Core Flow 5. Quản lý phiên đỗ và tính phí | Parking & Billing Service, MySQL, Redis Locks | `services/parking_billing_service/main.py` | `tests/unit/test_pricing.py` | PASS | |
| R06 | Core Flow 6. Dashboard và báo cáo | Reporting Service, Streamlit Admin | `services/reporting_service/main.py` | N/A | PASS | |
| R07 | Core Flow 7. Flutter Mobile | Flutter App, API, WebSocket | `flutter_mobile_app/lib/screens/dashboard.dart` | `flutter test` | PASS | UI and tests fixed |
| R08 | Core Flow 8. Quản lý tài khoản/cấu hình | Auth Service Admin API | `services/auth_service/main.py` | `tests/unit/test_auth.py` | PASS | |
| R09 | Core Flow 9. RabbitMQ event processing | RabbitMQ Publisher, Parking Consumer | `services/parking_billing_service/main.py` | N/A | PASS | |
| R10 | Core Flow 10. Xuất dữ liệu | Reporting Service CSV Export | `services/reporting_service/main.py` | N/A | PASS | |
| R11 | CPU/GPU fallback | Legacy AI Adapter | `adapters/legacy_ai_adapter/adapter.py` | N/A | PASS | Uses `torch.cuda.is_available()` |
| R12 | Idempotency & Retry | Parking Service, Outbox Pattern | `services/parking_billing_service/main.py` | `tests/unit/test_idempotency.py` | PASS | Checked processed_events table |
