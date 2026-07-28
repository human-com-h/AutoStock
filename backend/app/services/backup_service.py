from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


def _settings():
    from app.core.config import settings

    return settings


def _backup_dir() -> Path:
    path = _settings().data_dir / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup(prefix: str = "manual") -> dict:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = _backup_dir() / f"{prefix}-{stamp}.db"
    with (
        closing(sqlite3.connect(_settings().db_path)) as source,
        closing(sqlite3.connect(destination)) as target,
    ):
        source.backup(target)
    return _info(destination)


def _info(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def list_backups() -> list[dict]:
    return [_info(path) for path in sorted(_backup_dir().glob("*.db"), reverse=True)]


def restore_backup(name: str) -> dict:
    source_path = (_backup_dir() / name).resolve()
    backup_root = _backup_dir().resolve()
    if source_path.parent != backup_root or not source_path.is_file():
        raise FileNotFoundError("备份文件不存在")
    create_backup("pre_restore")
    from app.db.session import engine

    engine.dispose()
    with (
        closing(sqlite3.connect(source_path)) as source,
        closing(sqlite3.connect(_settings().db_path)) as target,
    ):
        source.backup(target)
    return {"restored": name}
