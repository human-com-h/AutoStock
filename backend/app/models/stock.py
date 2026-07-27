"""库存表：stock_ledger（唯一真相来源，append-only）、stock_snapshot（派生表）、
stock_take/stock_take_item（盘点单据，§5.5）。"""

from __future__ import annotations

from sqlalchemy import Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessMixin


class StockLedger(BusinessMixin, Base):
    __tablename__ = "stock_ledger"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_stock_ledger_source"),
        Index("ix_stock_ledger_part_occurred", "part_id", "occurred_at"),
    )

    part_id: Mapped[str] = mapped_column(String(26), nullable=False)
    change_type: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String(26), nullable=False)
    occurred_at: Mapped[str] = mapped_column(String, nullable=False)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)


class StockSnapshot(Base):
    """派生表，非同步同步对象（§7.3：库存数量不同步，由 Hub 依流水重算后下发）。"""

    __tablename__ = "stock_snapshot"

    part_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    avg_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_in_at: Mapped[str | None] = mapped_column(String, nullable=True)
    last_out_at: Mapped[str | None] = mapped_column(String, nullable=True)
    calc_rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StockTake(BusinessMixin, Base):
    __tablename__ = "stock_take"

    take_no: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    scope_type: Mapped[str] = mapped_column(String, nullable=False, default="all")
    scope_value: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    posted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)


class StockTakeItem(BusinessMixin, Base):
    __tablename__ = "stock_take_item"
    __table_args__ = (Index("ix_stock_take_item_take", "take_id"),)

    take_id: Mapped[str] = mapped_column(String(26), nullable=False)
    part_id: Mapped[str] = mapped_column(String(26), nullable=False)
    book_quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    book_rev: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_quantity: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    diff_quantity: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    diff_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
