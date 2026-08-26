from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, List
import uuid
import datetime

from shared.database import get_db_connection, get_db_transaction
from shared.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    require_role
)

app = FastAPI(title="Authentication Service")

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: int
    username: str
    ho_ten: str
    role: str
    is_active: bool

class UserCreateRequest(BaseModel):
    username: str
    password: str
    ho_ten: str
    role: str = "staff"

class UserUpdateRequest(BaseModel):
    ho_ten: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, username, password_hash, ho_ten, role, is_active FROM tai_khoan WHERE username = %s", (req.username,))
            user = await cur.fetchone()
            
    if not user or not verify_password(req.password, user[2]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    if not user[5]: # is_active
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Generate tokens
    access_token = create_access_token({"sub": user[1], "id": user[0], "role": user[4]})
    raw_refresh = str(uuid.uuid4())
    refresh_token = f"{user[0]}:{raw_refresh}"
    refresh_hash = get_password_hash(raw_refresh)
    
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    
    async with get_db_transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO refresh_tokens (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                (refresh_hash, user[0], expires_at)
            )
            await cur.execute(
                "UPDATE tai_khoan SET last_login = NOW() WHERE id = %s", (user[0],)
            )
            
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

@app.post("/api/v1/auth/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest):
    try:
        user_id_str, raw_token = req.refresh_token.split(":", 1)
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token format")

    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT token_hash, revoked, expires_at FROM refresh_tokens WHERE user_id = %s AND revoked = 0 AND expires_at > NOW()",
                (user_id,)
            )
            rows = await cur.fetchall()
            
    valid_hash = None
    for row in rows:
        if verify_password(raw_token, row[0]):
            valid_hash = row[0]
            break
            
    if not valid_hash:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        
    # Get user info
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, username, role, is_active FROM tai_khoan WHERE id = %s", (user_id,))
            user = await cur.fetchone()
            
    if not user or not user[3]:
        raise HTTPException(status_code=403, detail="Account is disabled")
        
    access_token = create_access_token({"sub": user[1], "id": user[0], "role": user[2]})
    raw_new_refresh = str(uuid.uuid4())
    new_refresh_token = f"{user[0]}:{raw_new_refresh}"
    new_refresh_hash = get_password_hash(raw_new_refresh)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    
    async with get_db_transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = %s", (valid_hash,))
            await cur.execute(
                "INSERT INTO refresh_tokens (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                (new_refresh_hash, user[0], expires_at)
            )
            
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)

@app.post("/api/v1/auth/logout")
async def logout(req: RefreshRequest, current_user: dict = Depends(get_current_user)):
    try:
        user_id_str, raw_token = req.refresh_token.split(":", 1)
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token format")
        
    if user_id != current_user.get("id"):
        raise HTTPException(status_code=403, detail="Cannot revoke token of another user")

    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT token_hash FROM refresh_tokens WHERE user_id = %s AND revoked = 0",
                (user_id,)
            )
            rows = await cur.fetchall()
            
    valid_hash = None
    for row in rows:
        if verify_password(raw_token, row[0]):
            valid_hash = row[0]
            break
            
    if valid_hash:
        async with get_db_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = %s", (valid_hash,))
                
    return {"message": "Logged out successfully"}

@app.get("/api/v1/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, username, ho_ten, role, is_active FROM tai_khoan WHERE id = %s", (current_user.get("id"),))
            user = await cur.fetchone()
            
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return UserResponse(id=user[0], username=user[1], ho_ten=user[2], role=user[3], is_active=bool(user[4]))

@app.get("/api/v1/users", response_model=List[UserResponse])
async def get_users(current_user: dict = Depends(require_role("admin"))):
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, username, ho_ten, role, is_active FROM tai_khoan")
            users = await cur.fetchall()
            
    return [UserResponse(id=u[0], username=u[1], ho_ten=u[2], role=u[3], is_active=bool(u[4])) for u in users]

@app.post("/api/v1/users", response_model=UserResponse)
async def create_user(req: UserCreateRequest, current_user: dict = Depends(require_role("admin"))):
    hashed_pwd = get_password_hash(req.password)
    async with get_db_transaction() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "INSERT INTO tai_khoan (username, password_hash, ho_ten, role, is_active) VALUES (%s, %s, %s, %s, 1)",
                    (req.username, hashed_pwd, req.ho_ten, req.role)
                )
                new_id = cur.lastrowid
            except Exception as e:
                raise HTTPException(status_code=400, detail="Username might already exist")
                
    return UserResponse(id=new_id, username=req.username, ho_ten=req.ho_ten, role=req.role, is_active=True)

@app.patch("/api/v1/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, req: UserUpdateRequest, current_user: dict = Depends(require_role("admin"))):
    async with get_db_transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, username, ho_ten, role, is_active FROM tai_khoan WHERE id = %s", (user_id,))
            user = await cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
                
            ho_ten = req.ho_ten if req.ho_ten is not None else user[2]
            role = req.role if req.role is not None else user[3]
            is_active = req.is_active if req.is_active is not None else user[4]
            
            await cur.execute(
                "UPDATE tai_khoan SET ho_ten = %s, role = %s, is_active = %s WHERE id = %s",
                (ho_ten, role, is_active, user_id)
            )
            
    return UserResponse(id=user[0], username=user[1], ho_ten=ho_ten, role=role, is_active=bool(is_active))

@app.patch("/api/v1/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(user_id: int, is_active: bool, current_user: dict = Depends(require_role("admin"))):
    req = UserUpdateRequest(is_active=is_active)
    return await update_user(user_id, req, current_user)

@app.patch("/api/v1/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(user_id: int, role: str, current_user: dict = Depends(require_role("admin"))):
    req = UserUpdateRequest(role=role)
    return await update_user(user_id, req, current_user)

