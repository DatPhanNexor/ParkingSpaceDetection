import datetime

def get_since_datetime(since: str = None) -> datetime.datetime | None:
    if not since:
        return None
    try:
        dt = datetime.datetime.fromisoformat(since.replace('Z', '+00:00'))
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt
    except:
        return None
import json
import asyncio
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any
import csv
import io
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("reporting_service")

from shared.database import get_db_connection, redis_client
from shared.security import get_current_user, require_role, decode_access_token

app = FastAPI(title="Dashboard and Reporting Service")

LIVE_SLOT_KEY_PREFIX = os.getenv("LIVE_OCCUPANCY_KEY_PREFIX", "parking:live:slot")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        stale = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)

manager = ConnectionManager()


async def _build_slots_snapshot() -> List[Dict[str, Any]]:
    slots = []
    for i in range(1, 10):
        slot_id = f"S0{i}"
        # Live occupancy is maintained by desktop-sync-service. Do not fall
        # back to session/billing Redis keys: those can be stale history.
        state = await redis_client.hgetall(f"{LIVE_SLOT_KEY_PREFIX}:{slot_id}")
        slots.append({
            "slot_id": slot_id,
            "status": state.get("status", "EMPTY") if state else "EMPTY",
            "session_id": state.get("session_id") if state else None,
            "started_at": state.get("started_at") if state else None,
            "updated_at": state.get("updated_at") if state else None,
        })
    return slots


async def _build_dashboard_snapshot() -> Dict[str, Any]:
    active_sessions = []
    summary = {"total_sessions": 0, "active_sessions": 0, "total_revenue": 0}
    alerts = []
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT slot_id, session_id, started_at FROM active_session_locks")
            active_rows = await cur.fetchall()
            active_sessions = [
                {"slot_id": r[0], "session_id": r[1], "started_at": _format_datetime(r[2])}
                for r in active_rows
            ]

            await cur.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM lich_su_xe) AS total_sessions,
                    (SELECT COUNT(*) FROM active_session_locks) AS active_sessions,
                    (SELECT COALESCE(SUM(thanh_tien), 0) FROM lich_su_xe WHERE gio_ra IS NOT NULL) AS total_revenue
                """
            )
            row = await cur.fetchone()
            if row:
                summary = {"total_sessions": row[0], "active_sessions": row[1], "total_revenue": row[2]}

            await cur.execute("SELECT id, level, source, message, created_at FROM system_alerts ORDER BY created_at DESC LIMIT 10")
            alert_rows = await cur.fetchall()
            alerts = [
                {"id": r[0], "level": r[1], "source": r[2], "message": r[3], "created_at": _format_datetime(r[4])}
                for r in alert_rows
            ]

    return {
        "type": "parking.snapshot",
        "slots": await _build_slots_snapshot(),
        "active_sessions": active_sessions,
        "summary": summary,
        "alerts": alerts,
    }


def _format_datetime(dt: datetime.datetime | None) -> str | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.isoformat()

def _json_serial(obj):
    if isinstance(obj, datetime.datetime):
        return _format_datetime(obj)
    return str(obj)

def _json_text(data: Dict[str, Any]) -> str:
    return json.dumps(data, default=_json_serial, ensure_ascii=False)

@app.get("/health")
def health():
    return {"status": "up"}

@app.get("/ready")
def ready():
    return {"status": "ready"}

@app.get("/metrics")
def metrics():
    return {"active_websocket_connections": len(manager.active_connections)}

@app.get("/api/v1/slots")
async def get_slots(current_user: dict = Depends(get_current_user)):
    return await _build_slots_snapshot()

@app.get("/api/v1/slots/{slot_id}")
async def get_slot(slot_id: str, current_user: dict = Depends(get_current_user)):
    if slot_id not in {f"S0{i}" for i in range(1, 10)}:
        raise HTTPException(status_code=404, detail="Slot not found")
    state = await redis_client.hgetall(f"{LIVE_SLOT_KEY_PREFIX}:{slot_id}")
    return {
        "slot_id": slot_id,
        "status": state.get("status", "EMPTY") if state else "EMPTY",
        "session_id": state.get("session_id") if state else None,
        "started_at": state.get("started_at") if state else None,
        "updated_at": state.get("updated_at") if state else None,
    }

@app.get("/api/v1/sessions/active")
async def get_active_sessions(current_user: dict = Depends(get_current_user)):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT slot_id, session_id, started_at FROM active_session_locks")
            rows = await cur.fetchall()
            return [{"slot_id": r[0], "session_id": r[1], "started_at": _format_datetime(r[2])} for r in rows]

@app.get("/api/v1/sessions/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT transaction_id, slot_id, gio_vao, gio_ra, thanh_tien FROM lich_su_xe ORDER BY gio_ra DESC LIMIT 50")
            rows = await cur.fetchall()
            return [{"transaction_id": r[0], "slot_id": r[1], "gio_vao": _format_datetime(r[2]), "gio_ra": _format_datetime(r[3]), "thanh_tien": r[4]} for r in rows]

@app.get("/api/v1/reports/summary")
async def get_summary(since: str = None, current_user: dict = Depends(require_role("admin"))):
    since_dt = get_since_datetime(since)
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            if since_dt:
                await cur.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM lich_su_xe WHERE gio_vao >= %s) AS total_sessions,
                        (SELECT COUNT(*) FROM active_session_locks WHERE started_at >= %s) AS active_sessions,
                        (SELECT COALESCE(SUM(thanh_tien), 0) FROM lich_su_xe WHERE gio_ra IS NOT NULL AND gio_vao >= %s) AS total_revenue
                    """, (since_dt, since_dt, since_dt)
                )
            else:
                await cur.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM lich_su_xe) AS total_sessions,
                        (SELECT COUNT(*) FROM active_session_locks) AS active_sessions,
                        (SELECT COALESCE(SUM(thanh_tien), 0) FROM lich_su_xe WHERE gio_ra IS NOT NULL) AS total_revenue
                    """
                )
            row = await cur.fetchone()
            if row:
                return {"total_sessions": row[0], "active_sessions": row[1], "total_revenue": row[2]}
            return {"total_sessions": 0, "active_sessions": 0, "total_revenue": 0}

@app.get("/api/v1/reports/revenue")
async def get_revenue(since: str = None, current_user: dict = Depends(require_role("admin"))):
    since_dt = get_since_datetime(since)
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            if since_dt:
                await cur.execute("""
                    SELECT slot_id, COUNT(*) AS so_luot, SUM(thanh_tien) AS doanh_thu
                    FROM lich_su_xe
                    WHERE gio_vao >= %s
                    GROUP BY slot_id
                """, (since_dt,))
            else:
                await cur.execute("SELECT slot_id, so_luot, doanh_thu FROM vw_doanh_thu_theo_slot")
            rows = await cur.fetchall()
            return [{"slot_id": r[0], "sessions": r[1], "revenue": r[2] or 0} for r in rows]

@app.get("/api/v1/reports/frequency")
async def get_frequency(since: str = None, current_user: dict = Depends(require_role("admin"))):
    since_dt = get_since_datetime(since)
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            if since_dt:
                await cur.execute("""
                    SELECT slot_id, COUNT(*) AS so_luot
                    FROM lich_su_xe
                    WHERE gio_vao >= %s
                    GROUP BY slot_id
                """, (since_dt,))
            else:
                await cur.execute("SELECT slot_id, so_luot FROM vw_tan_suat_theo_slot")
            rows = await cur.fetchall()
            return [{"slot_id": r[0], "sessions": r[1]} for r in rows]

@app.get("/api/v1/reports/export.csv")
async def export_csv(current_user: dict = Depends(require_role("admin"))):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT transaction_id, slot_id, gio_vao, gio_ra, thanh_tien FROM lich_su_xe ORDER BY gio_vao DESC")
            rows = await cur.fetchall()
            
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["transaction_id", "slot_id", "gio_vao", "gio_ra", "thanh_tien"])
    for row in rows:
        writer.writerow(row)
        
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=export.csv"})

@app.get("/api/v1/alerts")
async def get_alerts(current_user: dict = Depends(get_current_user)):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, level, source, message, created_at FROM system_alerts ORDER BY created_at DESC LIMIT 50")
            rows = await cur.fetchall()
            return [{"id": r[0], "level": r[1], "source": r[2], "message": r[3], "created_at": _format_datetime(r[4])} for r in rows]

@app.websocket("/ws/parking")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        user = decode_access_token(token)
    except Exception:
        await websocket.close(code=1008)
        return
        
    await manager.connect(websocket)
    try:
        await websocket.send_text(_json_text(await _build_dashboard_snapshot()))
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                if data:
                    try:
                        decoded = json.loads(data)
                    except json.JSONDecodeError:
                        decoded = {"type": "text"}
                    if decoded.get("type") == "client_ping":
                        await websocket.send_text(_json_text({"type": "server_pong"}))
            except asyncio.TimeoutError:
                await websocket.send_text(_json_text(await _build_dashboard_snapshot()))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WebSocket connection closed with error: %s", exc)
        manager.disconnect(websocket)

@app.delete("/api/v1/sessions/history/{transaction_id}")
async def delete_history_session(transaction_id: str, current_user: dict = Depends(require_role("admin"))):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT transaction_id FROM lich_su_xe WHERE transaction_id = %s", (transaction_id,))
            if not await cur.fetchone():
                return {"status": "success", "message": "Record not found"}
            await cur.execute("DELETE FROM lich_su_xe WHERE transaction_id = %s", (transaction_id,))
            await conn.commit()
    return {"status": "success", "message": "History record deleted successfully"}

from pydantic import BaseModel
class BatchDeleteRequest(BaseModel):
    transaction_ids: list[str]

@app.delete("/api/v1/sessions/history")
async def batch_delete_history(req: BatchDeleteRequest, current_user: dict = Depends(require_role("admin"))):
    if not req.transaction_ids:
        return {"status": "success", "message": "No records to delete", "deleted_count": 0}
        
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            format_strings = ','.join(['%s'] * len(req.transaction_ids))
            await cur.execute(f"DELETE FROM lich_su_xe WHERE transaction_id IN ({format_strings})", tuple(req.transaction_ids))
            deleted_count = cur.rowcount
            await conn.commit()
    return {"status": "success", "message": f"Deleted {deleted_count} records", "deleted_count": deleted_count}
