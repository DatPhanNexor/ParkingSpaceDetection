FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend_microservices/pyproject.toml .

RUN pip install --no-cache-dir hatchling \
    && pip install --no-cache-dir -e .

# We'll copy the shared layer and all services, then the command will define what runs
COPY backend_microservices/ ./backend_microservices/
COPY yolo* ./
COPY ParkingVisionV8/ ./ParkingVisionV8/

ENV PYTHONPATH=/app/backend_microservices:/app

CMD ["uvicorn", "backend_microservices.services.auth_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
