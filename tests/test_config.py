import pytest

from app.config import _env_int, normalize_keepalive_path


def test_env_int_raises_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "abc")

    with pytest.raises(RuntimeError, match="環境變數 PORT 必須是整數"):
        _env_int("PORT", "8080")


def test_normalize_keepalive_path_adds_leading_slash() -> None:
    assert normalize_keepalive_path("ping") == "/ping"
    assert normalize_keepalive_path("/custom/") == "/custom"
    assert normalize_keepalive_path("") == "/s12ryt"
