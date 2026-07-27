"""业务写入的公共字段填充（§4.1、§12：单据/主数据写入统一在同一事务内完成）。

新建行：id/rev/version/device_id 由此统一生成；created_at/updated_at 走模型 default。
更新行：只需 bump_version，updated_at 靠 SQLAlchemy onupdate 在有列变更时自动刷新。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.ulid import new_ulid
from app.sync.change_seq import next_rev

DEFAULT_DEVICE_ID = "pc-local"


def new_row_kwargs(db: Session) -> dict[str, Any]:
    return {
        "id": new_ulid(),
        "rev": next_rev(db),
        "version": 1,
        "device_id": DEFAULT_DEVICE_ID,
    }


def bump_version(db: Session, row: Any) -> None:
    row.version += 1
    row.rev = next_rev(db)
