from fastapi.testclient import TestClient

from app.main import app


def test_s12ryt_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/s12ryt")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_index_page() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "docker-keep-alive" in response.text


def test_healthz_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
