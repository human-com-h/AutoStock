from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import business_now
from app.models.master_data import Customer, Part, Supplier
from app.models.orders import PurchaseOrder, SalesItem, SalesOrder
from app.services.stock_service import list_inventory, list_snapshots_with_alerts


def dashboard(db: Session, days: int = 30) -> dict:
    today = business_now().date().isoformat()
    start = (business_now().date() - timedelta(days=days - 1)).isoformat()
    sales = list(
        db.execute(
            select(SalesOrder).where(
                SalesOrder.is_deleted == 0,
                SalesOrder.order_date >= start,
            )
        ).scalars()
    )
    purchases = list(
        db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.is_deleted == 0,
                PurchaseOrder.order_date >= start,
            )
        ).scalars()
    )
    sales_items = list(
        db.execute(
            select(SalesItem, SalesOrder)
            .join(SalesOrder, SalesOrder.id == SalesItem.order_id)
            .where(SalesOrder.is_deleted == 0, SalesItem.is_deleted == 0)
        )
    )
    trend: dict[str, dict[str, int]] = defaultdict(lambda: {"sales": 0, "profit": 0})
    for item, order in sales_items:
        sign = -1 if order.order_type == "sale_return" else 1
        trend[order.order_date]["sales"] += sign * item.amount
        trend[order.order_date]["profit"] += sign * (item.amount - item.cost_amount)
    alerts = list_snapshots_with_alerts(db)
    today_sales = trend[today]
    inventory = list_inventory(db, limit=1000)
    return {
        "today_sales": today_sales["sales"],
        "today_profit": today_sales["profit"],
        "low_stock_count": sum("low" in row["alerts"] for row in alerts),
        "negative_stock_count": sum("negative" in row["alerts"] for row in alerts),
        "inventory_amount": sum(row["stock_amount"] for row in inventory),
        "sales_order_count": len(sales),
        "purchase_order_count": len(purchases),
        "trend": [
            {"date": key, **trend[key]}
            for key in sorted(trend)
        ],
        "alerts": alerts[:20],
    }


def rankings(db: Session) -> dict:
    parts = {row.id: row for row in db.execute(select(Part)).scalars()}
    customers = {row.id: row for row in db.execute(select(Customer)).scalars()}
    suppliers = {row.id: row for row in db.execute(select(Supplier)).scalars()}
    part_totals: dict[str, dict[str, float | int | str]] = {}
    customer_totals: dict[str, int] = defaultdict(int)
    supplier_totals: dict[str, int] = defaultdict(int)

    for item, order in db.execute(
        select(SalesItem, SalesOrder)
        .join(SalesOrder, SalesOrder.id == SalesItem.order_id)
        .where(SalesOrder.is_deleted == 0, SalesItem.is_deleted == 0)
    ):
        sign = -1 if order.order_type == "sale_return" else 1
        row = part_totals.setdefault(
            item.part_id,
            {
                "part_id": item.part_id,
                "name": parts.get(item.part_id).name,
                "quantity": 0.0,
                "sales": 0,
            },
        )
        row["quantity"] = float(row["quantity"]) + sign * float(item.quantity)
        row["sales"] = int(row["sales"]) + sign * item.amount
        customer_name = (
            customers[order.customer_id].name
            if order.customer_id in customers
            else order.customer_name or "散客"
        )
        customer_totals[customer_name] += sign * item.amount

    for order in db.execute(
        select(PurchaseOrder).where(PurchaseOrder.is_deleted == 0)
    ).scalars():
        sign = -1 if order.order_type == "purchase_return" else 1
        name = suppliers[order.supplier_id].name if order.supplier_id in suppliers else "未指定"
        supplier_totals[name] += sign * order.total_amount

    return {
        "parts": sorted(part_totals.values(), key=lambda row: int(row["sales"]), reverse=True)[:20],
        "customers": [
            {"name": name, "sales": amount}
            for name, amount in sorted(
                customer_totals.items(), key=lambda row: row[1], reverse=True
            )[:20]
        ],
        "suppliers": [
            {"name": name, "purchases": amount}
            for name, amount in sorted(
                supplier_totals.items(), key=lambda row: row[1], reverse=True
            )[:20]
        ],
    }
