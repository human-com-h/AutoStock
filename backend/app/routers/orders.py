from __future__ import annotations

from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.schemas.order import (
    OrderReturnCreate,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    SalesOrderCreate,
    SalesOrderOut,
)
from app.services import order_service as svc
from app.services.order_print_service import build_order_pdf

router = APIRouter(
    prefix="/api/orders",
    tags=["orders"],
    dependencies=[Depends(require_auth)],
)


def _purchase_out(db: Session, order) -> dict:
    data = PurchaseOrderOut.model_validate(order).model_dump()
    data["items"] = [
        {
            "id": row.id,
            "order_id": row.order_id,
            "part_id": row.part_id,
            "quantity": float(row.quantity),
            "purchase_price": row.purchase_price,
            "amount": row.amount,
            "remark": row.remark,
        }
        for row in svc.get_purchase_items(db, order.id)
    ]
    return data


def _sales_out(db: Session, order) -> dict:
    data = SalesOrderOut.model_validate(order).model_dump()
    data["items"] = [
        {
            "id": row.id,
            "order_id": row.order_id,
            "part_id": row.part_id,
            "quantity": float(row.quantity),
            "sale_price": row.sale_price,
            "amount": row.amount,
            "cost_amount": row.cost_amount,
            "remark": row.remark,
        }
        for row in svc.get_sales_items(db, order.id)
    ]
    return data


@router.get("/purchases")
def list_purchases(
    limit: int = Query(default=100, ge=1, le=500),
    supplier_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    rows = [
        _purchase_out(db, row)
        for row in svc.list_purchase_orders(db, limit, supplier_id=supplier_id)
    ]
    return success_body(data=rows)


@router.post("/purchases")
def create_purchase(payload: PurchaseOrderCreate, db: Session = Depends(get_db)):
    order = svc.create_purchase_order(
        db,
        supplier_id=payload.supplier_id,
        order_date=payload.order_date.isoformat() if payload.order_date else None,
        items=[item.model_dump() for item in payload.items],
        remark=payload.remark,
    )
    return success_body(data=_purchase_out(db, order))


@router.get("/purchases/{order_id}")
def get_purchase(order_id: str, db: Session = Depends(get_db)):
    return success_body(data=_purchase_out(db, svc.get_purchase_order(db, order_id)))


@router.get("/purchases/{order_id}/pdf")
def download_purchase_pdf(order_id: str, db: Session = Depends(get_db)):
    content, filename = build_order_pdf(db, "purchases", order_id)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/purchases/{order_id}/returns")
def return_purchase(
    order_id: str,
    payload: OrderReturnCreate,
    db: Session = Depends(get_db),
):
    order = svc.create_purchase_return(
        db,
        source_order_id=order_id,
        items=[item.model_dump() for item in payload.items],
        remark=payload.remark,
    )
    return success_body(data=_purchase_out(db, order))


@router.post("/purchases/{order_id}/void")
def void_purchase(order_id: str, db: Session = Depends(get_db)):
    return success_body(data=_purchase_out(db, svc.void_purchase_order(db, order_id)))


@router.get("/sales")
def list_sales(
    limit: int = Query(default=100, ge=1, le=500),
    customer_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    rows = svc.list_sales_orders(db, limit, customer_id=customer_id)
    return success_body(data=[_sales_out(db, row) for row in rows])


@router.post("/sales")
def create_sale(payload: SalesOrderCreate, db: Session = Depends(get_db)):
    order = svc.create_sales_order(
        db,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        order_date=payload.order_date.isoformat() if payload.order_date else None,
        items=[item.model_dump() for item in payload.items],
        remark=payload.remark,
    )
    return success_body(data=_sales_out(db, order))


@router.get("/sales/{order_id}")
def get_sale(order_id: str, db: Session = Depends(get_db)):
    return success_body(data=_sales_out(db, svc.get_sales_order(db, order_id)))


@router.get("/sales/{order_id}/pdf")
def download_sales_pdf(order_id: str, db: Session = Depends(get_db)):
    content, filename = build_order_pdf(db, "sales", order_id)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/sales/{order_id}/returns")
def return_sale(
    order_id: str,
    payload: OrderReturnCreate,
    db: Session = Depends(get_db),
):
    order = svc.create_sales_return(
        db,
        source_order_id=order_id,
        items=[item.model_dump() for item in payload.items],
        remark=payload.remark,
    )
    return success_body(data=_sales_out(db, order))


@router.post("/sales/{order_id}/void")
def void_sale(order_id: str, db: Session = Depends(get_db)):
    return success_body(data=_sales_out(db, svc.void_sales_order(db, order_id)))
