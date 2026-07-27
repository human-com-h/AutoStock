"""业务单据表：purchase_order/item、sales_order/item（§4.3）。"""

from __future__ import annotations

from sqlalchemy import Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessMixin


class PurchaseOrder(BusinessMixin, Base):
    __tablename__ = "purchase_order"

    order_no: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    supplier_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    order_date: Mapped[str] = mapped_column(String, nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_type: Mapped[str] = mapped_column(String, nullable=False, default="purchase")
    source_order_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)


class PurchaseItem(BusinessMixin, Base):
    __tablename__ = "purchase_item"
    __table_args__ = (
        Index("ix_purchase_item_order", "order_id"),
        Index("ix_purchase_item_part_created", "part_id", "created_at"),
    )

    order_id: Mapped[str] = mapped_column(String(26), nullable=False)
    part_id: Mapped[str] = mapped_column(String(26), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    purchase_price: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)


class SalesOrder(BusinessMixin, Base):
    __tablename__ = "sales_order"

    order_no: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    customer_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    order_date: Mapped[str] = mapped_column(String, nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    received_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_type: Mapped[str] = mapped_column(String, nullable=False, default="sale")
    source_order_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)


class SalesItem(BusinessMixin, Base):
    __tablename__ = "sales_item"
    __table_args__ = (
        Index("ix_sales_item_order", "order_id"),
        Index("ix_sales_item_part_created", "part_id", "created_at"),
    )

    order_id: Mapped[str] = mapped_column(String(26), nullable=False)
    part_id: Mapped[str] = mapped_column(String(26), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    sale_price: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
