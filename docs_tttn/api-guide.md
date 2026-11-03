# API Guide

## Services & Base Ports
- **Auth Service (`:8001`)**:
  - `POST /api/v1/auth/login` — Authenticate and obtain `access_token` + `refresh_token`.
  - `POST /api/v1/auth/refresh` — Rotate refresh token and issue new access token.
  - `POST /api/v1/auth/logout` — Revoke active refresh token.
  - `GET /api/v1/auth/me` — Current authenticated user profile.
  - `GET/POST/PATCH /api/v1/users` — Admin user management.
- **Parking Billing Service (`:8003`)**:
  - `DELETE /api/v1/sessions/active/{session_id}` — Admin force-clear single active session.
  - `DELETE /api/v1/sessions/active` — Admin force-clear all active sessions.
- **Reporting Service (`:8004`)**:
  - `GET /api/v1/slots` & `GET /api/v1/slots/{slot_id}` — Live 9-slot status (`S01`–`S09`).
  - `GET /api/v1/sessions/active` — Active parking sessions.
  - `GET /api/v1/sessions/history` — Completed parking transactions (`lich_su_xe`).
  - `DELETE /api/v1/sessions/history/{transaction_id}` & `DELETE /api/v1/sessions/history` — Admin history deletion.
  - `GET /api/v1/reports/summary`, `/revenue`, `/frequency` — Analytics (supports optional `?since=<ISO-8601>` shift filter).
  - `GET /api/v1/reports/export.csv` — Admin CSV export with formula-injection protection.
  - `WS /ws/parking?token=<jwt>` — Real-time dashboard snapshot stream.
- **Desktop Sync Service (`:8005`)**:
  - `POST /api/v1/sync` — Ingest 9-slot canonical occupancy snapshot from the desktop application.
