import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from services.parking_billing_service.main import app
from shared.security import require_role

client = TestClient(app)

@pytest.fixture
def override_require_role():
    app.dependency_overrides[require_role("admin")] = lambda: {"id": 1, "username": "admin", "role": "admin"}
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def override_require_role_forbidden():
    from fastapi import HTTPException
    def raise_403():
        raise HTTPException(status_code=403, detail="Forbidden")
    app.dependency_overrides[require_role("admin")] = raise_403
    yield
    app.dependency_overrides.clear()

@patch('services.parking_billing_service.main.get_db_transaction')
def test_delete_one_active_session_admin(mock_db_transaction, override_require_role):
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    mock_db_transaction.return_value.__aenter__.return_value = mock_conn
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_cur.fetchone.return_value = {"slot_id": "S05"}
    
    response = client.delete("/api/v1/sessions/active/sess123")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_cur.execute.assert_any_call("DELETE FROM active_session_locks WHERE session_id = %s", ("sess123",))

@patch('services.parking_billing_service.main.get_db_transaction')
def test_delete_all_active_sessions_admin(mock_db_transaction, override_require_role):
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    mock_db_transaction.return_value.__aenter__.return_value = mock_conn
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    
    response = client.delete("/api/v1/sessions/active")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_cur.execute.assert_any_call("DELETE FROM active_session_locks")

def test_delete_active_sessions_non_admin_forbidden(override_require_role_forbidden):
    response = client.delete("/api/v1/sessions/active/sess123")
    assert response.status_code == 403
    
    response2 = client.delete("/api/v1/sessions/active")
    assert response2.status_code == 403

@patch('services.parking_billing_service.main.get_db_transaction')
def test_delete_idempotency_not_found(mock_db_transaction, override_require_role):
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    mock_db_transaction.return_value.__aenter__.return_value = mock_conn
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_cur.fetchone.return_value = None
    
    response = client.delete("/api/v1/sessions/active/sess999")
    assert response.status_code == 200
    assert response.json()["message"] == "Session not active"
