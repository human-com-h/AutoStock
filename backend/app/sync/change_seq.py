"""全局写入序号（rev）服务。§4.5：Hub 每写入一行业务数据自增一次并回填该行 rev。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sync import ChangeSeq

_SINGLETON_ID = 1


def _ensure_row(db: Session) -> ChangeSeq:
    row = db.get(ChangeSeq, _SINGLETON_ID)
    if row is None:
        row = ChangeSeq(id=_SINGLETON_ID, current_rev=0)
        db.add(row)
        db.flush()
    return row


def next_rev(db: Session) -> int:
    """在调用方所在事务内自增并返回新的 rev。必须在业务写入的同一事务里调用。"""
    row = _ensure_row(db)
    row.current_rev += 1
    db.flush()
    return row.current_rev


def get_current_rev() -> int:
    """只读查询当前 rev，用于 /api/health 等只读场景，使用独立短连接。"""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        stmt = select(ChangeSeq).where(ChangeSeq.id == _SINGLETON_ID)
        row = db.execute(stmt).scalar_one_or_none()
        return row.current_rev if row else 0
