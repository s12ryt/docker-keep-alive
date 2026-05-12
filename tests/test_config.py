from app.config import normalize_keepalive_path


def test_normalize_keepalive_path_adds_leading_slash() -> None:
    assert normalize_keepalive_path("ping") == "/ping"
    assert normalize_keepalive_path("/custom/") == "/custom"
    assert normalize_keepalive_path("") == "/s12ryt"
