"""主数据表：category / brand / supplier / customer / part（§4.2）。"""

from __future__ import annotations

from sqlalchemy import Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessMixin


class Category(BusinessMixin, Base):
    __tablename__ = "category"

    name: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Brand(BusinessMixin, Base):
    __tablename__ = "brand"

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Supplier(BusinessMixin, Base):
    __tablename__ = "supplier"

    name: Mapped[str] = mapped_column(String, nullable=False)
    contact: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Customer(BusinessMixin, Base):
    __tablename__ = "customer"

    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Part(BusinessMixin, Base):
    __tablename__ = "part"
    __table_args__ = (
        Index("ix_part_oe_number", "oe_number"),
        Index("ix_part_pinyin", "pinyin"),
        Index("ix_part_name", "name"),
        Index("ix_part_category_brand", "category_id", "brand_id"),
    )

    part_number: Mapped[str] = mapped_column(String, nullable=False)
    oe_number: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    spec: Mapped[str | None] = mapped_column(String, nullable=True)
    brand_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    category_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    supplier_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    unit: Mapped[str] = mapped_column(String, nullable=False, default="个")
    purchase_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sale_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_stock: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    max_stock: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    vehicle_models: Mapped[str | None] = mapped_column(String, nullable=True)
    pinyin: Mapped[str | None] = mapped_column(String, nullable=True)
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    merged_into: Mapped[str | None] = mapped_column(String(26), nullable=True)
