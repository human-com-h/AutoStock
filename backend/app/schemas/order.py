"""采购单/销售单 Pydantic 模型（§4.3, §5.2-5.3）。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.time import business_now


class _HasPartId(Protocol):
    part_id: str


def _validate_unique_parts(items: Sequence[_HasPartId]) -> None:
    part_ids = [item.part_id for item in items]
    if len(part_ids) != len(set(part_ids)):
        raise ValueError("同一张单据中不能重复添加同一零件")


def _validate_order_date(value: date | None) -> None:
    if value is not None and value > business_now().date():
        raise ValueError("业务日期不能晚于今天")


class PurchaseItemIn(BaseModel):
    part_id: str = Field(min_length=26, max_length=26)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    purchase_price: int = Field(ge=0)
    remark: str | None = None


class PurchaseOrderCreate(BaseModel):
    supplier_id: str | None = Field(default=None, min_length=26, max_length=26)
    order_date: date | None = None
    items: list[PurchaseItemIn] = Field(min_length=1)
    remark: str | None = None

    @model_validator(mode="after")
    def validate_unique_parts(self):
        _validate_unique_parts(self.items)
        _validate_order_date(self.order_date)
        return self


class PurchaseItemOut(BaseModel):
    id: str
    order_id: str
    part_id: str
    quantity: float
    purchase_price: int
    amount: int
    remark: str | None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderOut(BaseModel):
    id: str
    order_no: str
    supplier_id: str | None
    order_date: str
    total_amount: int
    paid_amount: int
    order_type: str
    source_order_id: str | None
    reversed_by: str | None
    remark: str | None
    items: list[PurchaseItemOut] = []

    model_config = ConfigDict(from_attributes=True)


class SalesItemIn(BaseModel):
    part_id: str = Field(min_length=26, max_length=26)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    sale_price: int = Field(ge=0)
    remark: str | None = None


class SalesOrderCreate(BaseModel):
    customer_id: str | None = Field(default=None, min_length=26, max_length=26)
    customer_name: str | None = None
    order_date: date | None = None
    items: list[SalesItemIn] = Field(min_length=1)
    remark: str | None = None

    @model_validator(mode="after")
    def validate_unique_parts(self):
        _validate_unique_parts(self.items)
        _validate_order_date(self.order_date)
        return self


class ReturnItemIn(BaseModel):
    part_id: str = Field(min_length=26, max_length=26)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    remark: str | None = None


class OrderReturnCreate(BaseModel):
    items: list[ReturnItemIn] = Field(min_length=1)
    remark: str | None = None

    @model_validator(mode="after")
    def validate_unique_parts(self):
        _validate_unique_parts(self.items)
        return self


class SalesItemOut(BaseModel):
    id: str
    order_id: str
    part_id: str
    quantity: float
    sale_price: int
    amount: int
    cost_amount: int
    remark: str | None

    model_config = ConfigDict(from_attributes=True)


class SalesOrderOut(BaseModel):
    id: str
    order_no: str
    customer_id: str | None
    customer_name: str | None
    order_date: str
    total_amount: int
    received_amount: int
    order_type: str
    source_order_id: str | None
    reversed_by: str | None
    remark: str | None
    items: list[SalesItemOut] = []

    model_config = ConfigDict(from_attributes=True)
