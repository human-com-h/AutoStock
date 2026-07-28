from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsUpdate(BaseModel):
    shop_name: str = Field(min_length=1, max_length=100)
    default_unit: str = Field(min_length=1, max_length=20)
    allow_negative_stock: bool
    stale_days: int = Field(ge=1, le=3650)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=4, max_length=128)
