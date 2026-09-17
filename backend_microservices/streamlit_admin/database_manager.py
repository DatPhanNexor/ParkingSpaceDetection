import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests


_CANONICAL_MANAGER = Path(__file__).with_name("canonical_database_manager.py")
_SPEC = importlib.util.spec_from_file_location(
    "canonical_desktop_database_manager",
    _CANONICAL_MANAGER,
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load canonical database manager: {_CANONICAL_MANAGER}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

DatabaseError = _MODULE.DatabaseError


class DatabaseManager(_MODULE.DatabaseManager):
    """Use Auth Service for login and the canonical MySQL for dashboard queries."""

    def __init__(self) -> None:
        super().__init__()
        self.auth_api_url = os.getenv(
            "AUTH_API_URL",
            "http://auth-service:8001/api/v1",
        ).rstrip("/")

    def authenticate_user(
        self,
        username: str,
        password_raw: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            login_response = requests.post(
                f"{self.auth_api_url}/auth/login",
                json={"username": username, "password": password_raw},
                timeout=8,
            )
            if login_response.status_code in {401, 403, 429}:
                return None
            login_response.raise_for_status()
            access_token = login_response.json()["access_token"]

            me_response = requests.get(
                f"{self.auth_api_url}/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=8,
            )
            me_response.raise_for_status()
            user = me_response.json()
            return {
                "user_id": user["id"],
                "username": user["username"],
                "ho_ten": user["ho_ten"],
                "role": user["role"],
            }
        except (KeyError, ValueError, requests.RequestException) as exc:
            raise DatabaseError(f"Authentication Service unavailable: {exc}") from exc

    def update_last_login(self, user_id: int) -> None:
        # Auth Service updates last_login in the same transaction that issues tokens.
        return None
