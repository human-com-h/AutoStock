from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)
    parent_id: str | None = None
    sort_no: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    parent_id: str | None = None
    sort_no: int | None = None
    is_active: int | None = None


class CategoryOut(BaseModel):
    id: str
    name: str
    parent_id: str | None
    sort_no: int
    is_active: int

    model_config = ConfigDict(from_attributes=True)


class BrandCreate(BaseModel):
    name: str = Field(min_length=1)
    remark: str | None = None


class BrandUpdate(BaseModel):
    name: str | None = None
    remark: str | None = None
    is_active: int | None = None


class BrandOut(BaseModel):
    id: str
    name: str
    remark: str | None
    is_active: int
    part_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1)
    contact: str | None = None
    phone: str | None = None
    address: str | None = None
    remark: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact: str | None = None
    phone: str | None = None
    address: str | None = None
    remark: str | None = None
    is_active: int | None = None


class SupplierOut(BaseModel):
    id: str
    name: str
    contact: str | None
    phone: str | None
    address: str | None
    remark: str | None
    is_active: int

    model_config = ConfigDict(from_attributes=True)


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1)
    phone: str | None = None
    location: str | None = None
    remark: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    location: str | None = None
    remark: str | None = None
    is_active: int | None = None


class CustomerOut(BaseModel):
    id: str
    name: str
    phone: str | None
    location: str | None
    remark: str | None
    is_active: int

    model_config = ConfigDict(from_attributes=True)
