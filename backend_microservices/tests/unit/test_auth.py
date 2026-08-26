import pytest
import datetime
from shared.security import get_password_hash, verify_password, create_access_token, decode_access_token

def test_password_hashing():
    # Test PBKDF2 compatibility
    pwd = "mypassword123"
    hashed = get_password_hash(pwd)
    
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_jwt_expiry():
    # Test JWT token creation and decoding
    data = {"sub": "admin", "id": 1, "role": "admin"}
    token = create_access_token(data)
    
    decoded = decode_access_token(token)
    assert decoded["sub"] == "admin"
    assert decoded["id"] == 1
    assert decoded["role"] == "admin"
    assert "exp" in decoded

def test_rbac_dependency():
    from shared.security import require_role
    from fastapi import HTTPException
    
    dep = require_role("admin")
    
    # Should pass
    admin_user = {"id": 1, "role": "admin"}
    assert dep(admin_user) == admin_user
    
    # Should fail
    staff_user = {"id": 2, "role": "staff"}
    with pytest.raises(HTTPException) as excinfo:
        dep(staff_user)
    assert excinfo.value.status_code == 403
