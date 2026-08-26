"""Independent parking-session billing and lightweight video track assignment.

This module intentionally has no GUI, camera, OpenCV, or model dependency.  The
caller supplies observation timestamps: source-media seconds for Video and a
monotonic clock for live camera sources.
"""

from __future__ import annotations

import csv
import logging
import math
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Callable, Iterable, Sequence


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BillingConfig:
    """Billing and state-stabilization settings."""

    hourly_rate_vnd: int = 20_000
    rounding_vnd: int = 5_000
    minimum_fee_vnd: int = 5_000
    debounce_observations: int = 3
    grace_period_seconds: float = 1.5
    recent_limit: int = 6

    def __post_init__(self) -> None:
        if self.hourly_rate_vnd <= 0:
            raise ValueError("hourly_rate_vnd must be positive")
        if self.rounding_vnd <= 0:
            raise ValueError("rounding_vnd must be positive")
        if self.minimum_fee_vnd < 0:
            raise ValueError("minimum_fee_vnd cannot be negative")
        if self.debounce_observations <= 0:
            raise ValueError("debounce_observations must be positive")
        if self.grace_period_seconds < 0:
            raise ValueError("grace_period_seconds cannot be negative")
        if self.recent_limit <= 0:
            raise ValueError("recent_limit must be positive")


@dataclass(frozen=True, slots=True)
class ParkingObservation:
    """One valid or invalid state observation for one physical/track position."""

    position_id: str
    state: str
    timestamp: float | None = None
    measurement_valid: bool = True
    confidence: float | None = None
    frame_id: int | None = None


@dataclass(slots=True)
class ActiveParkingSession:
    """A confirmed parking session that has not yet completed."""

    run_id: str
    position_id: str
    started_at: float
    last_seen: float
    duration_seconds: float = 0.0
    provisional_fee_vnd: int = 0
    transaction_id: str = ""


@dataclass(frozen=True, slots=True)
class CompletedTransaction:
    """A fee-producing OCCUPIED -> EMPTY transition."""

    transaction_id: str
    run_id: str
    timestamp: str
    input_mode: str
    input_source: str
    position_id: str
    started_at: float
    ended_at: float
    source_start_seconds: float
    source_end_seconds: float
    duration_seconds: float
    hourly_rate_vnd: int
    rounding_vnd: int
    fee_vnd: int
    completion_reason: str = "vehicle_departed"


@dataclass(frozen=True, slots=True)
class BillingSnapshot:
    """Immutable data for a throttled GUI refresh."""

    run_id: str
    input_mode: str
    input_source: str
    active_sessions: tuple[ActiveParkingSession, ...]
    recent_transactions: tuple[CompletedTransaction, ...]
    total_revenue_vnd: int
    status: str

    @property
    def active_count(self) -> int:
        return len(self.active_sessions)


@dataclass(slots=True)
class _PositionState:
    stable_state: str | None = None
    candidate_state: str | None = None
    candidate_count: int = 0
    candidate_since: float | None = None
    active_session: ActiveParkingSession | None = None
    last_observation_at: float | None = None
    last_frame_id: int | None = None


def calculate_fee(duration_seconds: float, config: BillingConfig | None = None) -> int:
    """Calculate a completed-session fee using ceiling increments."""

    settings = config or BillingConfig()
    duration = max(0.0, float(duration_seconds))
    raw_fee = duration / 3600.0 * settings.hourly_rate_vnd
    rounded = math.ceil(raw_fee / settings.rounding_vnd) * settings.rounding_vnd
    return max(settings.minimum_fee_vnd, int(rounded))


def format_duration(duration_seconds: float) -> str:
    """Format elapsed seconds as HH:MM:SS without wrapping after 24 hours."""

    total = max(0, int(duration_seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_vnd(amount_vnd: int) -> str:
    """Format Vietnamese dong using a dot thousands separator."""

    return f"{int(amount_vnd):,}".replace(",", ".") + "đ"


class BillingManager:
    """Stateful, thread-safe billing coordinator for one application run."""

    CSV_COLUMNS = (
        "transaction_id",
        "run_id",
        "timestamp",
        "input_mode",
        "input_source",
        "position_id",
        "started_at",
        "ended_at",
        "source_start_seconds",
        "source_end_seconds",
        "duration_seconds",
        "hourly_rate_vnd",
        "rounding_vnd",
        "fee_vnd",
        "completion_reason",
    )

    def __init__(
        self,
        config: BillingConfig | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or BillingConfig()
        self._clock = clock
        self._lock = RLock()
        self._run_id = ""
        self._input_mode = ""
        self._input_source = ""
        self._positions: dict[str, _PositionState] = {}
        self._transactions: list[CompletedTransaction] = []
        self._total_revenue_vnd = 0
        self.db_manager = None
        self.db_user_id = None

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def total_revenue_vnd(self) -> int:
        with self._lock:
            return self._total_revenue_vnd

    @property
    def transactions(self) -> tuple[CompletedTransaction, ...]:
        with self._lock:
            return tuple(self._transactions)

    @property
    def active_sessions(self) -> tuple[ActiveParkingSession, ...]:
        return self.snapshot().active_sessions

    @staticmethod
    def format_duration(duration_seconds: float) -> str:
        return format_duration(duration_seconds)

    @staticmethod
    def format_vnd(amount_vnd: int) -> str:
        return format_vnd(amount_vnd)

    def calculate_fee(self, duration_seconds: float) -> int:
        return calculate_fee(duration_seconds, self.config)

    def start_run(self, run_id: str, input_mode: str, input_source: str) -> None:
        """Start a clean billing run without charging abandoned sessions."""

        normalized_run_id = str(run_id).strip()
        if not normalized_run_id:
            raise ValueError("run_id cannot be empty")
        with self._lock:
            self._run_id = normalized_run_id
            self._input_mode = str(input_mode).strip()
            self._input_source = str(input_source).strip()
            self._positions.clear()
            self._transactions.clear()
            self._total_revenue_vnd = 0

    def reset_run(self) -> None:
        """Abandon active sessions on STOP; completed revenue remains visible."""

        with self._lock:
            self._positions.clear()

    def update(
        self,
        observations: Iterable[ParkingObservation],
        timestamp: float | None = None,
    ) -> list[CompletedTransaction]:
        """Apply observations and return only transactions completed by this call."""

        with self._lock:
            if not self._run_id:
                raise RuntimeError("start_run() must be called before update()")
            completed: list[CompletedTransaction] = []
            for observation in observations:
                transaction = self._apply_observation(observation, timestamp)
                if transaction is not None:
                    completed.append(transaction)
            return completed

    def snapshot(self, now: float | None = None, status: str = "") -> BillingSnapshot:
        """Return current active estimates and completed revenue.

        Video snapshots never fall back to wall-clock time.  If ``now`` is not
        supplied for Video, each active session is shown at its last source time.
        """

        with self._lock:
            active: list[ActiveParkingSession] = []
            for state in self._positions.values():
                session = state.active_session
                if session is None:
                    continue
                if now is not None:
                    display_now = float(now)
                elif self._is_video_mode():
                    display_now = session.last_seen
                else:
                    display_now = self._clock()
                duration = max(0.0, display_now - session.started_at)
                active.append(
                    replace(
                        session,
                        duration_seconds=duration,
                        provisional_fee_vnd=self.calculate_fee(duration),
                    )
                )
            active.sort(key=lambda item: item.position_id)
            recent = tuple(reversed(self._transactions[-self.config.recent_limit :]))
            resolved_status = status.strip() if status else (
                "Đang tính phí" if active else "Chờ xe"
            )
            return BillingSnapshot(
                run_id=self._run_id,
                input_mode=self._input_mode,
                input_source=self._input_source,
                active_sessions=tuple(active),
                recent_transactions=recent,
                total_revenue_vnd=self._total_revenue_vnd,
                status=resolved_status,
            )

    def export_transactions_csv(
        self,
        path: str | Path,
        transactions: Iterable[CompletedTransaction] | None = None,
    ) -> int:
        """Append new completed transactions and return the written row count.

        Existing transaction IDs are scanned so retries cannot duplicate rows.
        File-system errors are logged and converted to a zero-row result so they
        cannot stop recognition.
        """

        destination = Path(path)
        with self._lock:
            selected = list(self._transactions if transactions is None else transactions)
            if not selected:
                return 0
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                existing_ids = self._read_existing_ids(destination)
                new_rows: list[CompletedTransaction] = []
                pending_ids: set[str] = set()
                for transaction in selected:
                    transaction_id = transaction.transaction_id
                    if transaction_id in existing_ids or transaction_id in pending_ids:
                        continue
                    pending_ids.add(transaction_id)
                    new_rows.append(transaction)
                if not new_rows:
                    return 0
                needs_header = not destination.exists() or destination.stat().st_size == 0
                with destination.open("a", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=self.CSV_COLUMNS)
                    if needs_header:
                        writer.writeheader()
                    for transaction in new_rows:
                        writer.writerow(self._transaction_row(transaction)) # pyright: ignore[reportArgumentType]
                return len(new_rows)
            except (OSError, csv.Error, UnicodeError) as exc:
                LOGGER.warning("Không thể ghi lịch sử tính phí %s: %s", destination, exc)
                return 0

    def _apply_observation(
        self,
        observation: ParkingObservation,
        fallback_timestamp: float | None,
    ) -> CompletedTransaction | None:
        position_id = str(observation.position_id).strip()
        if not position_id:
            return None
        state = self._normalize_state(observation.state)
        if state is None:
            return None

        position = self._positions.setdefault(position_id, _PositionState())
        frame_id = observation.frame_id
        if frame_id is not None:
            if position.last_frame_id is not None and frame_id <= position.last_frame_id:
                return None
            position.last_frame_id = frame_id
        if not observation.measurement_valid:
            return None

        observed_at = self._observation_time(observation.timestamp, fallback_timestamp)
        if not math.isfinite(observed_at):
            return None
        if position.last_observation_at is not None and observed_at < position.last_observation_at:
            return None
        position.last_observation_at = observed_at

        if position.stable_state == state:
            self._clear_candidate(position)
            if state == "OCCUPIED" and position.active_session is not None:
                position.active_session.last_seen = observed_at
            return None

        if position.candidate_state != state:
            position.candidate_state = state
            position.candidate_count = 1
            position.candidate_since = observed_at
        else:
            position.candidate_count += 1

        if position.candidate_count < self.config.debounce_observations:
            return None

        if state == "EMPTY" and position.active_session is not None:
            unseen_for = observed_at - position.active_session.last_seen
            if unseen_for < self.config.grace_period_seconds:
                return None

        candidate_since = position.candidate_since
        position.stable_state = state
        self._clear_candidate(position)
        if state == "OCCUPIED":
            started_at = observed_at if candidate_since is None else candidate_since
            tx_id = uuid.uuid4().hex
            position.active_session = ActiveParkingSession(
                run_id=self._run_id,
                position_id=position_id,
                started_at=started_at,
                last_seen=observed_at,
                transaction_id=tx_id,
            )
            if getattr(self, 'db_manager', None):
                self.db_manager.upsert_active_parking_session(
                    transaction_id=tx_id,
                    run_id=self._run_id,
                    input_mode=self._input_mode,
                    input_source=self._input_source,
                    slot_id=position_id,
                    gio_vao=started_at,
                    user_id=getattr(self, 'db_user_id', None)
                )
            return None

        session = position.active_session
        position.active_session = None
        if session is None:
            return None
        ended_at = max(session.started_at, session.last_seen)
        duration = ended_at - session.started_at
        tx_id = session.transaction_id or uuid.uuid4().hex
        transaction = CompletedTransaction(
            transaction_id=tx_id,
            run_id=self._run_id,
            timestamp=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            input_mode=self._input_mode,
            input_source=self._input_source,
            position_id=position_id,
            started_at=session.started_at,
            ended_at=ended_at,
            source_start_seconds=session.started_at,
            source_end_seconds=ended_at,
            duration_seconds=duration,
            hourly_rate_vnd=self.config.hourly_rate_vnd,
            rounding_vnd=self.config.rounding_vnd,
            fee_vnd=self.calculate_fee(duration),
        )
        self._transactions.append(transaction)
        self._total_revenue_vnd += transaction.fee_vnd
        
        if getattr(self, 'db_manager', None):
            self.db_manager.complete_parking_session(
                transaction_id=transaction.transaction_id,
                gio_ra=transaction.ended_at,
                duration=transaction.duration_seconds,
                fee=transaction.fee_vnd,
                reason=transaction.completion_reason
            )
            
        return transaction

    def _observation_time(
        self,
        observation_timestamp: float | None,
        fallback_timestamp: float | None,
    ) -> float:
        if observation_timestamp is not None:
            return float(observation_timestamp)
        if fallback_timestamp is not None:
            return float(fallback_timestamp)
        if self._is_video_mode():
            raise ValueError("Video billing requires source_time_seconds")
        return float(self._clock())

    def _is_video_mode(self) -> bool:
        return self._input_mode.casefold() == "video"

    @staticmethod
    def _normalize_state(state: str) -> str | None:
        value = str(state).strip().upper()
        if value in {"OCCUPIED", "EMPTY"}:
            return value
        return None

    @staticmethod
    def _clear_candidate(position: _PositionState) -> None:
        position.candidate_state = None
        position.candidate_count = 0
        position.candidate_since = None

    @staticmethod
    def _read_existing_ids(path: Path) -> set[str]:
        if not path.exists() or path.stat().st_size == 0:
            return set()
        with path.open("r", newline="", encoding="utf-8") as handle:
            return {
                str(row.get("transaction_id", ""))
                for row in csv.DictReader(handle)
                if row.get("transaction_id")
            }

    @staticmethod
    def _csv_safe(value: str) -> str:
        text = str(value)
        if text.startswith(("=", "+", "-", "@")):
            return "'" + text
        return text

    def _transaction_row(self, transaction: CompletedTransaction) -> dict[str, object]:
        return {
            "transaction_id": self._csv_safe(transaction.transaction_id),
            "run_id": self._csv_safe(transaction.run_id),
            "timestamp": self._csv_safe(transaction.timestamp),
            "input_mode": self._csv_safe(transaction.input_mode),
            "input_source": self._csv_safe(transaction.input_source),
            "position_id": self._csv_safe(transaction.position_id),
            "started_at": transaction.started_at,
            "ended_at": transaction.ended_at,
            "source_start_seconds": transaction.source_start_seconds,
            "source_end_seconds": transaction.source_end_seconds,
            "duration_seconds": transaction.duration_seconds,
            "hourly_rate_vnd": transaction.hourly_rate_vnd,
            "rounding_vnd": transaction.rounding_vnd,
            "fee_vnd": transaction.fee_vnd,
            "completion_reason": self._csv_safe(transaction.completion_reason),
        }


Box = tuple[float, float, float, float]


@dataclass(slots=True)
class _VideoTrack:
    position_id: str
    box: Box
    first_seen: float
    last_seen: float
    observations: int = 1
    confirmed: bool = False
    published: bool = False
    empty_observations: int = 0


class VideoTrackAssigner:
    """Small one-to-one IoU/center tracker for parked-vehicle boxes only."""

    def __init__(
        self,
        config: BillingConfig | None = None,
        *,
        iou_threshold: float = 0.20,
        center_distance_threshold: float = 80.0,
    ) -> None:
        self.config = config or BillingConfig()
        self.iou_threshold = float(iou_threshold)
        self.center_distance_threshold = float(center_distance_threshold)
        self._tracks: dict[str, _VideoTrack] = {}
        self._next_track_number = 1

    def reset(self) -> None:
        self._tracks.clear()
        self._next_track_number = 1

    @property
    def track_boxes(self) -> dict[str, Box]:
        """Return confirmed track boxes for optional, non-invasive overlays."""

        return {
            track_id: track.box
            for track_id, track in self._tracks.items()
            if track.confirmed
        }

    def update(
        self,
        boxes: Iterable[Sequence[float]],
        timestamp: float,
        measurement_valid: bool = True,
        frame_id: int | None = None,
    ) -> list[ParkingObservation]:
        """Assign boxes and emit debounced OCCUPIED/EMPTY observations.

        Invalid measurements neither age nor mutate tracks.  A confirmed track
        emits EMPTY only after it has exceeded the grace period; it is retained
        for enough EMPTY observations to cooperate with ``BillingManager``'s
        debounce and permit a late recovery without a false charge.
        """

        if not measurement_valid:
            return []
        now = float(timestamp)
        if not math.isfinite(now):
            return []
        normalized_boxes = [self._normalize_box(box) for box in boxes]
        normalized_boxes = [box for box in normalized_boxes if box is not None]

        matched_tracks: set[str] = set()
        matched_boxes: set[int] = set()
        candidates: list[tuple[float, float, str, int]] = []
        for track_id, track in self._tracks.items():
            for box_index, box in enumerate(normalized_boxes):
                iou = self._iou(track.box, box)
                distance = self._center_distance(track.box, box)
                if iou >= self.iou_threshold or distance <= self.center_distance_threshold:
                    candidates.append((-iou, distance, track_id, box_index))
        candidates.sort()

        for _negative_iou, _distance, track_id, box_index in candidates:
            if track_id in matched_tracks or box_index in matched_boxes:
                continue
            matched_tracks.add(track_id)
            matched_boxes.add(box_index)
            track = self._tracks[track_id]
            track.box = normalized_boxes[box_index]
            track.last_seen = now
            track.observations += 1
            track.empty_observations = 0
            if track.observations >= self.config.debounce_observations:
                track.confirmed = True

        for box_index, box in enumerate(normalized_boxes):
            if box_index in matched_boxes:
                continue
            track_id = f"V{self._next_track_number:02d}"
            self._next_track_number += 1
            confirmed = self.config.debounce_observations == 1
            self._tracks[track_id] = _VideoTrack(
                position_id=track_id,
                box=box,
                first_seen=now,
                last_seen=now,
                confirmed=confirmed,
            )
            matched_tracks.add(track_id)

        observations: list[ParkingObservation] = []
        expired_tracks: list[str] = []
        for track_id, track in self._tracks.items():
            if track_id in matched_tracks:
                if not track.confirmed:
                    continue
                observation_time = now if track.published else track.first_seen
                track.published = True
                observations.append(
                    ParkingObservation(
                        position_id=track_id,
                        state="OCCUPIED",
                        timestamp=observation_time,
                        frame_id=frame_id,
                    )
                )
                continue

            missing_seconds = now - track.last_seen
            if missing_seconds <= self.config.grace_period_seconds:
                continue
            if not track.confirmed:
                expired_tracks.append(track_id)
                continue
            track.empty_observations += 1
            observations.append(
                ParkingObservation(
                    position_id=track_id,
                    state="EMPTY",
                    timestamp=now,
                    frame_id=frame_id,
                )
            )
            if track.empty_observations >= self.config.debounce_observations:
                expired_tracks.append(track_id)

        for track_id in expired_tracks:
            self._tracks.pop(track_id, None)
        return observations

    @staticmethod
    def _normalize_box(box: Sequence[float]) -> Box | None:
        if len(box) < 4:
            return None
        try:
            x1, y1, x2, y2 = (float(box[index]) for index in range(4))
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            return None
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        if right <= left or bottom <= top:
            return None
        return left, top, right, bottom

    @staticmethod
    def _iou(first: Box, second: Box) -> float:
        left = max(first[0], second[0])
        top = max(first[1], second[1])
        right = min(first[2], second[2])
        bottom = min(first[3], second[3])
        intersection = max(0.0, right - left) * max(0.0, bottom - top)
        first_area = (first[2] - first[0]) * (first[3] - first[1])
        second_area = (second[2] - second[0]) * (second[3] - second[1])
        union = first_area + second_area - intersection
        return intersection / union if union > 0.0 else 0.0

    @staticmethod
    def _center_distance(first: Box, second: Box) -> float:
        first_x = (first[0] + first[2]) / 2.0
        first_y = (first[1] + first[3]) / 2.0
        second_x = (second[0] + second[2]) / 2.0
        second_y = (second[1] + second[3]) / 2.0
        return math.hypot(first_x - second_x, first_y - second_y)


__all__ = [
    "ActiveParkingSession",
    "BillingConfig",
    "BillingManager",
    "BillingSnapshot",
    "CompletedTransaction",
    "ParkingObservation",
    "VideoTrackAssigner",
    "calculate_fee",
    "format_duration",
    "format_vnd",
]
