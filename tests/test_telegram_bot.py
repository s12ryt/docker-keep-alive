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
            return 1

    monkeypatch.setattr("app.telegram_bot.BackupStore", DummyStore)

    await controller._create_backup(update, "sqlite:///manual.db")

    assert state.get_backup_url() == "sqlite:///automatic.db"
    assert update.effective_message.replies == ["備份完成，備份編號：1"]


@pytest.mark.asyncio
async def test_polling_conflict_callback_stops_polling(monkeypatch) -> None:
    runtime = DummyRuntime()
    scheduled = []

    def fake_create_task(coro):
        scheduled.append(coro)
        return None

    monkeypatch.setattr("app.telegram_bot.asyncio.create_task", fake_create_task)

    polling_error_callback(runtime)(Conflict("terminated by other getUpdates request"))

    assert len(scheduled) == 1
    await scheduled[0]
    assert runtime.stopped is True


@pytest.mark.asyncio
async def test_bot_runtime_shutdown_stops_application() -> None:
    application = DummyApplication()
    runtime = BotRuntime(application)

    await runtime.shutdown()

    assert application.updater.stopped is True
    assert application.stopped is True
    assert application.shutdown_called is True


class DummyRuntime:
    def __init__(self) -> None:
        self.stopped = False

    async def stop_polling(self) -> None:
        self.stopped = True


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
