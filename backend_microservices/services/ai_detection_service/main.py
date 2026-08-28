import os
import asyncio
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from pydantic_settings import BaseSettings
from typing import Dict, Any
import logging
from pydantic import BaseModel
import datetime

class Settings(BaseSettings):
    rabbitmq_url: str = "amqp://guest:guest@127.0.0.1:5673/"

    class Config:
        env_file = ".env"

settings = Settings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ai_detection")

from shared.events import (
    get_publisher, EventEnvelope, DetectionCompletedPayload, SlotStatus
)
from adapters.slot_id_mapper import get_slot_code
from adapters.legacy_ai_adapter import LegacyAIAdapter

import cv2
import numpy as np

app = FastAPI(title="AI Detection Service")
adapter = LegacyAIAdapter()
active_streams = {}
video_jobs = {}


class DetectionResponse(BaseModel):
    status: str
    job_id: str
    message: str

@app.on_event("startup")
async def startup_event():
    await get_publisher()

@app.get("/health")
def health():
    return {"status": "up"}

@app.get("/ready")
def ready():
    # If model is loaded, we are ready
    return {"status": "ready" if adapter else "loading"}

@app.get("/metrics")
def metrics():
    # Minimal metrics endpoint for prometheus to scrape later
    return {"active_streams": len(active_streams)}

@app.post("/api/v1/detections/image")
async def detect_image(file: UploadFile = File(...)):
    # Simply process and return the result without creating a session, 
    # strictly per requirements: "Image chỉ trả kết quả nhận dạng và file output; tuyệt đối không tạo phiên"
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image")
        
    detected_status = adapter.detect_frame(frame)
    mapped_status = {get_slot_code(k): v for k, v in detected_status.items() if get_slot_code(k) != "UNMAPPED"}
    
    return {"status": "success", "detections": mapped_status}

async def process_video_job(job_id: str, file_path: str):
    video_jobs[job_id] = "running"
    publisher = await get_publisher()
    
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        video_jobs[job_id] = "failed"
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            detected_status = adapter.detect_frame(frame)
            
            for slot_raw, slot_data in detected_status.items():
                slot_code = get_slot_code(slot_raw)
                if slot_code == "UNMAPPED":
                    continue
                    
                status = SlotStatus.OCCUPIED if slot_data["status"] == "OCCUPIED" else SlotStatus.EMPTY
                
                payload = DetectionCompletedPayload(
                    slot_id=slot_code,
                    status=status,
                    confidence=slot_data["confidence"],
                    measurement_valid=slot_data["measurement_valid"],
                    board_lock_valid=slot_data["board_lock_valid"],
                    camera_ok=slot_data["camera_ok"],
                    status_reason=slot_data["status_reason"],
                    stable_frame_count=1,
                    observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    source_elapsed_seconds=cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0,
                    source_type="VIDEO"
                )
                event = EventEnvelope(
                    event_type="detection.completed",
                    source="ai-detection-service",
                    payload=payload.model_dump()
                )
                
                await publisher.publish(event, routing_key="detection.completed")
                
        video_jobs[job_id] = "succeeded"
    except Exception as e:
        logger.error(f"Video job {job_id} failed: {e}")
        video_jobs[job_id] = "failed"
    finally:
        cap.release()
        try:
            os.remove(file_path)
        except:
            pass

@app.post("/api/v1/detections/video")
async def detect_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    job_id = "video-" + os.urandom(4).hex()
    file_path = f"/tmp/{job_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    video_jobs[job_id] = "queued"
    background_tasks.add_task(process_video_job, job_id, file_path)
    
    return DetectionResponse(status="accepted", job_id=job_id, message="Video processing started")

@app.get("/api/v1/detections/jobs/{job_id}")
async def get_job_status(job_id: str):
    return {"job_id": job_id, "status": video_jobs.get(job_id, "unknown")}

class StreamRequest(BaseModel):
    source_url: str
    stream_id: str

async def process_stream(stream_id: str, source_url: str):
    # Dummy processing loop representing webcam/droidcam logic.
    # In reality this uses cv2.VideoCapture and adapter.detect_frame
    publisher = await get_publisher()
    
    cap = cv2.VideoCapture(source_url)
    if not cap.isOpened():
        print(f"Failed to open stream: {source_url}")
        return

    try:
        while active_streams.get(stream_id):
            ret, frame = cap.read()
            if not ret:
                break
                
            detected_status = adapter.detect_frame(frame)
            
            # Publish detection event
            for slot_raw, slot_data in detected_status.items():
                slot_code = get_slot_code(slot_raw)
                if slot_code == "UNMAPPED":
                    continue
                    
                status = SlotStatus.OCCUPIED if slot_data["status"] == "OCCUPIED" else SlotStatus.EMPTY
                
                payload = DetectionCompletedPayload(
                    slot_id=slot_code,
                    status=status,
                    confidence=slot_data["confidence"],
                    measurement_valid=slot_data["measurement_valid"],
                    board_lock_valid=slot_data["board_lock_valid"],
                    camera_ok=slot_data["camera_ok"],
                    status_reason=slot_data["status_reason"],
                    stable_frame_count=1,
                    observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    source_elapsed_seconds=cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 if cap.isOpened() else 0.0,
                    source_type="WEBCAM"
                )
                event = EventEnvelope(
                    event_type="detection.completed",
                    source="ai-detection-service",
                    payload=payload.model_dump()
                )
                
                await publisher.publish(event, routing_key="detection.completed")
                
            await asyncio.sleep(0.5) # Simulate frame processing time
    finally:
        cap.release()
        if stream_id in active_streams:
            del active_streams[stream_id]

@app.post("/api/v1/detections/stream/start")
async def start_stream(req: StreamRequest, background_tasks: BackgroundTasks):
    if req.stream_id in active_streams:
        raise HTTPException(status_code=400, detail="Stream already active")
        
    active_streams[req.stream_id] = True
    background_tasks.add_task(process_stream, req.stream_id, req.source_url)
    return {"status": "started", "stream_id": req.stream_id}

@app.post("/api/v1/detections/stream/stop")
async def stop_stream(req: StreamRequest):
    if req.stream_id in active_streams:
        active_streams[req.stream_id] = False
        return {"status": "stopping", "stream_id": req.stream_id}
    raise HTTPException(status_code=404, detail="Stream not found")
