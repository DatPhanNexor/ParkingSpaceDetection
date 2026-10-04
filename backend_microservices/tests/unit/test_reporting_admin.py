import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from services.reporting_service.main import app
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

@patch('services.reporting_service.main.get_db_connection')
def test_delete_history_session_admin(mock_db_connection, override_require_role):
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    mock_db_connection.return_value.__aenter__.return_value = mock_conn
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_cur.fetchone.return_value = {"transaction_id": "tx1"}
    
    response = client.delete("/api/v1/sessions/history/tx1")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_cur.execute.assert_any_call("DELETE FROM lich_su_xe WHERE transaction_id = %s", ("tx1",))

@patch('services.reporting_service.main.get_db_connection')
def test_batch_delete_history_admin(mock_db_connection, override_require_role):
    mock_conn = AsyncMock()
    mock_cur = AsyncMock()
    mock_db_connection.return_value.__aenter__.return_value = mock_conn
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur
    mock_cur.rowcount = 2
    
    response = client.request("DELETE", "/api/v1/sessions/history", json={"transaction_ids": ["tx1", "tx2"]})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_cur.execute.assert_called_with("DELETE FROM lich_su_xe WHERE transaction_id IN (%s,%s)", ("tx1", "tx2"))

def test_delete_history_forbidden(override_require_role_forbidden):
    response = client.delete("/api/v1/sessions/history/tx1")
    assert response.status_code == 403
    
    response2 = client.request("DELETE", "/api/v1/sessions/history", json={"transaction_ids": ["tx1"]})
    assert response2.status_code == 403
