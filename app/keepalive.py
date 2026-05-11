from __future__ import annotations

import asyncio

import httpx

from .backup import BackupStore
from .state import AppState, utc_now


async def ping_once(state: AppState) -> list[str]:
    targets = state.list_urls()
    if not targets:
        return []

    async def ping_target(client: httpx.AsyncClient, index: int, url: str) -> str | None:
        checked_at = utc_now()
        last_code: int | None = None
        last_error: str | None = None
        try:
            response = await client.get(url)
            last_code = response.status_code
            last_status = "成功" if response.status_code < 400 else "失敗"
        except Exception as exc:  # noqa: BLE001 - 需要把外部網站錯誤記入狀態
            last_status = "失敗"
            last_error = str(exc)
        current_url = state.update_url_status(
            index,
            last_status=last_status,
            last_code=last_code,
            last_error=last_error,
            last_checked_at=checked_at,
        )
        if current_url is None:
            return None
        return f"{current_url}：{last_status}" + (f" HTTP {last_code}" if last_code else "")

    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        messages = await asyncio.gather(*(ping_target(client, index, url) for index, url in targets))
    return [message for message in messages if message]


async def keepalive_loop(state: AppState, interval_seconds: int, notify) -> None:
    while True:
        messages = await ping_once(state)
        if state.snapshot()["notify_enabled"] and messages:
            await notify("保活完成：\n" + "\n".join(messages))
        await asyncio.sleep(interval_seconds)


async def backup_loop(state: AppState, interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        backup_url = state.get_backup_url()
        if not backup_url:
            continue
        try:
            BackupStore(backup_url).create_backup(state.snapshot(), keep_only_latest=True)
        except Exception:
            # 備份失敗不能讓主服務退出；使用者仍可透過 /state 查看服務狀態。
            continue
