"""API 测试的公共 fixture：每个测试用独立的临时 SQLite 文件，套用 Alembic 全部迁移。"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db_path() -> Iterator[str]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    for suffix in ("", "-wal", "-shm", "-journal"):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass


@pytest.fixture()
def app_client(db_path: str, monkeypatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("AUTOSTOCK_DATA_DIR", os.path.dirname(db_path))
    monkeypatch.setenv("AUTOSTOCK_DB_FILENAME", os.path.basename(db_path))

    from app.core import config as config_module
    from app.core.config import Settings

    test_settings = Settings()
    config_module.settings = test_settings

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from alembic import command
    from alembic.config import Config as AlembicConfig

    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    alembic_cfg = AlembicConfig(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    alembic_cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "migrations")
    )
    command.upgrade(alembic_cfg, "head")

    session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    from app.db import session as session_module

    session_module.engine = engine
    session_module.SessionLocal = session_local

    from app.main import app

    def _override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    from app.db.session import get_db

    app.dependency_overrides[get_db] = _override_get_db

    from app.core.security import require_auth

    app.dependency_overrides[require_auth] = lambda: None

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    engine.dispose()
