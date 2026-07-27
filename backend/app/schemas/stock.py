"""库存查询/预警响应模型（§1.2.6-1.2.7）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StockSnapshotOut(BaseModel):
    part_id: str
    quantity: float
    avg_cost: int
    last_in_at: str | None
    last_out_at: str | None
    calc_rev: int

    model_config = ConfigDict(from_attributes=True)


class StockAlertOut(BaseModel):
    part_id: str
    part_number: str
    name: str
    quantity: float
    avg_cost: int
    min_stock: float
    max_stock: float | None
    alerts: list[str]
