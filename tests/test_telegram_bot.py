import asyncio

import pytest
from telegram.error import Conflict

from app.state import AppState
from app.telegram_bot import BotController, BotRuntime, polling_error_callback


class DummyMessage:
    text = ""

    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class DummyChat:
    id = 123


class DummyUpdate:
    def __init__(self) -> None:
        self.effective_chat = DummyChat()
        self.effective_message = DummyMessage()


@pytest.mark.asyncio
async def test_notify_uses_state_toggle() -> None:
    state = AppState()
    controller = BotController(state, "123")
    update = DummyUpdate()

    await controller.notify(update, None)

    assert state.snapshot()["notify_enabled"] is True
    assert update.effective_message.replies == ["即時通知已開啟。"]


@pytest.mark.asyncio
async def test_manual_backup_url_does_not_override_existing_state(monkeypatch) -> None:
    state = AppState(backup_url="sqlite:///automatic.db")
    controller = BotController(state, "123")
    update = DummyUpdate()

    class DummyStore:
        def __init__(self, database_url: str) -> None:
            self.database_url = database_url

        def create_backup(self, payload) -> int:
            assert "backup_url" not in payload
            return 1

    monkeypatch.setattr("app.telegram_bot.BackupStore", DummyStore)

    await controller._create_backup(update, "sqlite:///manual.db")

    assert state.get_backup_url() == "sqlite:///automatic.db"
    assert update.effective_message.replies == ["備份完成，備份編號：1"]


@pytest.mark.asyncio
async def test_restore_uses_pending_database_url(monkeypatch) -> None:
    state = AppState()
    controller = BotController(state, "123")
    update = DummyUpdate()
    used_database_urls = []

    class DummyStore:
        def __init__(self, database_url: str) -> None:
            used_database_urls.append(database_url)

        def get_backup(self, backup_id: int):
            return {"urls": [{"url": "https://restored.example.com"}], "notify_enabled": True}

    monkeypatch.setattr("app.telegram_bot.BackupStore", DummyStore)

    await controller._handle_restore(
        update,
        "1",
        [{"id": "5", "created_at": "2026-05-12T00:00:00+00:00"}],
        database_url="sqlite:///manual.db",
    )

    assert used_database_urls == ["sqlite:///manual.db"]
    assert state.snapshot()["urls"][0]["url"] == "https://restored.example.com"
    assert update.effective_message.replies == ["已恢復備份。"]


@pytest.mark.asyncio
async def test_pending_action_expires() -> None:
    state = AppState()
    controller = BotController(state, "123", pending_ttl_seconds=0)
    update = DummyUpdate()
    update.effective_message.text = "https://example.com"

    controller._set_pending(update.effective_chat.id, {"action": "sub-url"})
    await asyncio.sleep(0)
    await controller.text_message(update, None)

    assert state.snapshot()["urls"] == []
    assert update.effective_message.replies == []
    assert controller.pending == {}


@pytest.mark.asyncio
async def test_set_pending_clears_expired_pending_actions() -> None:
    state = AppState()
    controller = BotController(state, "123", pending_ttl_seconds=0)

    controller._set_pending(1, {"action": "sub-url"})
    await asyncio.sleep(0)
    controller._set_pending(2, {"action": "sub-url"})

    assert set(controller.pending) == {2}


@pytest.mark.asyncio
async def test_restore_without_database_url_returns_clear_message(monkeypatch) -> None:
    state = AppState()
    controller = BotController(state, "123")
    update = DummyUpdate()

    def fail_if_used(database_url: str):
        raise AssertionError("BackupStore should not be created without a database URL")

    monkeypatch.setattr("app.telegram_bot.BackupStore", fail_if_used)

    await controller._handle_restore(update, "1", [{"id": "5", "created_at": "2026-05-12T00:00:00+00:00"}])

    assert update.effective_message.replies == ["沒有設定資料庫。"]


@pytest.mark.asyncio
async def test_del_url_lists_masked_urls_and_deletes_pending_url() -> None:
    state = AppState()
    secret_url = "https://secret.example.com/private/path?token=abc"
    state.add_url(secret_url)
    state.add_url("https://other.example.com")
    controller = BotController(state, "123")
    update = DummyUpdate()

    await controller.del_url(update, None)

    listed_text = update.effective_message.replies[-1]
    assert secret_url not in listed_text
    assert "token=abc" not in listed_text
    assert "••••" in listed_text

    state.delete_url_by_value("https://other.example.com")
    update.effective_message.text = "1"
    await controller.text_message(update, None)

    snapshot = state.snapshot()
    assert snapshot["urls"] == []
    assert secret_url not in update.effective_message.replies[-1]


@pytest.mark.asyncio
async def test_del_url_does_not_delete_wrong_url_after_list_changes() -> None:
    state = AppState()
    state.add_url("https://first.example.com")
    state.add_url("https://second.example.com")
    controller = BotController(state, "123")
    update = DummyUpdate()

    await controller.del_url(update, None)
    state.delete_url_by_value("https://first.example.com")
    update.effective_message.text = "1"
    await controller.text_message(update, None)

    snapshot = state.snapshot()
    assert [item["url"] for item in snapshot["urls"]] == ["https://second.example.com"]
    assert update.effective_message.replies[-1] == "找不到這個網址，清單可能已變更。"


@pytest.mark.asyncio
async def test_polling_conflict_callback_schedules_recovery_once() -> None:
    runtime = DummyRuntime()

    polling_error_callback(runtime)(Conflict("terminated by other getUpdates request"))
    polling_error_callback(runtime)(Conflict("terminated by other getUpdates request"))

    assert runtime.recovery_scheduled_count == 1


@pytest.mark.asyncio
async def test_bot_runtime_shutdown_stops_application() -> None:
    application = DummyApplication()
    runtime = BotRuntime(application)

    await runtime.shutdown()

    assert application.updater.stopped is True
    assert application.stopped is True
    assert application.shutdown_called is True


@pytest.mark.asyncio
async def test_bot_runtime_shutdown_cancels_conflict_retry() -> None:
    application = DummyApplication()
    runtime = BotRuntime(application, conflict_retry_seconds=60)
    runtime._conflict_retry_task = asyncio.create_task(asyncio.sleep(60))

    await runtime.shutdown()

    assert runtime._conflict_retry_task.cancelled() is True


class DummyRuntime:
    def __init__(self) -> None:
        self.recovery_scheduled_count = 0

    def schedule_conflict_recovery(self) -> None:
        if self.recovery_scheduled_count:
            return
        self.recovery_scheduled_count += 1


class DummyUpdater:
    running = True

    def __init__(self) -> None:
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True
        self.running = False


class DummyApplication:
    running = True

    def __init__(self) -> None:
        self.updater = DummyUpdater()
        self.stopped = False
        self.shutdown_called = False

    async def stop(self) -> None:
        self.stopped = True
        self.running = False

    async def shutdown(self) -> None:
        self.shutdown_called = True
