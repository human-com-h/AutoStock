from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.schemas.master_data import BrandCreate, BrandOut, BrandUpdate
from app.services import master_data_service as svc

router = APIRouter(prefix="/api/brands", tags=["brands"], dependencies=[Depends(require_auth)])


@router.get("")
def list_brands(db: Session = Depends(get_db)):
    rows = svc.list_brands(db)
    data = []
    for brand, part_count in rows:
        out = BrandOut.model_validate(brand).model_dump()
        out["part_count"] = part_count
        data.append(out)
    return success_body(data=data)


@router.post("")
def create_brand(body: BrandCreate, db: Session = Depends(get_db)):
    row = svc.create_brand(db, name=body.name, remark=body.remark)
    return success_body(data=BrandOut.model_validate(row).model_dump())


@router.put("/{brand_id}")
def update_brand(brand_id: str, body: BrandUpdate, db: Session = Depends(get_db)):
    row = svc.update_brand(db, brand_id, **body.model_dump(exclude_unset=True))
    return success_body(data=BrandOut.model_validate(row).model_dump())
