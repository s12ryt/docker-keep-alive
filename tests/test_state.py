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


def test_update_url_status_and_toggle_notify() -> None:
    state = AppState()
    state.add_url("https://example.com")

    updated_url = state.update_url_status(
        "https://example.com",
        last_status="成功",
        last_code=200,
        last_error=None,
        last_checked_at="2026-05-12T00:00:00+00:00",
    )
    notify_enabled = state.toggle_notify()

    snapshot = state.snapshot()
    assert updated_url == "https://example.com"
    assert snapshot["urls"][0]["last_status"] == "成功"
    assert snapshot["urls"][0]["last_code"] == 200
    assert notify_enabled is True
    assert state.update_url_status("https://missing.example.com", last_status="失敗", last_code=None, last_error="missing", last_checked_at="now") is None


def test_backup_url_accessors() -> None:
    state = AppState()
    state.set_backup_url("sqlite:///backup.db")
    assert state.get_backup_url() == "sqlite:///backup.db"


def test_public_snapshot_omits_backup_url() -> None:
    state = AppState(backup_url="postgres://user:secret@example.com/db")
    snapshot = state.public_snapshot()

    assert "backup_url" not in snapshot


def test_backup_snapshot_omits_backup_url() -> None:
    state = AppState(backup_url="postgres://user:secret@example.com/db")
    snapshot = state.backup_snapshot()

    assert "backup_url" not in snapshot
    assert "secret" not in str(snapshot)


def test_restore_keeps_existing_backup_url() -> None:
    state = AppState(backup_url="postgres://current:secret@example.com/db")

    state.restore({"backup_url": "postgres://old:leaked@example.com/db", "urls": [], "notify_enabled": False})

    assert state.get_backup_url() == "postgres://current:secret@example.com/db"


def test_restore_can_read_legacy_backup_url_when_current_is_missing() -> None:
    state = AppState()

    state.restore({"backup_url": "postgres://legacy:secret@example.com/db", "urls": [], "notify_enabled": False})

    assert state.get_backup_url() == "postgres://legacy:secret@example.com/db"


def test_state_text_masks_urls() -> None:
    state = AppState()
    secret_url = "https://secret.example.com/private/path?token=super-secret-token"
    state.add_url(secret_url)

    text = state.state_text()

    assert secret_url not in text
    assert "super-secret-token" not in text
    assert "private" not in text
    assert "••••" in text
