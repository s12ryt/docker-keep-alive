from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .config import Settings
from .keepalive import backup_loop, keepalive_loop
from .state import AppState
from .telegram_bot import run_bot


settings = Settings.from_env()
state = AppState(backup_url=settings.backup_url)
background_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async def noop_notify(text: str) -> None:
        return None

    notify = noop_notify
    if settings.bot_token and settings.chat_id and not os.getenv("DISABLE_TELEGRAM"):
        notify = await run_bot(state, settings.bot_token, settings.chat_id)
    background_tasks.append(asyncio.create_task(keepalive_loop(state, settings.keepalive_interval_seconds, notify)))
    background_tasks.append(asyncio.create_task(backup_loop(state, settings.backup_interval_seconds)))
    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            with suppress(asyncio.CancelledError):
                await task
        background_tasks.clear()


app = FastAPI(title="docker-keep-alive", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    snapshot = state.snapshot()
    rows = "".join(
        f"<tr><td>{idx}</td><td>{item['url']}</td><td>{item['last_status']}</td><td>{item['last_code'] or ''}</td><td>{item['last_checked_at'] or '尚未執行'}</td><td>{item['last_error'] or ''}</td></tr>"
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
      <p>服務已啟動：{snapshot['started_at']}｜通知：{notify}｜第三方保活端點：<code>/s12ryt</code></p>
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
