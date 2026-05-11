from app.state import AppState


def test_add_and_delete_url() -> None:
    state = AppState()
    assert state.add_url("https://example.com") is True
    assert state.add_url("https://example.com") is False
    assert len(state.snapshot()["urls"]) == 1
    deleted = state.delete_url(0)
    assert deleted is not None
    assert deleted.url == "https://example.com"
    assert state.delete_url(0) is None


def test_restore_snapshot() -> None:
    state = AppState()
    state.restore({"notify_enabled": True, "urls": [{"url": "https://example.com", "last_status": "成功"}]})
    snapshot = state.snapshot()
    assert snapshot["notify_enabled"] is True
    assert snapshot["urls"][0]["url"] == "https://example.com"
    assert snapshot["urls"][0]["last_status"] == "成功"
