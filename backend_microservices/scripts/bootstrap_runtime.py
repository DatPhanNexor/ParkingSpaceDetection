import asyncio
import datetime
import os

import aiomysql
import redis.asyncio as redis

from shared.security import get_password_hash


TRUE_VALUES = {"1", "true", "yes", "on"}


async def _connect_mysql() -> aiomysql.Connection:
    last_error = None
    for _ in range(45):
        try:
            return await aiomysql.connect(
                host=os.environ["DB_HOST"],
                port=int(os.environ["DB_PORT"]),
                user=os.environ["DB_USER"],
                password=os.environ.get("DB_PASSWORD", ""),
                db=os.environ["DB_NAME"],
                charset="utf8mb4",
                autocommit=False,
            )
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(2)
    raise RuntimeError(f"MySQL is not ready: {last_error}")


async def _bootstrap_admin(connection: aiomysql.Connection) -> None:
    enabled = os.getenv("BOOTSTRAP_ADMIN_ENABLED", "false").lower() in TRUE_VALUES
    if not enabled:
        print("[bootstrap] Admin account bootstrap is disabled", flush=True)
        return

    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    full_name = os.getenv("BOOTSTRAP_ADMIN_FULL_NAME", "").strip()
    if not username or not password or not full_name:
        raise RuntimeError("Enabled admin bootstrap requires username, password, and full name")

    async with connection.cursor() as cursor:
        await cursor.execute(
            "SELECT id FROM tai_khoan WHERE username = %s LIMIT 1",
            (username,),
        )
        existing = await cursor.fetchone()
        if existing is not None:
            print(f"[bootstrap] Existing account preserved: {username}", flush=True)
            return

        await cursor.execute(
            """
            INSERT INTO tai_khoan
                (username, password_hash, ho_ten, role, is_active)
            VALUES (%s, %s, %s, 'admin', 1)
            """,
            (username, get_password_hash(password), full_name),
        )
        print(f"[bootstrap] Created admin account: {username}", flush=True)


async def _bootstrap_redis_slots() -> None:
    cache = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for index in range(1, 10):
            slot_id = f"S{index:02d}"
            key = f"parking:slot:{slot_id}"
            if not await cache.exists(key):
                await cache.hset(
                    key,
                    mapping={
                        "status": "EMPTY",
                        "session_id": "",
                        "started_at": "",
                        "updated_at": now,
                    },
                )
        print("[bootstrap] Redis slots S01-S09 are ready", flush=True)
    finally:
        await cache.aclose()


async def main() -> None:
    connection = await _connect_mysql()
    try:
        await _bootstrap_admin(connection)
        await connection.commit()
    except Exception:
        await connection.rollback()
        raise
    finally:
        connection.close()

    await _bootstrap_redis_slots()


if __name__ == "__main__":
    asyncio.run(main())
