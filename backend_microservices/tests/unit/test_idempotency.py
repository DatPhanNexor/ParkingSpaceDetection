import uuid

from shared.events import DetectionCompletedPayload, EventEnvelope, SlotStatus


def test_event_envelope_serialization():
    payload = DetectionCompletedPayload(
        slot_id="S01",
        status=SlotStatus.OCCUPIED,
        confidence=0.95,
        measurement_valid=True,
        board_lock_valid=True,
        camera_ok=True,
        status_reason="stable_detection",
        stable_frame_count=5,
        observed_at_utc="2026-08-28T00:00:00+00:00",
        source_elapsed_seconds=1.25,
        source_type="WEBCAM",
    )

    event = EventEnvelope(
        event_type="detection.completed",
        source="test-service",
        payload=payload.model_dump(mode="json"),
    )

    uuid_object = uuid.UUID(event.event_id)
    assert uuid_object.version == 4

    json_data = event.model_dump_json()
    assert "S01" in json_data
    assert "OCCUPIED" in json_data

    parsed_event = EventEnvelope.model_validate_json(json_data)

    assert parsed_event.event_id == event.event_id
    assert parsed_event.payload["slot_id"] == "S01"
    assert parsed_event.payload["status"] == "OCCUPIED"
    assert parsed_event.payload["measurement_valid"] is True
    assert parsed_event.payload["board_lock_valid"] is True
    assert parsed_event.payload["camera_ok"] is True
    assert parsed_event.payload["status_reason"] == "stable_detection"
    assert parsed_event.payload["stable_frame_count"] == 5
    assert parsed_event.payload["observed_at_utc"] == "2026-08-28T00:00:00+00:00"
    assert parsed_event.payload["source_elapsed_seconds"] == 1.25
    assert parsed_event.payload["source_type"] == "WEBCAM"
