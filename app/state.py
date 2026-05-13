from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any
from urllib.parse import urlsplit

from .timezone import now_iso


def utc_now() -> str:
    return now_iso()


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


@dataclass
class TargetUrl:
    url: str
    last_status: str = "尚未保活"
    last_code: int | None = None
    last_error: str | None = None
    last_checked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "last_status": self.last_status,
            "last_code": self.last_code,
            "last_error": self.last_error,
            "last_checked_at": self.last_checked_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetUrl":
        return cls(
            url=str(data["url"]),
            last_status=str(data.get("last_status", "尚未保活")),
            last_code=data.get("last_code"),
            last_error=data.get("last_error"),
            last_checked_at=data.get("last_checked_at"),
        )


@dataclass
class AppState:
    urls: list[TargetUrl] = field(default_factory=list)
    notify_enabled: bool = False
    started_at: str = field(default_factory=utc_now)
    backup_url: str | None = None
    _lock: RLock = field(default_factory=RLock, repr=False)

    def list_urls(self) -> list[str]:
        with self._lock:
            return [item.url for item in self.urls]

    def add_url(self, url: str) -> bool:
        normalized = url.strip()
        with self._lock:
            if any(item.url == normalized for item in self.urls):
                return False
            self.urls.append(TargetUrl(url=normalized))
            return True

    def delete_url(self, index: int) -> TargetUrl | None:
        with self._lock:
            if index < 0 or index >= len(self.urls):
                return None
            return self.urls.pop(index)

    def delete_url_by_value(self, url: str) -> TargetUrl | None:
        with self._lock:
            for index, item in enumerate(self.urls):
                if item.url == url:
                    return self.urls.pop(index)
            return None

    def update_url_status(
        self,
        url: str,
        *,
        last_status: str,
        last_code: int | None,
        last_error: str | None,
        last_checked_at: str,
    ) -> str | None:
        with self._lock:
            target = next((item for item in self.urls if item.url == url), None)
            if target is None:
                return None
            target.last_status = last_status
            target.last_code = last_code
            target.last_error = last_error
            target.last_checked_at = last_checked_at
            return target.url

    def toggle_notify(self) -> bool:
        with self._lock:
            self.notify_enabled = not self.notify_enabled
            return self.notify_enabled

    def get_backup_url(self) -> str | None:
        with self._lock:
            return self.backup_url

    def set_backup_url(self, database_url: str | None) -> None:
        with self._lock:
            self.backup_url = database_url

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "started_at": self.started_at,
                "notify_enabled": self.notify_enabled,
                "backup_url": self.backup_url,
                "urls": [item.to_dict() for item in self.urls],
            }

    def public_snapshot(self) -> dict[str, Any]:
        data = self.snapshot()
        data.pop("backup_url", None)
        return data

    def backup_snapshot(self) -> dict[str, Any]:
        return self.public_snapshot()

    def restore(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.notify_enabled = bool(data.get("notify_enabled", False))
            if self.backup_url is None:
                backup_url = data.get("backup_url")
                self.backup_url = backup_url if isinstance(backup_url, str) else None
            self.urls = [TargetUrl.from_dict(item) for item in data.get("urls", [])]

    def state_text(self) -> str:
        data = self.snapshot()
        lines = ["目前狀態：", f"通知：{'開啟' if data['notify_enabled'] else '關閉'}"]
        if not data["urls"]:
            lines.append("尚未新增保活網址。")
            return "\n".join(lines)
        for idx, item in enumerate(data["urls"], start=1):
            status = item["last_status"]
            code = f" HTTP {item['last_code']}" if item["last_code"] else ""
            checked = item["last_checked_at"] or "尚未執行"
            err = f"，錯誤：{item['last_error']}" if item["last_error"] else ""
            lines.append(f"{idx}. {mask_url_for_display(item['url'])}｜{status}{code}｜{checked}{err}")
        return "\n".join(lines)
