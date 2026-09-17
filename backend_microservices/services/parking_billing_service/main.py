import os
import json
import asyncio
import uuid
import datetime
import logging
from contextlib import asynccontextmanager, suppress
from typing import Optional

from fastapi import FastAPI
from pydantic_settings import BaseSettings
import aio_pika

class Settings(BaseSettings):
    rabbitmq_url: str = "amqp://guest:guest@127.0.0.1:5673/"
    redis_url: str = "redis://127.0.0.1:6380/0"
    
    class Config:
        env_file = ".env"

settings = Settings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("parking_billing")

from shared.events import (
    EventEnvelope, DetectionCompletedPayload, SlotStatus, get_publisher
)
from shared.database import get_db_connection, get_db_transaction, redis_client, acquire_lock
from adapters.legacy_billing_adapter import calculate_fee, BillingConfig


def _utc_now_naive() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _parse_event_time(value: Optional[str]) -> datetime.datetime:
    if not value:
        return _utc_now_naive()
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        logger.warning("Invalid event timestamp received; using server time")
        return _utc_now_naive()


async def _mark_processed(cur, event: EventEnvelope) -> None:
    await cur.execute(
        "INSERT IGNORE INTO processed_events (event_id, event_type) VALUES (%s, %s)",
        (event.event_id, event.event_type),
    )


async def _insert_outbox(cur, event_type: str, payload: dict) -> None:
    await cur.execute(
        "INSERT INTO outbox_events (event_type, payload) VALUES (%s, %s)",
        (event_type, json.dumps(payload, default=str)),
    )


async def process_detection_event(event: EventEnvelope):
    payload = DetectionCompletedPayload(**event.payload)
    slot_id = payload.slot_id
    status = payload.status.value
    event_id = event.event_id

    logger.info(f"Processing event {event_id} for slot {slot_id} with status {status}")

    if slot_id not in {f"S0{i}" for i in range(1, 10)}:
        logger.warning("Ignoring detection event %s for invalid slot %s", event_id, slot_id)
        return

    lock_key = f"parking:lock:{slot_id}"
    async with acquire_lock(lock_key, timeout=5) as acquired:
        if not acquired:
            raise RuntimeError(f"Could not acquire lock for {slot_id}")

        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT event_id FROM processed_events WHERE event_id = %s", (event_id,))
                if await cur.fetchone():
                    return

        if (
            not payload.measurement_valid
            or not payload.board_lock_valid
            or not payload.camera_ok
            or status not in {SlotStatus.EMPTY.value, SlotStatus.OCCUPIED.value}
        ):
            logger.info("Ignoring invalid measurement event %s for %s: %s", event_id, slot_id, payload.status_reason)
            async with get_db_transaction() as conn:
                async with conn.cursor() as cur:
                    await _mark_processed(cur, event)
            return

        state_key = f"parking:slot:{slot_id}"
        current_state = await redis_client.hgetall(state_key)
        current_status = current_state.get("status", "EMPTY")
        current_session = current_state.get("session_id")

        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT session_id, started_at FROM active_session_locks WHERE slot_id = %s",
                    (slot_id,),
                )
                active_row = await cur.fetchone()

        if active_row and current_status != "OCCUPIED":
            current_status = "OCCUPIED"
            current_session = active_row[0]
            await redis_client.hset(
                state_key,
                mapping={
                    "status": "OCCUPIED",
                    "session_id": active_row[0],
                    "started_at": active_row[1].isoformat() if active_row[1] else "",
                    "updated_at": _utc_now_naive().isoformat(),
                },
            )

        if status == "OCCUPIED" and current_status == "EMPTY":
            session_id = str(uuid.uuid4())
            started_at_dt = _parse_event_time(payload.observed_at_utc or event.occurred_at)
            started_at = started_at_dt.isoformat()

            await redis_client.hset(
                state_key,
                mapping={
                    "status": "OCCUPIED",
                    "session_id": session_id,
                    "started_at": started_at,
                    "updated_at": started_at,
                },
            )

            async with get_db_transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO active_session_locks (slot_id, session_id, started_at, locked_by_service)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (slot_id, session_id, started_at_dt, "parking-billing-service"),
                    )
                    slot_payload = {
                        "slot_id": slot_id,
                        "status": "OCCUPIED",
                        "updated_at": started_at,
                    }
                    session_payload = {
                        "session_id": session_id,
                        "slot_id": slot_id,
                        "started_at": started_at,
                    }
                    await _insert_outbox(cur, "parking.slot.updated", slot_payload)
                    await _insert_outbox(cur, "parking.session.started", session_payload)
                    await _mark_processed(cur, event)

        elif status == "EMPTY" and current_status == "OCCUPIED" and current_session:
            ended_at_dt = _parse_event_time(payload.observed_at_utc or event.occurred_at)
            ended_at = ended_at_dt.isoformat()
            started_at_str = current_state.get("started_at")
            if active_row and active_row[1]:
                started_at_dt = active_row[1]
            else:
                started_at_dt = _parse_event_time(started_at_str)

            duration_seconds = max(0, int((ended_at_dt - started_at_dt).total_seconds()))

            async with get_db_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT gia_moi_gio, buoc_lam_tron, phi_toi_thieu FROM cau_hinh LIMIT 1")
                    config = await cur.fetchone()
                    if not config:
                        config = (20000, 5000, 5000)

            gia_moi_gio, buoc_lam_tron, phi_toi_thieu = config
            billing_config = BillingConfig(
                hourly_rate_vnd=gia_moi_gio,
                rounding_vnd=buoc_lam_tron,
                minimum_fee_vnd=phi_toi_thieu,
            )
            fee = calculate_fee(duration_seconds, billing_config)

            await redis_client.hset(
                state_key,
                mapping={
                    "status": "EMPTY",
                    "session_id": "",
                    "started_at": "",
                    "updated_at": ended_at,
                },
            )

            async with get_db_transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM active_session_locks WHERE slot_id = %s", (slot_id,))
                    await cur.execute(
                        """
                        INSERT INTO lich_su_xe 
                        (transaction_id, input_mode, slot_id, gio_vao, gio_ra, so_giay, gia_moi_gio, buoc_lam_tron, thanh_tien)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            current_session,
                            payload.source_type,
                            slot_id,
                            started_at_dt,
                            ended_at_dt,
                            duration_seconds,
                            gia_moi_gio,
                            buoc_lam_tron,
                            fee,
                        ),
                    )
                    slot_payload = {
                        "slot_id": slot_id,
                        "status": "EMPTY",
                        "updated_at": ended_at,
                    }
                    session_payload = {
                        "session_id": current_session,
                        "slot_id": slot_id,
                        "started_at": started_at_str,
                        "ended_at": ended_at,
                        "duration_seconds": duration_seconds,
                    }
                    billing_payload = {
                        **session_payload,
                        "amount": fee,
                        "currency": "VND",
                        "calculated_at": ended_at,
                    }
                    await _insert_outbox(cur, "parking.slot.updated", slot_payload)
                    await _insert_outbox(cur, "parking.session.completed", session_payload)
                    await _insert_outbox(cur, "billing.completed", billing_payload)
                    await _mark_processed(cur, event)
        else:
            async with get_db_transaction() as conn:
                async with conn.cursor() as cur:
                    await _mark_processed(cur, event)

async def outbox_poller():
    publisher = await get_publisher()
    while True:
        try:
            async with get_db_connection() as conn:
                async with conn.cursor() as cur:
                    # Select pending events
                    await cur.execute("SELECT id, event_type, payload FROM outbox_events ORDER BY id ASC LIMIT 50")
                    rows = await cur.fetchall()
                    
                    if not rows:
                        await asyncio.sleep(2)
                        continue
                        
                    for row in rows:
                        event_id = row[0]
                        event_type = row[1]
                        payload_str = row[2]
                        
                        # Use outbox event ID as correlation
                        event = EventEnvelope(
                            event_type=event_type,
                            source="parking-billing-service",
                            payload=json.loads(payload_str),
                            correlation_id=str(event_id)
                        )
                        
                        # Publish to RMQ
                        await publisher.publish(event, routing_key=event_type)
                        
                        # Delete from outbox
                        await cur.execute("DELETE FROM outbox_events WHERE id = %s", (event_id,))
                    
                    await conn.commit()
        except Exception as e:
            logger.error(f"Outbox poller error: {e}")
            await asyncio.sleep(5)


async def consume_events():
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        
        exchange = await channel.declare_exchange("parking.events", aio_pika.ExchangeType.TOPIC, durable=True)
        
        # Dead Letter Exchange
        dlx = await channel.declare_exchange("parking.dlx", aio_pika.ExchangeType.FANOUT, durable=True)
        dlq = await channel.declare_queue("parking.dlq", durable=True)
        await dlq.bind(dlx)
        
        queue = await channel.declare_queue(
            "billing.worker.queue", 
            durable=True,
            arguments={
                "x-dead-letter-exchange": "parking.dlx"
            }
        )
        await queue.bind(exchange, routing_key="detection.*")
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                try:
                    body = json.loads(message.body.decode())
                    envelope = EventEnvelope(**body)
                    await process_detection_event(envelope)
                    await message.ack()
                except Exception as e:
                    logger.exception("Error processing RabbitMQ message: %s", e)
                    # Reject without requeue sends the failed message to the DLQ configured above.
                    await message.reject(requeue=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Restore Redis state from MySQL on startup
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT slot_id, session_id, started_at FROM active_session_locks")
            rows = await cur.fetchall()
            for row in rows:
                state_key = f"parking:slot:{row[0]}"
                started_at = row[2].isoformat() if row[2] else ""
                await redis_client.hset(
                    state_key,
                    mapping={
                        "status": "OCCUPIED",
                        "session_id": row[1],
                        "started_at": started_at,
                        "updated_at": started_at,
                    },
                )
                
    task = asyncio.create_task(consume_events())
    outbox_task = asyncio.create_task(outbox_poller())
    try:
        yield
    finally:
        task.cancel()
        outbox_task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        with suppress(asyncio.CancelledError):
            await outbox_task
    
app = FastAPI(title="Parking and Billing Service", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "up"}

@app.get("/ready")
def ready():
    return {"status": "ready"}

@app.get("/metrics")
def metrics():
    return {"events_processed": 0} # Stub
