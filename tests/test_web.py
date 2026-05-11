from fastapi.testclient import TestClient

from app.main import app
from app.telegram_bot import hyphen_command_handlers


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


def test_hyphen_commands_can_be_registered() -> None:
    handlers = hyphen_command_handlers()
    assert len(handlers) == 2
