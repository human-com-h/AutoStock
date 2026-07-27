from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _make_engine():
    from sqlalchemy import create_engine

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


engine: Engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
