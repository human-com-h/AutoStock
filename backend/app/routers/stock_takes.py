from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.schemas.stock_take import StockTakeCreate, StockTakeUpdate
from app.services import stock_take_service as svc

router = APIRouter(
    prefix="/api/stock-takes",
    tags=["stock-takes"],
    dependencies=[Depends(require_auth)],
)


def _out(db: Session, take) -> dict:
    return {
        "id": take.id,
        "take_no": take.take_no,
        "scope_type": take.scope_type,
        "scope_value": take.scope_value,
        "status": take.status,
        "started_at": take.started_at,
        "posted_at": take.posted_at,
        "remark": take.remark,
        "items": [
            {
                "id": item.id,
                "part_id": item.part_id,
                "book_quantity": float(item.book_quantity),
                "actual_quantity": (
                    float(item.actual_quantity) if item.actual_quantity is not None else None
                ),
                "diff_quantity": (
                    float(item.diff_quantity) if item.diff_quantity is not None else None
                ),
                "diff_amount": item.diff_amount,
            }
            for item in svc.list_stock_take_items(db, take.id)
        ],
    }


@router.get("")
def list_takes(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return success_body(data=[_out(db, row) for row in svc.list_stock_takes(db, limit)])


@router.post("")
def create_take(payload: StockTakeCreate, db: Session = Depends(get_db)):
    take = svc.create_stock_take(
        db,
        scope_type=payload.scope_type,
        scope_value=payload.scope_value,
        remark=payload.remark,
    )
    return success_body(data=_out(db, take))


@router.get("/{take_id}")
def get_take(take_id: str, db: Session = Depends(get_db)):
    return success_body(data=_out(db, svc.get_stock_take(db, take_id)))


@router.put("/{take_id}/items")
def update_take(take_id: str, payload: StockTakeUpdate, db: Session = Depends(get_db)):
    take = svc.update_actual_quantities(
        db,
        take_id,
        [item.model_dump() for item in payload.items],
    )
    return success_body(data=_out(db, take))


@router.post("/{take_id}/post")
def post_take(take_id: str, db: Session = Depends(get_db)):
    return success_body(data=_out(db, svc.post_stock_take(db, take_id)))
