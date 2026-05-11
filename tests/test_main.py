from app.main import restore_latest_backup, state
from app.backup import BackupStore


def test_restore_latest_backup_loads_database_snapshot(tmp_path) -> None:
    original_backup_url = state.get_backup_url()
    original_snapshot = state.snapshot()
    database_url = f"sqlite:///{tmp_path / 'backup.db'}"
    try:
        state.set_backup_url(database_url)
        state.restore({"urls": [], "notify_enabled": False, "backup_url": database_url})
        BackupStore(database_url).create_backup(
            {
                "urls": [{"url": "https://restored.example.com"}],
                "notify_enabled": True,
                "backup_url": database_url,
            }
        )

        restore_latest_backup()

        snapshot = state.snapshot()
        assert snapshot["urls"][0]["url"] == "https://restored.example.com"
        assert snapshot["notify_enabled"] is True
    finally:
        state.restore(original_snapshot)
        state.set_backup_url(original_backup_url)
