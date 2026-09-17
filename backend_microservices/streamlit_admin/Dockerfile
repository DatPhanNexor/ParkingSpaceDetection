FROM python:3.11-slim AS builder

ARG PIP_FIND_LINKS=""
ARG PIP_NO_INDEX=false
ARG PIP_TRUSTED_HOST=""

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    PIP_FIND_LINKS=${PIP_FIND_LINKS} \
    PIP_NO_INDEX=${PIP_NO_INDEX} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

RUN useradd -m -s /bin/bash appuser

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

RUN mkdir -p /app/ParkingSpaceDesktopApp
COPY database_manager.py /app/ParkingSpaceDesktopApp/database_manager.py

RUN chown -R appuser:appuser /app

USER appuser

WORKDIR /app/ParkingSpaceDesktopApp

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_dashboard.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
