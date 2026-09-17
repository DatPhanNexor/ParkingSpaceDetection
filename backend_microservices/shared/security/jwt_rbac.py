import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
try:
    import jwt
    _JWT_BACKEND = "pyjwt"
except ImportError:  # pragma: no cover - exercised only in minimal local test envs
    from jose import jwt  # type: ignore[no-redef]
    from jose import exceptions as jose_exceptions

    _JWT_BACKEND = "jose"

try:
    from fastapi import HTTPException, Security, status
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
except ImportError:  # pragma: no cover - keeps pure unit tests importable without FastAPI
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    class status:
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403

    def Security(dependency):
        return dependency

    class HTTPBearer:
        pass

    class HTTPAuthorizationCredentials:
        credentials: str

from passlib.context import CryptContext

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is not set")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

pwd_context = CryptContext(schemes=["django_pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # PBKDF2-HMAC-SHA256 compatibility
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Fallback or strict legacy check if needed
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except _expired_token_error():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except _invalid_token_error():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def _expired_token_error():
    if _JWT_BACKEND == "pyjwt":
        return jwt.ExpiredSignatureError
    return jose_exceptions.ExpiredSignatureError


def _invalid_token_error():
    if _JWT_BACKEND == "pyjwt":
        return jwt.InvalidTokenError
    return jose_exceptions.JWTError

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    return decode_access_token(token)

def require_role(required_role: str):
    def role_checker(user: dict = Security(get_current_user)):
        if user.get("role") != required_role and user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return user
    return role_checker
