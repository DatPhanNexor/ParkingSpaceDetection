import os
import json
import asyncio
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any
import csv
import io
import logging
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "ai_parking_system"
    redis_url: str = "redis://127.0.0.1:6380/0"
    jwt_secret: str = "supersecret123"

    class Config:
        env_file = ".env"

settings = Settings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("reporting_service")

from shared.database import get_db_connection, redis_client
from shared.security import get_current_user, require_role, decode_access_token

app = FastAPI(title="Dashboard and Reporting Service")

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
        state = await redis_client.hgetall(f"parking:slot:{slot_id}")
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
                {"slot_id": r[0], "session_id": r[1], "started_at": r[2]}
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
                {"id": r[0], "level": r[1], "source": r[2], "message": r[3], "created_at": r[4]}
                for r in alert_rows
            ]

    return {
        "type": "parking.snapshot",
        "slots": await _build_slots_snapshot(),
        "active_sessions": active_sessions,
        "summary": summary,
        "alerts": alerts,
    }


def _json_text(data: Dict[str, Any]) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)

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
    state = await redis_client.hgetall(f"parking:slot:{slot_id}")
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
            return [{"slot_id": r[0], "session_id": r[1], "started_at": r[2]} for r in rows]

@app.get("/api/v1/sessions/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT transaction_id, slot_id, gio_vao, gio_ra, thanh_tien FROM lich_su_xe ORDER BY gio_ra DESC LIMIT 50")
            rows = await cur.fetchall()
            return [{"transaction_id": r[0], "slot_id": r[1], "gio_vao": r[2], "gio_ra": r[3], "thanh_tien": r[4]} for r in rows]

@app.get("/api/v1/reports/summary")
async def get_summary(current_user: dict = Depends(require_role("admin"))):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
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
async def get_revenue(current_user: dict = Depends(require_role("admin"))):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT slot_id, so_luot, doanh_thu FROM vw_doanh_thu_theo_slot")
            rows = await cur.fetchall()
            return [{"slot_id": r[0], "sessions": r[1], "revenue": r[2]} for r in rows]

@app.get("/api/v1/reports/frequency")
async def get_frequency(current_user: dict = Depends(require_role("admin"))):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
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
            return [{"id": r[0], "level": r[1], "source": r[2], "message": r[3], "created_at": r[4]} for r in rows]

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
                data = await asyncio.wait_for(websocket.receive_text(), timeout=3.0)
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
