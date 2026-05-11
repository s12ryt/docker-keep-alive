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
            return 1

    monkeypatch.setattr("app.telegram_bot.BackupStore", DummyStore)

    await controller._create_backup(update, "sqlite:///manual.db")

    assert state.get_backup_url() == "sqlite:///automatic.db"
    assert update.effective_message.replies == ["備份完成，備份編號：1"]


@pytest.mark.asyncio
async def test_polling_conflict_callback_schedules_recovery_once(monkeypatch) -> None:
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
