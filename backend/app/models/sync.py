"""同步设备、批次日志与冲突留档（§4.5、§7）。"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessMixin


class ChangeSeq(Base):
    """单行表：全局写入序号。Hub 每写入一行业务数据自增一次，回填该行的 rev。"""

    __tablename__ = "change_seq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    current_rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Device(BusinessMixin, Base):
    __tablename__ = "device"

    name: Mapped[str] = mapped_column(String, nullable=False)
    device_type: Mapped[str] = mapped_column(String, nullable=False, default="mobile")
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    last_sync_at: Mapped[str | None] = mapped_column(String, nullable=True)
    last_pull_rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SyncLog(BusinessMixin, Base):
    __tablename__ = "sync_log"
    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "direction",
            "client_batch_id",
            name="uq_sync_log_device_direction_batch",
        ),
        Index("ix_sync_log_started_at", "started_at"),
    )

    direction: Mapped[str] = mapped_column(String, nullable=False)
    client_batch_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
    pushed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pulled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    from_rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    to_rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result: Mapped[str] = mapped_column(String, nullable=False, default="success")
    message: Mapped[str | None] = mapped_column(String, nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class SyncConflict(BusinessMixin, Base):
    __tablename__ = "sync_conflict"
    __table_args__ = (
        Index("ix_sync_conflict_unresolved", "resolved_at", "created_at"),
        Index("ix_sync_conflict_row", "table_name", "row_id"),
    )

    table_name: Mapped[str] = mapped_column(String, nullable=False)
    row_id: Mapped[str] = mapped_column(String(26), nullable=False)
    local_value: Mapped[str] = mapped_column(Text, nullable=False)
    remote_value: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str] = mapped_column(String, nullable=False)
    conflict_type: Mapped[str] = mapped_column(String, nullable=False, default="lww")
    clock_skew: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[str | None] = mapped_column(String, nullable=True)
