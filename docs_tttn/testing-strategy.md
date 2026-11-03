# Testing Strategy

## Test Suites
1. **Root Legacy & Desktop Runtime Unit Tests (`tests/`)**:
   - Run with: `python -B -m pytest tests`
   - Covers `src/parkingspace/` (`test_main.py`, `test_regions.py`, `test_packaging_metadata.py`), desktop runtime & camera normalization (`test_desktop_runtime.py`, `test_desktop_smoke.py`, `test_detection_semantics.py`, `test_billing_manager.py`), and ParkingVisionV8 frame-skip scheduling (`test_parkingvision_frame_skip.py`).
2. **Backend Microservices Unit & Contract Tests (`backend_microservices/tests/unit/`)**:
   - Run with: `PYTHONPATH=backend_microservices JWT_SECRET=test-secret python -B -m pytest backend_microservices/tests/unit`
   - Covers JWT/RBAC (`test_auth.py`), pricing adapter (`test_pricing.py`), slot mapper (`test_slot_mapper.py`), desktop sync pipeline (`test_desktop_sync.py`), event idempotency (`test_idempotency.py`), and admin session/history endpoints (`test_parking_billing_admin.py`, `test_reporting_admin.py`).
3. **Flutter Static Analysis & Widget/Model Tests (`flutter_mobile_app/test/`)**:
   - Run with: `flutter analyze --no-fatal-infos --no-fatal-warnings && flutter test --no-pub`
   - Covers slot/session/history parsing (`model_parsing_test.dart`) and login/grid rendering (`widget_test.dart`).
