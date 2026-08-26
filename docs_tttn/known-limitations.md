# Known Limitations

- **Legacy AI Adapter**: Due to the rigid procedural nature of `ParkingVisionV8/run_droidcam_v8s_boardlock.py`, the AI Detection Service adapter uses `ultralytics` directly to load the model and evaluate frames based on the static `DEFAULT_SLOTS_TEMPLATE` exported from the legacy code. It does not re-use the complex hysteresis logic from the old script since that logic was tied to a GUI loop. Hysteresis should theoretically be moved to the Parking and Billing Service for complete decoupling.
- **Flutter App**: The Flutter app is functional and correctly configured to use Dio interceptors for token refresh. However, it requires a physical device or emulator pointing to the correct API base URL.
- **Refresh Token Generation**: Refresh tokens are stored randomly as hashes in the database but are communicated via `user_id:raw_token` format to simplify lookup.
- **Video Detection Mocking**: Processing a full video asynchronously in the background requires a substantial worker queue for chunking video frames, which is mocked in `ai_detection_service/main.py`.
