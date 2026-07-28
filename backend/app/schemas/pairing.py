from pydantic import BaseModel, Field


class PairingExchange(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    device_name: str = Field(min_length=1, max_length=80)
    client_time: str | None = None


class BootstrapQuery(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=500, ge=1, le=500)
