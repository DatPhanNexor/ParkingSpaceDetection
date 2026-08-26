from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest


DESKTOP_DIR = Path(__file__).resolve().parents[1] / "ParkingSpaceDesktopApp"
if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_DIR))

from billing_manager import (  # noqa: E402
    BillingConfig,
    BillingManager,
    ParkingObservation,
    VideoTrackAssigner,
    calculate_fee,
    format_duration,
    format_vnd,
)


def observation(
    position_id: str,
    state: str,
    timestamp: float,
    *,
    valid: bool = True,
    frame_id: int | None = None,
) -> ParkingObservation:
    return ParkingObservation(
        position_id=position_id,
        state=state,
        timestamp=timestamp,
        measurement_valid=valid,
        frame_id=frame_id,
    )


def started_manager(*, mode: str = "Video", source: str = "sample.mp4") -> BillingManager:
    manager = BillingManager()
    manager.start_run("run-1", mode, source)
    return manager


def confirm_occupied(
    manager: BillingManager,
    position_id: str = "S01",
    start: float = 0.0,
) -> None:
    for offset in (0.0, 0.1, 0.2):
        assert manager.update([observation(position_id, "OCCUPIED", start + offset)]) == []


def complete_session(
    manager: BillingManager,
    duration_seconds: float,
    position_id: str = "S01",
):
    confirm_occupied(manager, position_id)
    manager.update([observation(position_id, "OCCUPIED", duration_seconds)])
    completed = []
    for offset in (0.2, 0.8, 1.6):
        completed.extend(
            manager.update([observation(position_id, "EMPTY", duration_seconds + offset)])
        )
    assert len(completed) == 1
    return completed[0]


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(75, 25_000), (42, 15_000), (130, 45_000), (18, 10_000)],
)
def test_required_fee_examples(minutes: int, expected: int) -> None:
    assert calculate_fee(minutes * 60) == expected


def test_empty_to_occupied_creates_active_session() -> None:
    manager = started_manager()
    for timestamp in (0.0, 0.1, 0.2):
        manager.update([observation("S05", "EMPTY", timestamp)])
    for timestamp in (1.0, 1.1, 1.2):
        manager.update([observation("S05", "OCCUPIED", timestamp)])
    active = manager.snapshot(now=10.0).active_sessions
    assert len(active) == 1
    assert active[0].position_id == "S05"
    assert active[0].started_at == pytest.approx(1.0)


def test_occupied_to_empty_creates_exactly_one_transaction() -> None:
    manager = started_manager()
    transaction = complete_session(manager, 75 * 60)
    assert transaction.position_id == "S01"
    assert transaction.duration_seconds == pytest.approx(75 * 60)
    assert transaction.fee_vnd == 25_000


def test_invalid_measurement_does_not_end_session() -> None:
    manager = started_manager()
    confirm_occupied(manager)
    for timestamp in (10.0, 20.0, 30.0):
        assert manager.update([observation("S01", "EMPTY", timestamp, valid=False)]) == []
    assert len(manager.snapshot(now=30.0).active_sessions) == 1
    assert manager.total_revenue_vnd == 0


def test_one_noisy_empty_frame_does_not_charge() -> None:
    manager = started_manager()
    confirm_occupied(manager)
    manager.update([observation("S01", "OCCUPIED", 10.0)])
    assert manager.update([observation("S01", "EMPTY", 12.0)]) == []
    assert manager.update([observation("S01", "OCCUPIED", 12.1)]) == []
    assert manager.total_revenue_vnd == 0
    assert len(manager.snapshot(now=13.0).active_sessions) == 1


def test_short_detection_loss_inside_grace_does_not_charge() -> None:
    manager = started_manager()
    confirm_occupied(manager)
    manager.update([observation("S01", "OCCUPIED", 10.0)])
    for timestamp in (10.2, 10.4, 10.6, 11.0):
        assert manager.update([observation("S01", "EMPTY", timestamp)]) == []
    manager.update([observation("S01", "OCCUPIED", 11.1)])
    assert manager.total_revenue_vnd == 0


def test_completed_session_cannot_double_charge() -> None:
    manager = started_manager()
    complete_session(manager, 42 * 60)
    for timestamp in (2600.0, 2601.0, 2602.0, 2603.0):
        assert manager.update([observation("S01", "EMPTY", timestamp)]) == []
    assert len(manager.transactions) == 1
    assert manager.total_revenue_vnd == 15_000


def test_video_uses_source_time_not_wall_clock() -> None:
    manager = BillingManager(clock=lambda: 999_999.0)
    manager.start_run("video-run", "Video", "clip.mp4")
    transaction = complete_session(manager, 18 * 60)
    assert transaction.duration_seconds == pytest.approx(18 * 60)
    assert transaction.fee_vnd == 10_000


def test_video_rejects_missing_source_time() -> None:
    manager = started_manager()
    with pytest.raises(ValueError, match="source_time_seconds"):
        manager.update([ParkingObservation("V01", "OCCUPIED")])


def test_webcam_defaults_to_monotonic_clock() -> None:
    times = iter((100.0, 100.1, 100.2))
    manager = BillingManager(clock=lambda: next(times))
    manager.start_run("live-run", "Webcam", "0")
    for _ in range(3):
        manager.update([ParkingObservation("S01", "OCCUPIED")])
    session = manager.snapshot(now=101.0).active_sessions[0]
    assert session.started_at == pytest.approx(100.0)


def test_stop_reset_never_charges_active_vehicle() -> None:
    manager = started_manager()
    confirm_occupied(manager)
    manager.reset_run()
    assert manager.transactions == ()
    assert manager.total_revenue_vnd == 0
    assert manager.snapshot(now=100.0).active_sessions == ()


def test_two_positions_are_independent() -> None:
    manager = started_manager()
    for timestamp in (0.0, 0.1, 0.2):
        manager.update(
            [
                observation("S01", "OCCUPIED", timestamp),
                observation("S02", "OCCUPIED", timestamp),
            ]
        )
    manager.update([observation("S01", "OCCUPIED", 100.0)])
    completed = []
    for timestamp in (100.2, 100.8, 101.6):
        completed.extend(manager.update([observation("S01", "EMPTY", timestamp)]))
    assert len(completed) == 1
    assert completed[0].position_id == "S01"
    assert [item.position_id for item in manager.snapshot(now=102.0).active_sessions] == ["S02"]


def test_total_revenue_contains_only_completed_transactions() -> None:
    manager = started_manager()
    complete_session(manager, 42 * 60, "S01")
    confirm_occupied(manager, "S02", 3000.0)
    assert manager.total_revenue_vnd == 15_000
    assert len(manager.snapshot(now=4000.0).active_sessions) == 1


def test_starting_new_run_discards_unfinished_and_resets_revenue() -> None:
    manager = started_manager()
    complete_session(manager, 18 * 60)
    confirm_occupied(manager, "S02", 2000.0)
    manager.start_run("run-2", "Webcam", "1")
    snapshot = manager.snapshot(now=3000.0)
    assert snapshot.run_id == "run-2"
    assert snapshot.active_sessions == ()
    assert snapshot.recent_transactions == ()
    assert snapshot.total_revenue_vnd == 0


def test_duplicate_or_old_frame_is_not_applied_twice() -> None:
    manager = started_manager()
    manager.update([observation("S01", "OCCUPIED", 0.0, frame_id=5)])
    manager.update([observation("S01", "OCCUPIED", 0.1, frame_id=5)])
    manager.update([observation("S01", "OCCUPIED", 0.2, frame_id=4)])
    assert manager.snapshot(now=1.0).active_sessions == ()
    manager.update([observation("S01", "OCCUPIED", 0.3, frame_id=6)])
    manager.update([observation("S01", "OCCUPIED", 0.4, frame_id=7)])
    assert len(manager.snapshot(now=1.0).active_sessions) == 1


def test_csv_export_is_utf8_and_deduplicates_transaction_id(tmp_path: Path) -> None:
    manager = started_manager(source="=unsafe-source")
    transaction = complete_session(manager, 75 * 60)
    destination = tmp_path / "csv" / "billing_transactions.csv"
    assert manager.export_transactions_csv(destination, [transaction]) == 1
    assert manager.export_transactions_csv(destination, [transaction]) == 0
    with destination.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["transaction_id"] == transaction.transaction_id
    assert rows[0]["input_source"] == "'=unsafe-source"


def test_formatters_are_stable() -> None:
    assert format_duration(4532.9) == "01:15:32"
    assert format_duration(-5) == "00:00:00"
    assert format_vnd(450_000) == "450.000đ"


def test_video_tracker_keeps_id_during_small_motion() -> None:
    assigner = VideoTrackAssigner()
    assert assigner.update([(10, 10, 60, 80)], 0.0) == []
    assert assigner.update([(12, 11, 62, 81)], 0.1) == []
    observed = assigner.update([(14, 12, 64, 82)], 0.2)
    assert [(item.position_id, item.state) for item in observed] == [("V01", "OCCUPIED")]
    observed = assigner.update([(16, 13, 66, 83)], 0.3)
    assert observed[0].position_id == "V01"
    assert set(assigner.track_boxes) == {"V01"}


def test_video_tracker_temporary_loss_does_not_emit_empty() -> None:
    assigner = VideoTrackAssigner()
    for timestamp in (0.0, 0.1, 0.2):
        assigner.update([(10, 10, 60, 80)], timestamp)
    assert assigner.update([], 1.0) == []
    recovered = assigner.update([(12, 11, 62, 81)], 1.2)
    assert recovered[0].position_id == "V01"
    assert recovered[0].state == "OCCUPIED"


def test_video_tracker_requires_three_observations_for_new_track() -> None:
    assigner = VideoTrackAssigner()
    assert assigner.update([(0, 0, 20, 40)], 0.0) == []
    assert assigner.update([(1, 0, 21, 40)], 0.1) == []
    assert assigner.update([(2, 0, 22, 40)], 0.2)[0].position_id == "V01"


def test_video_tracker_is_one_to_one_and_assigns_distinct_ids() -> None:
    assigner = VideoTrackAssigner()
    boxes = [(0, 0, 20, 40), (200, 0, 220, 40)]
    for timestamp in (0.0, 0.1):
        assert assigner.update(boxes, timestamp) == []
    observed = assigner.update([(2, 0, 22, 40), (198, 0, 218, 40)], 0.2)
    assert {item.position_id for item in observed} == {"V01", "V02"}


def test_video_tracker_invalid_measurement_does_not_age_tracks() -> None:
    assigner = VideoTrackAssigner()
    for timestamp in (0.0, 0.1, 0.2):
        assigner.update([(10, 10, 60, 80)], timestamp)
    assert assigner.update([], 100.0, measurement_valid=False) == []
    recovered = assigner.update([(10, 10, 60, 80)], 100.1)
    assert recovered[0].position_id == "V01"


def test_tracker_and_manager_charge_only_after_grace_and_debounce() -> None:
    config = BillingConfig()
    assigner = VideoTrackAssigner(config)
    manager = BillingManager(config)
    manager.start_run("video", "Video", "clip.mp4")
    box = [(10, 10, 60, 80)]
    for frame_id, timestamp in enumerate((0.0, 0.1, 0.2, 0.3, 0.4), start=1):
        manager.update(assigner.update(box, timestamp, frame_id=frame_id))
    manager.update(assigner.update(box, 60.0, frame_id=6))
    assert manager.update(assigner.update([], 60.5, frame_id=7)) == []
    completed = []
    for frame_id, timestamp in ((8, 61.6), (9, 61.7), (10, 61.8)):
        completed.extend(manager.update(assigner.update([], timestamp, frame_id=frame_id)))
    assert len(completed) == 1
    assert completed[0].position_id == "V01"
    assert completed[0].ended_at == pytest.approx(60.0)

