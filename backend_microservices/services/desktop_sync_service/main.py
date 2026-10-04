import os
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException

from shared.events import get_publisher, EventEnvelope, DetectionCompletedPayload, SlotStatus
import uuid
from pydantic import BaseModel, Field

from shared.database import get_db_connection, redis_client

SLOT_IDS = tuple(f"S{i:02d}" for i in range(1, 10))
LIVE_KEY_PREFIX = os.getenv("LIVE_OCCUPANCY_KEY_PREFIX", "parking:live:slot")
LIVE_META_KEY = os.getenv("LIVE_OCCUPANCY_META_KEY", "parking:live:meta")
_last_snapshot: dict[str, Any] = {"run_id": None, "observed_at": None, "slots": []}

class SlotSnapshot(BaseModel):
    slot_id: str
    status: str
    session_id: str | None = None
    started_at: str | None = None
    updated_at: str | None = None

class OccupancySnapshot(BaseModel):
    slots: list[SlotSnapshot] = Field(min_length=9, max_length=9)
    observed_at: str | None = None

def normalize_slot_id(raw: Any) -> str | None:
    text = str(raw).strip().upper() if raw is not None else ""
    if text.startswith("S"):
        text = text[1:]
    try:
        number = int(text)
    except (TypeError, ValueError):
        return None
    return f"S{number:02d}" if 1 <= number <= 9 else None

async def publish_snapshot(snapshot: OccupancySnapshot) -> dict[str, Any]:
    normalized: dict[str, SlotSnapshot] = {}
    for slot in snapshot.slots:
        slot_id = normalize_slot_id(slot.slot_id)
        status = slot.status.upper()
        if slot_id is None or status not in {"EMPTY", "OCCUPIED"}:
            raise HTTPException(status_code=422, detail="Snapshot must contain S01-S09 EMPTY/OCCUPIED slots")
        if slot_id in normalized:
            raise HTTPException(status_code=422, detail="Snapshot contains duplicate slots")
        normalized[slot_id] = slot.model_copy(update={"slot_id": slot_id, "status": status})
    if set(normalized) != set(SLOT_IDS):
        raise HTTPException(status_code=422, detail="Snapshot must contain each slot exactly once")

    observed_at = snapshot.observed_at or datetime.now(timezone.utc).isoformat()
    
    # 1. Compare with current Redis state and publish events
    publisher = await get_publisher()
    
    for slot_id in SLOT_IDS:
        new_status = normalized[slot_id].status
        
        # Read current status
        current_state = await redis_client.hgetall(f"{LIVE_KEY_PREFIX}:{slot_id}")
        old_status = current_state.get("status", "EMPTY")
        
        if old_status != new_status:
            # Emit detection.completed event
            payload = DetectionCompletedPayload(
                slot_id=slot_id,
                status=SlotStatus.OCCUPIED if new_status == "OCCUPIED" else SlotStatus.EMPTY,
                confidence=1.0,
                measurement_valid=True,
                board_lock_valid=True,
                camera_ok=True,
                status_reason=f"Transitioned from {old_status} to {new_status}",
                stable_frame_count=5,
                observed_at_utc=observed_at,
                source_elapsed_seconds=0.0,
                source_type="desktop-droidcam"
            )
            event = EventEnvelope(
                event_id=str(uuid.uuid4()),
                event_type="detection.completed",
                source="desktop_sync_service",
                payload=payload.model_dump()
            )
            await publisher.publish(event, routing_key="detection.completed")

    # 2. Update Redis
    pipe = redis_client.pipeline(transaction=True)
    for slot_id in SLOT_IDS:
        slot = normalized[slot_id]
        
        # Read current state to preserve session info if we are just pinging the same status
        current_state = await redis_client.hgetall(f"{LIVE_KEY_PREFIX}:{slot_id}")
        
        mapping_dict = {
            "status": slot.status,
            "updated_at": slot.updated_at or observed_at,
            "observed_at": observed_at,
            "source": "desktop-droidcam",
        }
        
        if slot.status == "OCCUPIED":
            # Preserve existing session_id and started_at if not provided by snapshot
            mapping_dict["session_id"] = slot.session_id or current_state.get("session_id", "")
            mapping_dict["started_at"] = slot.started_at or current_state.get("started_at", "")
        else:
            mapping_dict["session_id"] = ""
            mapping_dict["started_at"] = ""

        pipe.hset(f"{LIVE_KEY_PREFIX}:{slot_id}", mapping=mapping_dict)
        pipe.expire(f"{LIVE_KEY_PREFIX}:{slot_id}", 15)
    pipe.hset(
        LIVE_META_KEY,
        mapping={"observed_at": observed_at, "source": "desktop-droidcam"},
    )
    await pipe.execute()
    return {
        "type": "parking.snapshot",
        "observed_at": observed_at,
        "slots": [normalized[slot_id].model_dump() for slot_id in SLOT_IDS],
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set default empty snapshot on startup
    observed_at = datetime.now(timezone.utc).isoformat()
    pipe = redis_client.pipeline(transaction=True)
    for slot_id in SLOT_IDS:
        pipe.hset(f"{LIVE_KEY_PREFIX}:{slot_id}", mapping={
            "status": "EMPTY",
            "session_id": "",
            "started_at": "",
            "updated_at": observed_at,
            "observed_at": observed_at,
            "source": "desktop-droidcam",
        })
    pipe.hset(LIVE_META_KEY, mapping={"observed_at": observed_at, "source": "desktop-droidcam"})
    await pipe.execute()
    _last_snapshot.clear()
    _last_snapshot.update({"run_id": None, "observed_at": observed_at, "slots": []})
    yield

app = FastAPI(title="Desktop Live Occupancy Sync", lifespan=lifespan)

@app.post("/api/v1/sync")
async def sync_snapshot(snapshot: OccupancySnapshot):
    payload = await publish_snapshot(snapshot)
    _last_snapshot.clear()
    _last_snapshot.update({**payload, "run_id": snapshot.observed_at})
    return {"status": "success"}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "up"}

@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}

@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return {
        "source": "desktop-droidcam",
        "run_id": _last_snapshot.get("run_id"),
        "observed_at": _last_snapshot.get("observed_at"),
        "occupied": sum(
            1 for slot in _last_snapshot.get("slots", []) if slot.get("status") == "OCCUPIED"
        ),
    }
