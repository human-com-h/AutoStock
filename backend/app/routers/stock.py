from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.schemas.stock import StockSnapshotOut
from app.services import stock_service as svc

router = APIRouter(prefix="/api/stock", tags=["stock"], dependencies=[Depends(require_auth)])


@router.get("")
def list_inventory(
    keyword: str | None = None,
    brand_id: str | None = None,
    category_id: str | None = None,
    location: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return success_body(
        data=svc.list_inventory(
            db,
            keyword=keyword,
            brand_id=brand_id,
            category_id=category_id,
            location=location,
            limit=limit,
        )
    )


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db)):
    return success_body(data=svc.list_snapshots_with_alerts(db))


@router.get("/{part_id}")
def get_snapshot(part_id: str, db: Session = Depends(get_db)):
    row = svc.get_snapshot(db, part_id)
    return success_body(data=StockSnapshotOut.model_validate(row).model_dump())


@router.post("/recalculate")
def recalculate(db: Session = Depends(get_db)):
    svc.recalculate_all(db)
    return success_body(data={"message": "库存已重算"})
