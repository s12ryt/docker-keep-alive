import pytest

from app.config import _env_int


def test_env_int_raises_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "abc")

    with pytest.raises(RuntimeError, match="環境變數 PORT 必須是整數"):
        _env_int("PORT", "8080")
