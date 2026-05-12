from app.backup import BackupStore, clear_engine_cache, normalize_database_url


def test_normalize_database_url() -> None:
    assert normalize_database_url("postgres://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("postgresql://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("mysql://u:p@host/db") == "mysql+pymysql://u:p@host/db"


def test_sqlite_backup_roundtrip(tmp_path) -> None:
    store = BackupStore(f"sqlite:///{tmp_path / 'backup.db'}")
    backup_id = store.create_backup({"urls": [{"url": "https://example.com"}], "notify_enabled": False})
    assert store.list_backups()[0]["id"] == backup_id
    assert store.get_backup(backup_id)["urls"][0]["url"] == "https://example.com"


def test_get_latest_backup(tmp_path) -> None:
    store = BackupStore(f"sqlite:///{tmp_path / 'backup.db'}")
    store.create_backup({"urls": [{"url": "https://old.example.com"}], "notify_enabled": False})
    store.create_backup({"urls": [{"url": "https://new.example.com"}], "notify_enabled": True})

    latest = store.get_latest_backup()

    assert latest is not None
    assert latest["urls"][0]["url"] == "https://new.example.com"
    assert latest["notify_enabled"] is True


def test_create_backup_can_keep_only_latest(tmp_path) -> None:
    store = BackupStore(f"sqlite:///{tmp_path / 'backup.db'}")
    store.create_backup({"urls": [{"url": "https://old.example.com"}], "notify_enabled": False})
    latest_id = store.create_backup({"urls": [{"url": "https://new.example.com"}], "notify_enabled": True}, keep_only_latest=True)

    backups = store.list_backups()

    assert [item["id"] for item in backups] == [latest_id]
    assert store.get_latest_backup()["urls"][0]["url"] == "https://new.example.com"


def test_delete_backups_except(tmp_path) -> None:
    store = BackupStore(f"sqlite:///{tmp_path / 'backup.db'}")
    old_id = store.create_backup({"urls": [{"url": "https://old.example.com"}], "notify_enabled": False})
    keep_id = store.create_backup({"urls": [{"url": "https://keep.example.com"}], "notify_enabled": True})

    deleted_count = store.delete_backups_except(keep_id)

    assert deleted_count == 1
    assert store.get_backup(old_id) is None
    assert store.get_backup(keep_id)["urls"][0]["url"] == "https://keep.example.com"


def test_backup_store_reuses_engine_for_same_database_url(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'backup.db'}"
    first = BackupStore(database_url)
    second = BackupStore(database_url)

    assert first.engine is second.engine


def test_clear_engine_cache_discards_cached_engines(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'backup.db'}"
    first = BackupStore(database_url)

    clear_engine_cache()
    second = BackupStore(database_url)

    assert first.engine is not second.engine


def test_list_backups_uses_limit(tmp_path) -> None:
    store = BackupStore(f"sqlite:///{tmp_path / 'backup.db'}")
    for idx in range(3):
        store.create_backup({"urls": [{"url": f"https://{idx}.example.com"}], "notify_enabled": False})

    assert len(store.list_backups(limit=2)) == 2
