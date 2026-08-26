import pytest
from shared.events import EventEnvelope, DetectionCompletedPayload, SlotStatus
import uuid
import datetime

def test_event_envelope_serialization():
    payload = DetectionCompletedPayload(
        slot_id="S01",
        status=SlotStatus.OCCUPIED,
        confidence=0.95,
        source_type="WEBCAM"
    )
    
    event = EventEnvelope(
        event_type="detection.completed",
        source="test-service",
        payload=payload.model_dump()
    )
    
    # Event ID must be UUID
    uuid_obj = uuid.UUID(event.event_id)
    assert uuid_obj.version == 4
    
    # Dump to JSON
    json_data = event.model_dump_json()
    assert "S01" in json_data
    assert "OCCUPIED" in json_data
    
    # Parse back
    event2 = EventEnvelope.model_validate_json(json_data)
    assert event2.event_id == event.event_id
    assert event2.payload["slot_id"] == "S01"
