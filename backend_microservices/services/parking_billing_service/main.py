import os
import json
import asyncio
import uuid
import datetime
import logging
from fastapi import FastAPI, BackgroundTasks
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
from contextlib import asynccontextmanager

from shared.events import (
    EventEnvelope, DetectionCompletedPayload, SlotStatus, get_publisher
)
from shared.database import get_db_connection, get_db_transaction, redis_client, acquire_lock

from shared.database import get_db_connection, get_db_transaction, redis_client, acquire_lock

async def process_detection_event(event: EventEnvelope):
    payload = DetectionCompletedPayload(**event.payload)
    slot_id = payload.slot_id
    status = payload.status.value
    event_id = event.event_id
    
    # Extract explicitly requested parameters
    observed_at_utc = event.occurred_at
    source_elapsed_seconds = payload.source_elapsed_seconds if hasattr(payload, 'source_elapsed_seconds') else 0
    
    logger.info(f"Processing event {event_id} for slot {slot_id} with status {status}")
    
    # 1. Idempotency Check in MySQL
    async with get_db_transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT event_id FROM processed_events WHERE event_id = %s", (event_id,))
            if await cur.fetchone():
                return # Already processed
                
            await cur.execute(
                "INSERT INTO processed_events (event_id, event_type) VALUES (%s, %s)",
                (event_id, event.event_type)
            )
            
    # 2. Redis Distributed Lock for the slot
    lock_key = f"parking:lock:{slot_id}"
    async with acquire_lock(lock_key, timeout=5) as acquired:
        if not acquired:
            # Requeue or let it timeout/retry in RMQ DLQ
            raise Exception(f"Could not acquire lock for {slot_id}")
            
        # 3. Check current state in Redis
        state_key = f"parking:slot:{slot_id}"
        current_state = await redis_client.hgetall(state_key)
        
        current_status = current_state.get("status", "EMPTY")
        current_session = current_state.get("session_id")
        
        # 4. Handle State Transition
        if status == "OCCUPIED" and current_status == "EMPTY":
            # New Session
            session_id = str(uuid.uuid4())
            started_at = datetime.datetime.utcnow().isoformat()
            
            # Update Redis
            await redis_client.hmset(state_key, {
                "status": "OCCUPIED",
                "session_id": session_id,
                "started_at": started_at
            })
            
            # Persist to MySQL and Outbox in transaction
            async with get_db_transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO active_session_locks (slot_id, session_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE session_id=VALUES(session_id)",
                        (slot_id, session_id)
                    )
                    
                    # Outbox event for session.started
                    outbox_payload = {
                        "session_id": session_id,
                        "slot_id": slot_id,
                        "started_at": started_at
                    }
                    await cur.execute(
                        "INSERT INTO outbox_events (event_type, payload) VALUES (%s, %s)",
                        ("parking.session.started", json.dumps(outbox_payload))
                    )
                    
        elif status == "EMPTY" and current_status == "OCCUPIED" and current_session:
            # End Session
            ended_at_dt = datetime.datetime.utcnow()
            ended_at = ended_at_dt.isoformat()
            started_at_str = current_state.get("started_at")
            started_at_dt = datetime.datetime.fromisoformat(started_at_str)
            
            duration_seconds = int((ended_at_dt - started_at_dt).total_seconds())
            
            # Read pricing from DB
            async with get_db_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT gia_moi_gio, buoc_lam_tron, phi_toi_thieu FROM cau_hinh LIMIT 1")
                    config = await cur.fetchone()
                    if not config:
                        config = (20000, 5000, 5000) # Default
            
            gia_moi_gio, buoc_lam_tron, phi_toi_thieu = config
            hours = max(1, (duration_seconds / 3600))
            raw_fee = hours * gia_moi_gio
            
            # Rounding
            fee = int(round(raw_fee / buoc_lam_tron) * buoc_lam_tron)
            fee = max(fee, phi_toi_thieu)
            
            # Update Redis
            await redis_client.hmset(state_key, {
                "status": "EMPTY",
                "session_id": "",
                "started_at": ""
            })
            
            # Persist to MySQL
            async with get_db_transaction() as conn:
                async with conn.cursor() as cur:
                    # Remove lock
                    await cur.execute("DELETE FROM active_session_locks WHERE slot_id = %s", (slot_id,))
                    
                    # Insert history
                    await cur.execute(
                        """
                        INSERT INTO lich_su_xe 
                        (transaction_id, input_mode, slot_id, gio_vao, gio_ra, so_giay, gia_moi_gio, buoc_lam_tron, thanh_tien)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (current_session, "WEBCAM", slot_id, started_at_dt, ended_at_dt, duration_seconds, gia_moi_gio, buoc_lam_tron, fee)
                    )
                    
                    # Outbox event
                    outbox_payload = {
                        "session_id": current_session,
                        "slot_id": slot_id,
                        "started_at": started_at_str,
                        "ended_at": ended_at,
                        "duration_seconds": duration_seconds,
                        "amount": fee
                    }
                    await cur.execute(
                        "INSERT INTO outbox_events (event_type, payload) VALUES (%s, %s)",
                        ("parking.session.completed", json.dumps(outbox_payload))
                    )

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
                async with message.process(ignore_processed=True):
                    try:
                        body = json.loads(message.body.decode())
                        envelope = EventEnvelope(**body)
                        await process_detection_event(envelope)
                        await message.ack()
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        # Reject without requeue sends to DLX
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
                await redis_client.hmset(state_key, {
                    "status": "OCCUPIED",
                    "session_id": row[1],
                    "started_at": row[2].isoformat() if row[2] else ""
                })
                
    task = asyncio.create_task(consume_events())
    yield
    task.cancel()
    
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

