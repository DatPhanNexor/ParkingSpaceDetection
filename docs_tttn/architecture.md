# Architecture

This repository implements an end-to-end Smart Parking Detection, Billing, and Real-Time Reporting platform across four layers:

1. **Legacy Core Package (`src/parkingspace/`)**:
   - YOLOv8 vehicle detection (`services.py`) combined with probability-map + morphological contour analysis (`pipeline.py`) and polygon region thresholds (`regions.py`).
   - Hardware capability detection (`capabilities.py`) and bounded runtime performance monitoring (`performance.py`).
2. **Desktop Vision & Board-Lock Engines (`ParkingSpaceDesktopApp/` & `ParkingVisionV8/`)**:
   - PySide6 desktop operator station (`ParkingSpaceDesktopApp/main.py`) with 9-slot canonical detection (`detector_engine.py`, `parkingvision_v8_bridge.py`), anti-jitter debounce, local billing (`billing_manager.py`), and HTTP snapshot synchronization (`desktop_sync_client.py`) to `desktop_sync_service`.
3. **Backend Microservices (`backend_microservices/`)**:
   - `auth_service` (`:8001`): JWT + refresh-token rotation + RBAC (`admin`, `staff`) against MariaDB `tai_khoan` / `refresh_tokens`.
   - `ai_detection_service` (`:8002`): Optional server-side frame stabilization and RabbitMQ event producer.
   - `parking_billing_service` (`:8003`): RabbitMQ consumer (`detection.completed` -> `session.started` / `session.ended` / `billing.calculated`), Redis distributed locking (`acquire_lock`), and MariaDB persistence (`lich_su_xe`, `active_session_locks`, `processed_events`).
   - `reporting_service` (`:8004`): Dashboard REST endpoints, CSV export (with formula-injection escaping), and `/ws/parking` WebSocket push snapshots backed by Redis pipelines and MariaDB views.
   - `desktop_sync_service` (`:8005`): Receives 9-slot snapshots from the desktop app (`/api/v1/sync`), updates Redis `parking:live:slot:S01..S09` via pipeline, and emits `detection.completed` transitions to RabbitMQ.
4. **Flutter Mobile App (`flutter_mobile_app/`)**:
   - Riverpod state management (`dashboard_provider.dart`), real-time WebSocket stream with exponential backoff (`websocket_service.dart`), token-refresh interceptor (`api_client.dart`), and live dashboard/map/history/reporting screens.
