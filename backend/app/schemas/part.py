"""零件（part）Pydantic 模型（§4.2）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PartCreate(BaseModel):
    part_number: str = Field(min_length=1)
    oe_number: str | None = None
    name: str = Field(min_length=1)
    spec: str | None = None
    brand_id: str | None = None
    category_id: str | None = None
    supplier_id: str | None = None
    unit: str = "个"
    purchase_price: int = 0
    sale_price: int = 0
    min_stock: float = 0
    max_stock: float | None = None
    location: str | None = None
    vehicle_models: str | None = None
    remark: str | None = None


class PartUpdate(BaseModel):
    part_number: str | None = None
    oe_number: str | None = None
    name: str | None = None
    spec: str | None = None
    brand_id: str | None = None
    category_id: str | None = None
    supplier_id: str | None = None
    unit: str | None = None
    purchase_price: int | None = None
    sale_price: int | None = None
    min_stock: float | None = None
    max_stock: float | None = None
    location: str | None = None
    vehicle_models: str | None = None
    remark: str | None = None
    is_active: int | None = None


class PartOut(BaseModel):
    id: str
    part_number: str
    oe_number: str | None
    name: str
    spec: str | None
    brand_id: str | None
    category_id: str | None
    supplier_id: str | None
    unit: str
    purchase_price: int
    sale_price: int
    min_stock: float
    max_stock: float | None
    location: str | None
    vehicle_models: str | None
    pinyin: str | None
    remark: str | None
    is_active: int
    merged_into: str | None = None

    model_config = ConfigDict(from_attributes=True)
