import os

import pytest

from app.timezone import configured_timezone


os.environ.setdefault("bot_id", "test-token")
os.environ.setdefault("chat_id", "123")
os.environ.setdefault("DISABLE_TELEGRAM", "1")


@pytest.fixture(autouse=True)
def clear_configured_timezone_cache():
    configured_timezone.cache_clear()
    yield
    configured_timezone.cache_clear()
