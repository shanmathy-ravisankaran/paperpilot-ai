from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_expected_payload() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "paperpilot-api"
    assert data["version"] == "0.1.0"
    assert data["timestamp"]


def test_openapi_is_available() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/health" in response.json()["paths"]


def test_health_cors_for_local_frontend() -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
