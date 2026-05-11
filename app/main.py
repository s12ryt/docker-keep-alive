from __future__ import annotations

import asyncio
import html
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .backup import BackupStore
from .config import Settings
from .keepalive import backup_loop, keepalive_loop
from .state import AppState
from .telegram_bot import BotRuntime, run_bot


settings = Settings.from_env()
state = AppState(backup_url=settings.backup_url)


def restore_latest_backup() -> None:
    backup_url = state.get_backup_url()
    if not backup_url:
        return
    try:
        latest = BackupStore(backup_url).get_latest_backup()
    except Exception:
        # 資料庫短暫不可用時仍應啟動 web 與 Telegram 控制面板。
        return
    if latest:
        state.restore(latest)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async def noop_notify(text: str) -> None:
        return None

    restore_latest_backup()

    notify = noop_notify
    tasks: list[asyncio.Task] = []
    bot_runtime: BotRuntime | None = None
    if settings.bot_token and settings.chat_id and not os.getenv("DISABLE_TELEGRAM"):
        bot_runtime = await run_bot(
            state,
            settings.bot_token,
            settings.chat_id,
            conflict_retry_seconds=settings.telegram_conflict_retry_seconds,
        )

        async def telegram_notify(text: str) -> None:
            await bot_runtime.notify(text, settings.chat_id)

        notify = telegram_notify
    tasks.append(asyncio.create_task(keepalive_loop(state, settings.keepalive_interval_seconds, notify)))
    tasks.append(asyncio.create_task(backup_loop(state, settings.backup_interval_seconds)))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        if bot_runtime:
            await bot_runtime.shutdown()


app = FastAPI(title="docker-keep-alive", lifespan=lifespan)


def _mask_text(value: str, visible_prefix: int = 4, visible_suffix: int = 3) -> str:
    if not value:
        return ""
    if len(value) <= visible_prefix + visible_suffix:
        return "•" * len(value)
    return f"{value[:visible_prefix]}••••{value[-visible_suffix:]}"


def mask_url_for_display(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return _mask_text(url)

    if not parsed.scheme or not parsed.netloc:
        return _mask_text(url)

    hostname = parsed.hostname or parsed.netloc
    masked_host = _mask_text(hostname, visible_prefix=3, visible_suffix=3)
    port = f":{parsed.port}" if parsed.port else ""
    suffix = "/•••" if parsed.path or parsed.query or parsed.fragment else ""
    return f"{parsed.scheme}://{masked_host}{port}{suffix}"


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    snapshot = state.snapshot()
    rows = "".join(
        "<tr>"
        f"<td>{idx}</td>"
        f"<td>{html.escape(mask_url_for_display(item['url']))}</td>"
        f"<td>{html.escape(str(item['last_status']))}</td>"
        f"<td>{html.escape(str(item['last_code'] or ''))}</td>"
        f"<td>{html.escape(str(item['last_checked_at'] or '尚未執行'))}</td>"
        f"<td>{html.escape(str(item['last_error'] or ''))}</td>"
        "</tr>"
        for idx, item in enumerate(snapshot["urls"], start=1)
    )
    if not rows:
        rows = "<tr><td colspan='6'>尚未新增保活網址</td></tr>"
    notify = "開啟" if snapshot["notify_enabled"] else "關閉"
    return f"""
    <!doctype html>
    <html lang="zh-Hant">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>docker-keep-alive</title>
      <style>
        body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f7f7fb; color: #1f2937; }}
        main {{ max-width: 960px; margin: auto; background: white; border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px #0001; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; word-break: break-all; }}
        code {{ background: #eef2ff; padding: 2px 6px; border-radius: 6px; }}
      </style>
    </head>
    <body><main>
      <h1>docker-keep-alive</h1>
      <p>服務已啟動：{html.escape(str(snapshot['started_at']))}｜通知：{notify}</p>
      <table><thead><tr><th>#</th><th>網址</th><th>狀態</th><th>HTTP</th><th>最後檢查</th><th>錯誤</th></tr></thead><tbody>{rows}</tbody></table>
    </main></body></html>
    """


@app.get("/s12ryt")
async def keepalive_endpoint() -> dict[str, str]:
    return {"status": "ok", "message": "ciallo~"}


@app.get("/api/state")
async def api_state() -> dict:
    return state.snapshot()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port)
