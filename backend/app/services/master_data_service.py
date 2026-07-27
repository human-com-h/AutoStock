"""主数据业务逻辑：分类/品牌/供应商/客户的增删改查、停用规则、引用计数。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError
from app.db.write_helpers import bump_version, new_row_kwargs
from app.models.master_data import Brand, Category, Customer, Part, Supplier


def list_categories(db: Session) -> list[Category]:
    return list(db.execute(select(Category).where(Category.is_deleted == 0)).scalars())


def create_category(db: Session, name: str, parent_id: str | None, sort_no: int) -> Category:
    row = Category(name=name, parent_id=parent_id, sort_no=sort_no, **new_row_kwargs(db))
    db.add(row)
    db.commit()
    return row


def update_category(db: Session, category_id: str, **fields) -> Category:
    row = db.get(Category, category_id)
    if row is None or row.is_deleted:
        raise BusinessAppError("分类不存在", code="BUSINESS_NOT_FOUND")
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    bump_version(db, row)
    db.commit()
    return row


def list_brands(db: Session) -> list[tuple[Brand, int]]:
    stmt = (
        select(Brand, func.count(Part.id))
        .outerjoin(Part, (Part.brand_id == Brand.id) & (Part.is_deleted == 0))
        .where(Brand.is_deleted == 0)
        .group_by(Brand.id)
    )
    return [(row[0], row[1]) for row in db.execute(stmt)]


def create_brand(db: Session, name: str, remark: str | None) -> Brand:
    existing = db.execute(
        select(Brand).where(Brand.name == name, Brand.is_deleted == 0)
    ).scalar_one_or_none()
    if existing is not None:
        raise BusinessAppError(f"品牌名称「{name}」已存在", code="BUSINESS_BRAND_DUPLICATE")
    row = Brand(name=name, remark=remark, **new_row_kwargs(db))
    db.add(row)
    db.commit()
    return row


def update_brand(db: Session, brand_id: str, **fields) -> Brand:
    row = db.get(Brand, brand_id)
    if row is None or row.is_deleted:
        raise BusinessAppError("品牌不存在", code="BUSINESS_NOT_FOUND")
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    bump_version(db, row)
    db.commit()
    return row


def list_suppliers(db: Session) -> list[Supplier]:
    return list(db.execute(select(Supplier).where(Supplier.is_deleted == 0)).scalars())


def create_supplier(db: Session, **fields) -> Supplier:
    row = Supplier(**fields, **new_row_kwargs(db))
    db.add(row)
    db.commit()
    return row


def update_supplier(db: Session, supplier_id: str, **fields) -> Supplier:
    row = db.get(Supplier, supplier_id)
    if row is None or row.is_deleted:
        raise BusinessAppError("供应商不存在", code="BUSINESS_NOT_FOUND")
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    bump_version(db, row)
    db.commit()
    return row


def list_customers(db: Session) -> list[Customer]:
    return list(db.execute(select(Customer).where(Customer.is_deleted == 0)).scalars())


def create_customer(db: Session, **fields) -> Customer:
    row = Customer(**fields, **new_row_kwargs(db))
    db.add(row)
    db.commit()
    return row


def update_customer(db: Session, customer_id: str, **fields) -> Customer:
    row = db.get(Customer, customer_id)
    if row is None or row.is_deleted:
        raise BusinessAppError("客户不存在", code="BUSINESS_NOT_FOUND")
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    bump_version(db, row)
    db.commit()
    return row
