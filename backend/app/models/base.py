"""公共字段 Mixin（系统设计说明书 §4.1）。

所有业务表必须携带：id/created_at/updated_at/rev/version/device_id/is_deleted。
sync_status 仅手机端表需要，PC 后端库不用（PC 是 Hub，本身即真相来源）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class BusinessMixin:
    """业务表公共字段。rev 由 change_seq 服务在写入时回填，此处只声明列。"""

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(
        String, nullable=False, default=_utcnow_iso, onupdate=_utcnow_iso
    )
    rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    device_id: Mapped[str] = mapped_column(String(26), nullable=False, default="pc-local")
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
