from fastapi.testclient import TestClient

from app.main import app


def test_health_ready():
    """Test that the health/ready endpoint returns expected status."""
    client = TestClient(app)
    response = client.get("/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_health_ready_json_structure():
    """Test that response has correct structure."""
    client = TestClient(app)
    response = client.get("/v1/health/ready")

    data = response.json()
    assert "status" in data
    assert isinstance(data["status"], str)
