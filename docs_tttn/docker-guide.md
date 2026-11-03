# Docker Guide

## Compose Files
- `infrastructure/compose.yaml`: Full stack including MariaDB (`:3307` -> `:3306`), Redis (`:6380` -> `:6379`), RabbitMQ (`:5673` -> `:5672`), core FastAPI microservices (`auth_service`, `parking_billing_service`, `reporting_service`, `desktop_sync_service`), and optional `ai_detection_service` + `streamlit_admin`.
- `infrastructure/compose.standalone.yaml`: Core backend stack connecting to host MariaDB (`host.docker.internal:3306`).

## Usage
```bash
docker compose -f infrastructure/compose.yaml up --build -d
docker compose -f infrastructure/compose.yaml ps
```
