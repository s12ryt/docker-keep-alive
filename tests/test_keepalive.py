import asyncio

import httpx
import pytest

from app.keepalive import keepalive_loop, ping_once
from app.state import AppState


@pytest.mark.asyncio
async def test_ping_once_updates_state_and_runs_concurrently(monkeypatch) -> None:
    state = AppState()
    state.add_url("https://one.example.com")
    state.add_url("https://two.example.com")
    started = 0
    release = asyncio.Event()

    async def fake_get(self, url: str):
        nonlocal started
        started += 1
        if started == 2:
            release.set()
        await asyncio.wait_for(release.wait(), timeout=1)
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    messages = await ping_once(state)

    snapshot = state.snapshot()
    assert len(messages) == 2
    assert all(item["last_status"] == "成功" for item in snapshot["urls"])
    assert all(item["last_code"] == 200 for item in snapshot["urls"])


@pytest.mark.asyncio
async def test_ping_once_updates_matching_url_when_list_changes(monkeypatch) -> None:
    state = AppState()
    state.add_url("https://one.example.com")
    state.add_url("https://two.example.com")
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def fake_get(self, url: str):
        if url == "https://one.example.com":
            first_started.set()
            await asyncio.wait_for(release_first.wait(), timeout=1)
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    task = asyncio.create_task(ping_once(state))
    await asyncio.wait_for(first_started.wait(), timeout=1)
    state.delete_url_by_value("https://one.example.com")
    release_first.set()

    messages = await task

    snapshot = state.snapshot()
    assert [item["url"] for item in snapshot["urls"]] == ["https://two.example.com"]
    assert snapshot["urls"][0]["last_status"] == "成功"
    assert messages == ["https://two.example.com：成功 HTTP 200"]


@pytest.mark.asyncio
async def test_keepalive_loop_waits_before_first_ping(monkeypatch) -> None:
    state = AppState()
    calls = 0

    async def fake_ping_once(_state):
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr("app.keepalive.ping_once", fake_ping_once)
    task = asyncio.create_task(keepalive_loop(state, 60, lambda text: None))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == 0


@pytest.mark.asyncio
async def test_keepalive_loop_allows_zero_initial_delay(monkeypatch) -> None:
    state = AppState()
    state.notify_enabled = True
    called = asyncio.Event()
    notifications: list[str] = []

    async def fake_ping_once(_state):
        called.set()
        return ["done"]

    async def notify(text: str) -> None:
        notifications.append(text)

    monkeypatch.setattr("app.keepalive.ping_once", fake_ping_once)
    task = asyncio.create_task(keepalive_loop(state, 60, notify, initial_delay_seconds=0))
    await asyncio.wait_for(called.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert notifications == ["保活完成：\ndone"]
