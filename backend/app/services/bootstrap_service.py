from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import business_now
from app.models.master_data import Brand, Category, Customer, Part, Supplier
from app.models.orders import PurchaseItem, PurchaseOrder, SalesItem, SalesOrder
from app.models.stock import StockLedger, StockSnapshot
from app.services.settings_service import get_public_settings


def parts_page(db: Session, offset: int, limit: int) -> dict:
    total = db.execute(
        select(func.count(Part.id)).where(Part.is_deleted == 0)
    ).scalar_one()
    rows = db.execute(
        select(Part, StockSnapshot)
        .outerjoin(StockSnapshot, StockSnapshot.part_id == Part.id)
        .where(Part.is_deleted == 0)
        .order_by(Part.part_number)
        .offset(offset)
        .limit(limit)
    )
    items = []
    for part, snapshot in rows:
        part_data = {
            column.name: getattr(part, column.name) for column in Part.__table__.columns
        }
        part_data["min_stock"] = float(part.min_stock)
        part_data["max_stock"] = (
            float(part.max_stock) if part.max_stock is not None else None
        )
        snapshot_data = {
            "part_id": part.id,
            "quantity": float(snapshot.quantity) if snapshot else 0,
            "avg_cost": snapshot.avg_cost if snapshot else 0,
            "last_in_at": snapshot.last_in_at if snapshot else None,
            "last_out_at": snapshot.last_out_at if snapshot else None,
            "updated_at": part.updated_at,
        }
        items.append({"part": part_data, "snapshot": snapshot_data})
    next_offset = offset + len(items)
    return {
        "items": items,
        "total": total,
        "next_offset": next_offset,
        "has_more": next_offset < total,
    }


def master_data(db: Session) -> dict:
    def dump(row) -> dict:
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}

    return {
        "suppliers": [dump(row) for row in _active_rows(db, Supplier)],
        "customers": [dump(row) for row in _active_rows(db, Customer)],
        "brands": [dump(row) for row in _active_rows(db, Brand)],
        "categories": [dump(row) for row in _active_rows(db, Category)],
    }


def mobile_settings(db: Session) -> dict:
    """返回手机离线预览需要的业务与打印设置。"""
    return get_public_settings(db)


def _active_rows(db: Session, model) -> list:
    return list(
        db.execute(
            select(model).where(model.is_deleted == 0, model.is_active == 1)
        ).scalars()
    )


def recent_orders(db: Session) -> dict:
    since = (business_now().date() - timedelta(days=90)).isoformat()
    purchases = list(
        db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.is_deleted == 0, PurchaseOrder.order_date >= since
            )
        ).scalars()
    )
    sales = list(
        db.execute(
            select(SalesOrder).where(
                SalesOrder.is_deleted == 0, SalesOrder.order_date >= since
            )
        ).scalars()
    )
    purchase_ids = [row.id for row in purchases]
    sales_ids = [row.id for row in sales]
    purchase_items = (
        list(
            db.execute(
                select(PurchaseItem).where(
                    PurchaseItem.order_id.in_(purchase_ids),
                    PurchaseItem.is_deleted == 0,
                )
            ).scalars()
        )
        if purchase_ids
        else []
    )
    sales_items = (
        list(
            db.execute(
                select(SalesItem).where(
                    SalesItem.order_id.in_(sales_ids), SalesItem.is_deleted == 0
                )
            ).scalars()
        )
        if sales_ids
        else []
    )
    stock_ledgers = list(
        db.execute(
            select(StockLedger)
            .where(StockLedger.is_deleted == 0, StockLedger.occurred_at >= since)
            .order_by(StockLedger.occurred_at.desc())
        ).scalars()
    )

    def dump(row) -> dict:
        data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        for key in ("quantity",):
            if key in data:
                data[key] = float(data[key])
        return data

    return {
        "purchase_orders": [dump(row) for row in purchases],
        "purchase_items": [dump(row) for row in purchase_items],
        "sales_orders": [dump(row) for row in sales],
        "sales_items": [dump(row) for row in sales_items],
        "stock_ledgers": [dump(row) for row in stock_ledgers],
    }
