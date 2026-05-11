from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Integer, MetaData, Table, Text, create_engine, delete, insert, select
from sqlalchemy.engine import Engine

from .timezone import configured_timezone, format_datetime


metadata = MetaData()
_engine_cache: dict[str, Engine] = {}
backups = Table(
    "docker_keep_alive_backups",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", Text, nullable=False),
)


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("mysql://"):
        return "mysql+pymysql://" + url.removeprefix("mysql://")
    return url


class BackupStore:
    def __init__(self, database_url: str):
        self.database_url = normalize_database_url(database_url)
        self.engine = _engine_cache.get(self.database_url)
        if self.engine is None:
            self.engine = create_engine(self.database_url, pool_pre_ping=True)
            _engine_cache[self.database_url] = self.engine
        metadata.create_all(self.engine)

    def create_backup(self, payload: dict[str, Any], keep_only_latest: bool = False) -> int:
        created_at = datetime.now(configured_timezone())
        with self.engine.begin() as conn:
            result = conn.execute(insert(backups).values(created_at=created_at, payload=json.dumps(payload, ensure_ascii=False)))
            backup_id = int(result.inserted_primary_key[0])
            if keep_only_latest:
                conn.execute(delete(backups).where(backups.c.id != backup_id))
            return backup_id

    def list_backups(self, limit: int = 20) -> list[dict[str, Any]]:
        stmt = select(backups.c.id, backups.c.created_at).order_by(backups.c.created_at.desc()).limit(limit)
        with self.engine.begin() as conn:
            return [{"id": row.id, "created_at": format_datetime(row.created_at)} for row in conn.execute(stmt)]

    def get_backup(self, backup_id: int) -> dict[str, Any] | None:
        stmt = select(backups.c.payload).where(backups.c.id == backup_id)
        with self.engine.begin() as conn:
            row = conn.execute(stmt).first()
        if row is None:
            return None
        return json.loads(row.payload)

    def get_latest_backup(self) -> dict[str, Any] | None:
        stmt = select(backups.c.payload).order_by(backups.c.created_at.desc(), backups.c.id.desc()).limit(1)
        with self.engine.begin() as conn:
            row = conn.execute(stmt).first()
        if row is None:
            return None
        return json.loads(row.payload)

    def delete_backups_except(self, keep_id: int) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(delete(backups).where(backups.c.id != keep_id))
            return int(result.rowcount or 0)
