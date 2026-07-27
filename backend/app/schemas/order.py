"""采购单/销售单 Pydantic 模型（§4.3, §5.2-5.3）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PurchaseItemIn(BaseModel):
    part_id: str
    quantity: float = Field(gt=0)
    purchase_price: int = Field(ge=0)
    remark: str | None = None


class PurchaseOrderCreate(BaseModel):
    supplier_id: str | None = None
    items: list[PurchaseItemIn] = Field(min_length=1)
    remark: str | None = None


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
    part_id: str
    quantity: float = Field(gt=0)
    sale_price: int = Field(ge=0)
    remark: str | None = None


class SalesOrderCreate(BaseModel):
    customer_id: str | None = None
    customer_name: str | None = None
    items: list[SalesItemIn] = Field(min_length=1)
    remark: str | None = None


class ReturnItemIn(BaseModel):
    part_id: str
    quantity: float = Field(gt=0)
    remark: str | None = None


class OrderReturnCreate(BaseModel):
    items: list[ReturnItemIn] = Field(min_length=1)
    remark: str | None = None


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
