"""用户操作历史：记录主数据修改前后版本，支持可审计的定向恢复。"""

from __future__ import annotations

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessMixin


class OperationHistory(BusinessMixin, Base):
    __tablename__ = "operation_history"
    __table_args__ = (
        Index("ix_operation_history_created", "created_at"),
        Index("ix_operation_history_entity", "entity_type", "entity_id", "created_at"),
    )

    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(26), nullable=False)
    entity_label: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String, nullable=False, default="本机用户")
    restored_from_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
