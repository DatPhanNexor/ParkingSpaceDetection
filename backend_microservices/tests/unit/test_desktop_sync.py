import pytest
pytest.importorskip("aiomysql")
from pydantic import ValidationError
from datetime import datetime, timezone

from services.desktop_sync_service.main import (
    SLOT_IDS,
    normalize_slot_id,
    SlotSnapshot,
    OccupancySnapshot,
)

def test_detector_region_mapping_is_canonical():
    assert normalize_slot_id(1) == "S01"
    assert normalize_slot_id("S04") == "S04"
    assert normalize_slot_id(9) == "S09"
    assert normalize_slot_id(10) is None

def test_snapshot_requires_9_slots():
    with pytest.raises(ValidationError):
        OccupancySnapshot(slots=[
            SlotSnapshot(slot_id="S01", status="OCCUPIED"),
            SlotSnapshot(slot_id="S02", status="EMPTY")
        ])

def test_snapshot_clears_stale_data():
    slots = []
    for i in range(1, 10):
        sid = f"S0{i}"
        status = "OCCUPIED" if i in [1, 4] else "EMPTY"
        slots.append(SlotSnapshot(slot_id=sid, status=status))
    
    snapshot = OccupancySnapshot(slots=slots, observed_at=datetime.now(timezone.utc).isoformat())
    assert len(snapshot.slots) == 9
    
    occupied = {s.slot_id for s in snapshot.slots if s.status == "OCCUPIED"}
    assert occupied == {"S01", "S04"}
    
    empty = {s.slot_id for s in snapshot.slots if s.status == "EMPTY"}
    assert empty == {"S02", "S03", "S05", "S06", "S07", "S08", "S09"}

