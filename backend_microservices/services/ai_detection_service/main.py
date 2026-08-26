import os
import asyncio
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any

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

@app.post("/api/v1/detections/video")
async def detect_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # Stub for video processing. In real system, we'd save the file and process it frame by frame in background.
    job_id = "video-" + os.urandom(4).hex()
    return DetectionResponse(status="accepted", job_id=job_id, message="Video processing started")

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
            for slot_raw, status_raw in detected_status.items():
                slot_code = get_slot_code(slot_raw)
                if slot_code == "UNMAPPED":
                    continue
                    
                status = SlotStatus.OCCUPIED if status_raw == "OCCUPIED" else SlotStatus.EMPTY
                
                payload = DetectionCompletedPayload(
                    slot_id=slot_code,
                    status=status,
                    confidence=0.9, # stub confidence
                    source_type="WEBCAM"
                )
                event = EventEnvelope(
                    event_type="detection.completed",
                    source="ai-detection-service",
                    payload=payload.model_dump()
                )
                
                await publisher.publish(event, routing_key=f"detection.{slot_code}")
                
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
