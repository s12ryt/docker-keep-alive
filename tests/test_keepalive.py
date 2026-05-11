import asyncio

import httpx
import pytest

from app.keepalive import ping_once
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
