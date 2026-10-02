import pytest

pytest.importorskip("aiomysql")

from services.desktop_sync_service.main import (
    SLOT_IDS,
    normalize_slot_id,
    snapshot_from_desktop_rows,
)


def test_detector_region_mapping_is_canonical():
    assert normalize_slot_id(1) == "S01"
    assert normalize_slot_id("S04") == "S04"
    assert normalize_slot_id(9) == "S09"
    assert normalize_slot_id(10) is None


def test_desktop_rows_replace_all_slots_and_clear_empty_slots():
    snapshot = snapshot_from_desktop_rows(
        [
            ("run-1", "tx-1", 1, "2026-10-01T10:00:00Z", None, None),
            ("run-1", "tx-4", "S04", "2026-10-01T10:00:00Z", None, None),
        ]
    )
    occupied = {slot.slot_id for slot in snapshot.slots if slot.status == "OCCUPIED"}
    assert occupied == {"S01", "S04"}
    assert len(snapshot.slots) == 9

    empty_snapshot = snapshot_from_desktop_rows(
        [
            ("run-1", "tx-1", 1, "2026-10-01T10:00:00Z", "2026-10-01T10:05:00Z", None),
            ("run-1", "tx-4", 4, "2026-10-01T10:00:00Z", "2026-10-01T10:05:00Z", None),
        ]
    )
    assert {slot.slot_id for slot in empty_snapshot.slots if slot.status == "OCCUPIED"} == set()
    assert {slot.slot_id for slot in empty_snapshot.slots} == set(SLOT_IDS)
