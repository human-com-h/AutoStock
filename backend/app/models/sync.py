"""同步相关表。阶段一只落地 change_seq（rev 从第一笔业务写入起就需要）。

device / sync_log / sync_conflict 属于阶段三范围，暂不建表，等同步系统开工时再补。
"""

from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChangeSeq(Base):
    """单行表：全局写入序号。Hub 每写入一行业务数据自增一次，回填该行的 rev。"""

    __tablename__ = "change_seq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    current_rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
