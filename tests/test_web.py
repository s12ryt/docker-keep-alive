from fastapi.testclient import TestClient

from app.main import app
from app.telegram_bot import COMMAND_LIST_TEXT, bot_menu_commands, hyphen_command_handlers


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


def test_command_list_mentions_all_user_commands() -> None:
    for command in [
        "/start",
        "/help",
        "/commands",
        "/state",
        "/sub-url",
        "/sub_url",
        "/del-url",
        "/del_url",
        "/notify",
        "/backup",
        "/rebackup",
    ]:
        assert command in COMMAND_LIST_TEXT


def test_bot_menu_commands_are_valid_for_set_my_commands() -> None:
    commands = bot_menu_commands()
    command_names = [item.command for item in commands]
    assert command_names == ["start", "help", "commands", "state", "sub_url", "del_url", "notify", "backup", "rebackup"]
    assert all("-" not in item.command for item in commands)
    assert all(item.description for item in commands)
