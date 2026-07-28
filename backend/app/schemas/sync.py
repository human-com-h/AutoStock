from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SyncChange(BaseModel):
    table: str = Field(min_length=1, max_length=40)
    op: Literal["insert", "upsert", "delete"] = "upsert"
    row: dict[str, Any]
    client_updated_at: str | None = None


class SyncPush(BaseModel):
    device_id: str = Field(min_length=26, max_length=26)
    client_batch_id: str = Field(min_length=26, max_length=26)
    changes: list[SyncChange] = Field(max_length=1000)


class ConflictResolve(BaseModel):
    action: Literal["keep_current", "restore_local", "restore_remote"] = "keep_current"


class DeviceUpdate(BaseModel):
    is_enabled: bool
