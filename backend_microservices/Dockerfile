FROM python:3.11-slim as builder

WORKDIR /app
COPY backend_microservices/requirements.txt requirements.txt
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

# Create non-root user
RUN useradd -m -s /bin/bash appuser

WORKDIR /app

# Copy dependencies
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Install cv2 dependencies
RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*

COPY . .

# Set permissions
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "services.auth_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
