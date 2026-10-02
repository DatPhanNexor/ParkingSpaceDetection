"""Ingress adapter for the existing Desktop detector live-state contract.

It adapts the Desktop application's already-debounced Webcam output into the
live Redis keys consumed by reporting and the WebSocket. The mobile API never
uses its session/history endpoints for slot colors.
"""

from __future__ import annotations

import os
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.database import get_db_connection, redis_client

SLOT_IDS = tuple(f"S{i:02d}" for i in range(1, 10))
LIVE_KEY_PREFIX = os.getenv("LIVE_OCCUPANCY_KEY_PREFIX", "parking:live:slot")
LIVE_META_KEY = os.getenv("LIVE_OCCUPANCY_META_KEY", "parking:live:meta")
SYNC_INTERVAL_SECONDS = max(float(os.getenv("DESKTOP_SYNC_INTERVAL_SECONDS", "0.5")), 0.2)
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
    """Map detector region ids (1..9) and S01..S09 to the domain code."""

    text = str(raw).strip().upper() if raw is not None else ""
    if text.startswith("S"):
        text = text[1:]
    try:
        number = int(text)
    except (TypeError, ValueError):
        return None
    return f"S{number:02d}" if 1 <= number <= 9 else None


def snapshot_from_desktop_rows(rows: list[tuple[Any, ...]]) -> OccupancySnapshot:
    """Adapt the Desktop app's existing debounced Webcam observations."""

    slots = {
        slot_id: SlotSnapshot(slot_id=slot_id, status="EMPTY") for slot_id in SLOT_IDS
    }
    for _run_id, transaction_id, raw_slot_id, started_at, ended_at, updated_at in rows:
        slot_id = normalize_slot_id(raw_slot_id)
        if slot_id is None:
            continue
        if ended_at is None:
            slots[slot_id] = SlotSnapshot(
                slot_id=slot_id,
                status="OCCUPIED",
                session_id=str(transaction_id) if transaction_id is not None else None,
                started_at=str(started_at) if started_at is not None else None,
                updated_at=str(updated_at) if updated_at is not None else None,
            )
        else:
            # The newest completed observation must clear a prior occupied row.
            slots[slot_id] = SlotSnapshot(
                slot_id=slot_id,
                status="EMPTY",
                updated_at=str(updated_at) if updated_at is not None else None,
            )
    return OccupancySnapshot(slots=list(slots.values()))


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
    pipe = redis_client.pipeline(transaction=True)
    for slot_id in SLOT_IDS:
        slot = normalized[slot_id]
        pipe.hset(f"{LIVE_KEY_PREFIX}:{slot_id}", mapping={
            "status": slot.status,
            "session_id": slot.session_id or "",
            "started_at": slot.started_at or "",
            "updated_at": slot.updated_at or observed_at,
            "observed_at": observed_at,
            "source": "desktop-droidcam",
        })
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


async def _sync_desktop_run() -> None:
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT run_id
                FROM lich_su_xe
                WHERE input_mode = 'Webcam' AND run_id IS NOT NULL
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            )
            latest = await cur.fetchone()
            if latest is None:
                # No Desktop run has produced an observation yet. Clear any
                # previous live state instead of presenting it as current.
                observed_at = datetime.now(timezone.utc).isoformat()
                pipe = redis_client.pipeline(transaction=True)
                for slot_id in SLOT_IDS:
                    pipe.hset(
                        f"{LIVE_KEY_PREFIX}:{slot_id}",
                        mapping={
                            "status": "UNKNOWN",
                            "session_id": "",
                            "started_at": "",
                            "updated_at": observed_at,
                            "observed_at": observed_at,
                            "source": "desktop-droidcam",
                        },
                    )
                pipe.hset(
                    LIVE_META_KEY,
                    mapping={"observed_at": observed_at, "source": "desktop-droidcam"},
                )
                await pipe.execute()
                _last_snapshot.clear()
                _last_snapshot.update({"run_id": None, "observed_at": observed_at, "slots": []})
                return
            else:
                run_id = str(latest[0])
                await cur.execute(
                    """
                    SELECT run_id, transaction_id, slot_id, gio_vao, gio_ra, updated_at
                    FROM lich_su_xe
                    WHERE input_mode = 'Webcam' AND run_id = %s
                    ORDER BY updated_at ASC, id ASC
                    """,
                    (latest[0],),
                )
                rows = await cur.fetchall()

    snapshot = snapshot_from_desktop_rows(list(rows)).model_copy(
        update={"observed_at": datetime.now(timezone.utc).isoformat()}
    )
    payload = await publish_snapshot(snapshot)
    _last_snapshot.clear()
    _last_snapshot.update({**payload, "run_id": run_id})


async def _sync_loop() -> None:
    while True:
        try:
            await _sync_desktop_run()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Keep the last known detector snapshot through a temporary DB outage.
            pass
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_sync_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Desktop Live Occupancy Sync", lifespan=lifespan)


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
