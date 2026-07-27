from __future__ import annotations

from pydantic import BaseModel, Field


class StockTakeCreate(BaseModel):
    scope_type: str = "all"
    scope_value: str | None = None
    remark: str | None = None


class StockTakeQuantityIn(BaseModel):
    part_id: str
    actual_quantity: float = Field(ge=0)


class StockTakeUpdate(BaseModel):
    items: list[StockTakeQuantityIn] = Field(min_length=1)
