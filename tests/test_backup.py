from app.backup import BackupStore, normalize_database_url


def test_normalize_database_url() -> None:
    assert normalize_database_url("postgres://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("postgresql://u:p@host/db") == "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url("mysql://u:p@host/db") == "mysql+pymysql://u:p@host/db"


def test_sqlite_backup_roundtrip(tmp_path) -> None:
    store = BackupStore(f"sqlite:///{tmp_path / 'backup.db'}")
    backup_id = store.create_backup({"urls": [{"url": "https://example.com"}], "notify_enabled": False})
    assert store.list_backups()[0]["id"] == backup_id
    assert store.get_backup(backup_id)["urls"][0]["url"] == "https://example.com"
