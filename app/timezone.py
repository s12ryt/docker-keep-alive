from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone


_OFFSET_RE = re.compile(r"^([+-])(\d{2})(\d{2})$")


def timezone_from_offset(value: str | None) -> timezone | None:
    if not value:
        return None
    match = _OFFSET_RE.fullmatch(value.strip())
    if not match:
        return None
    sign_text, hours_text, minutes_text = match.groups()
    hours = int(hours_text)
    minutes = int(minutes_text)
    if hours > 23 or minutes > 59:
        return None
    sign = 1 if sign_text == "+" else -1
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def configured_timezone() -> timezone:
    return timezone_from_offset(os.getenv("TZ")) or timezone.utc


def now_iso() -> str:
    return datetime.now(configured_timezone()).isoformat(timespec="seconds")


def format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(configured_timezone()).isoformat(timespec="seconds")
