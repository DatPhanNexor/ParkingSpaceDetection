"""Provision a least-privilege application user on the host MySQL server."""

import argparse
import os
import re
from pathlib import Path

import mysql.connector


SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+$")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def require_identifier(value: str, label: str) -> str:
    if not SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {label}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "infrastructure" / ".env",
    )
    args = parser.parse_args()

    values = load_env(args.env_file)
    database = require_identifier(values["AI_PARKING_DB_NAME"], "database name")
    app_user = require_identifier(values["AI_PARKING_DB_USER"], "application user")
    app_password = values.get("AI_PARKING_DB_PASSWORD", "")
    if not app_password:
        raise ValueError("AI_PARKING_DB_PASSWORD must not be empty")

    admin_host = os.getenv("HOST_DB_ADMIN_HOST", "127.0.0.1")
    admin_port = int(os.getenv("HOST_DB_ADMIN_PORT", "3306"))
    admin_user = os.getenv("HOST_DB_ADMIN_USER", "root")
    admin_password = os.getenv("HOST_DB_ADMIN_PASSWORD", "")

    connection = mysql.connector.connect(
        host=admin_host,
        port=admin_port,
        user=admin_user,
        password=admin_password,
        connection_timeout=5,
    )
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(
                "SELECT 1 FROM mysql.user WHERE User = %s AND Host = '%' LIMIT 1",
                (app_user,),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    f"CREATE USER '{app_user}'@'%' IDENTIFIED BY %s",
                    (app_password,),
                )
                print(f"Created MySQL application user: {app_user}@%")
            else:
                print(f"Preserved existing MySQL application user: {app_user}@%")

            cursor.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, "
                f"REFERENCES, CREATE VIEW, SHOW VIEW ON `{database}`.* "
                f"TO '{app_user}'@'%'"
            )
            connection.commit()
        finally:
            cursor.close()
    finally:
        connection.close()

    verification = mysql.connector.connect(
        host=admin_host,
        port=admin_port,
        user=app_user,
        password=app_password,
        database=database,
        connection_timeout=5,
    )
    try:
        cursor = verification.cursor()
        try:
            cursor.execute("SELECT DATABASE(), @@hostname, @@port")
            db_name, hostname, port = cursor.fetchone()
            print(f"Verified application connection: {db_name} on {hostname}:{port}")
        finally:
            cursor.close()
    finally:
        verification.close()


if __name__ == "__main__":
    main()
