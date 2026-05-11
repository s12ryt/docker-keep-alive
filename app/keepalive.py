from __future__ import annotations

import asyncio

import httpx

from .backup import BackupStore
from .state import AppState, utc_now


async def ping_once(state: AppState) -> list[str]:
    messages: list[str] = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        for target in state.urls:
            try:
                response = await client.get(target.url)
                target.last_code = response.status_code
                target.last_error = None
                target.last_status = "成功" if response.status_code < 400 else "失敗"
                target.last_checked_at = utc_now()
            except Exception as exc:  # noqa: BLE001 - 需要把外部網站錯誤記入狀態
                target.last_code = None
                target.last_status = "失敗"
                target.last_error = str(exc)
                target.last_checked_at = utc_now()
            messages.append(f"{target.url}：{target.last_status}" + (f" HTTP {target.last_code}" if target.last_code else ""))
    return messages


async def keepalive_loop(state: AppState, interval_seconds: int, notify) -> None:
    while True:
        messages = await ping_once(state)
        if state.notify_enabled and messages:
            await notify("保活完成：\n" + "\n".join(messages))
        await asyncio.sleep(interval_seconds)


async def backup_loop(state: AppState, interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        if not state.backup_url:
            continue
        try:
            BackupStore(state.backup_url).create_backup(state.snapshot(), keep_only_latest=True)
        except Exception:
            # 備份失敗不能讓主服務退出；使用者仍可透過 /state 查看服務狀態。
            continue
