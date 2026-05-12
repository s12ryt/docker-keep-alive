from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, os.getenv(name.upper(), default)).strip()


def _env_int(name: str, default: str) -> int:
    value = _env(name, default)
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"環境變數 {name} 必須是整數，目前值為 {value!r}") from exc


def normalize_keepalive_path(value: str) -> str:
    path = (value or "/s12ryt").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or "/"


@dataclass(frozen=True)
class Settings:
    bot_token: str
    chat_id: str
    backup_url: str | None
    port: int
    keepalive_interval_seconds: int
    backup_interval_seconds: int = 600
    telegram_conflict_retry_seconds: int = 60
    keepalive_path: str = "/s12ryt"

    @classmethod
    def from_env(cls) -> "Settings":
        backup = _env("backup") or None
        bot_token = _env("bot_id")
        chat_id = _env("chat_id")
        if not bot_token:
            raise RuntimeError("缺少必要環境變數 bot_id")
        if not chat_id:
            raise RuntimeError("缺少必要環境變數 chat_id")
        return cls(
            bot_token=bot_token,
            chat_id=chat_id,
            backup_url=backup,
            port=_env_int("PORT", "8080"),
            keepalive_interval_seconds=_env_int("KEEPALIVE_INTERVAL_SECONDS", "300"),
            backup_interval_seconds=_env_int("BACKUP_INTERVAL_SECONDS", "600"),
            telegram_conflict_retry_seconds=_env_int("TELEGRAM_CONFLICT_RETRY_SECONDS", "60"),
            keepalive_path=normalize_keepalive_path(_env("KEEPALIVE_PATH", "/s12ryt")),
        )
