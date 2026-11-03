import pytest
pytest.importorskip("aiomysql")
from pydantic import ValidationError
from datetime import datetime, timezone

import services.desktop_sync_service.main as desktop_sync_main
from services.desktop_sync_service.main import (
    SLOT_IDS,
    normalize_slot_id,
    publish_snapshot,
    SlotSnapshot,
    OccupancySnapshot,
)

def test_detector_region_mapping_is_canonical():
    assert normalize_slot_id(1) == "S01"
    assert normalize_slot_id("S04") == "S04"
    assert normalize_slot_id(9) == "S09"
    assert normalize_slot_id(10) is None
    assert normalize_slot_id(True) is None
    assert normalize_slot_id(False) is None

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


@pytest.mark.asyncio
async def test_publish_snapshot_uses_redis_pipeline_and_emits_transitions(monkeypatch):
    class FakePipe:
        def __init__(self, parent):
            self.parent = parent
            self.ops = []
        def hgetall(self, key):
            self.ops.append(("hgetall", key, None))
            return self
        def hset(self, key, mapping):
            self.ops.append(("hset", key, mapping))
            return self
        def expire(self, key, ttl):
            self.ops.append(("expire", key, ttl))
            return self
        async def execute(self):
            self.parent.round_trips += 1
            out = []
            for op, key, val in self.ops:
                if op == "hgetall":
                    out.append(dict(self.parent.store.get(key, {})))
                elif op == "hset":
                    self.parent.store[key] = dict(val)
                    out.append(1)
                elif op == "expire":
                    out.append(True)
            self.ops.clear()
            return out

    class FakeRedis:
        def __init__(self):
            self.store = {}
            self.round_trips = 0
        def pipeline(self, transaction=False):
            return FakePipe(self)

    published_events = []

    class FakePublisher:
        async def publish(self, event, routing_key=""):
            published_events.append((routing_key, event))

    fake_redis = FakeRedis()
    monkeypatch.setattr(desktop_sync_main, "redis_client", fake_redis)
    async def _fake_get_pub():
        return FakePublisher()
    monkeypatch.setattr(desktop_sync_main, "get_publisher", _fake_get_pub)

    snapshot = OccupancySnapshot(
        slots=[
            SlotSnapshot(slot_id=f"S0{i}", status="OCCUPIED" if i == 1 else "EMPTY")
            for i in range(1, 10)
        ],
        observed_at="2026-10-04T07:00:00+00:00",
    )
    res = await publish_snapshot(snapshot)
    assert res["type"] == "parking.snapshot"
    assert fake_redis.round_trips == 2
    assert len(published_events) == 1
    assert published_events[0][1].payload["slot_id"] == "S01"
