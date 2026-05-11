from datetime import datetime, timezone

from app.state import utc_now
from app.timezone import format_datetime, timezone_from_offset


def test_timezone_from_offset_accepts_plus_and_minus() -> None:
    assert timezone_from_offset("+0800").utcoffset(None).total_seconds() == 8 * 60 * 60
    assert timezone_from_offset("-0530").utcoffset(None).total_seconds() == -(5 * 60 + 30) * 60


def test_timezone_from_offset_rejects_invalid_values() -> None:
    assert timezone_from_offset("Asia/Taipei") is None
    assert timezone_from_offset("+2460") is None
    assert timezone_from_offset("") is None


def test_utc_now_uses_tz_offset(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "+0800")

    assert utc_now().endswith("+08:00")


def test_format_datetime_converts_to_configured_timezone(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "-0530")
    value = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)

    assert format_datetime(value) == "2026-05-12T02:30:00-05:30"
