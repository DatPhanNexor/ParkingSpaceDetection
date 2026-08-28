import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class SlotStatus(str, Enum):
    EMPTY = "EMPTY"
    OCCUPIED = "OCCUPIED"
    UNKNOWN = "UNKNOWN"

class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    schema_version: str = "1.0"
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    payload: Dict[str, Any]

class DetectionCompletedPayload(BaseModel):
    slot_id: str
    status: SlotStatus
    confidence: float
    measurement_valid: bool
    board_lock_valid: bool
    camera_ok: bool
    status_reason: str
    stable_frame_count: int
    observed_at_utc: str
    source_elapsed_seconds: float
    source_type: str

class ParkingSlotUpdatedPayload(BaseModel):
    slot_id: str
    status: SlotStatus
    updated_at: str

class ParkingSessionStartedPayload(BaseModel):
    session_id: str
    slot_id: str
    started_at: str

class ParkingSessionCompletedPayload(BaseModel):
    session_id: str
    slot_id: str
    started_at: str
    ended_at: str
    duration_seconds: int

class BillingCompletedPayload(BaseModel):
    session_id: str
    amount: float
    currency: str = "VND"
    calculated_at: str
