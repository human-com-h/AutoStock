from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.schemas.part import PartCreate, PartOut, PartUpdate
from app.services import part_service as svc

router = APIRouter(prefix="/api/parts", tags=["parts"], dependencies=[Depends(require_auth)])


@router.get("")
def search_parts(
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    rows = svc.search_parts(db, keyword=keyword, limit=limit)
    return success_body(data=[PartOut.model_validate(r).model_dump() for r in rows])


@router.get("/{part_id}")
def get_part(part_id: str, db: Session = Depends(get_db)):
    row = svc.get_part(db, part_id)
    return success_body(data=PartOut.model_validate(row).model_dump())


@router.post("")
def create_part(body: PartCreate, db: Session = Depends(get_db)):
    row = svc.create_part(db, **body.model_dump())
    return success_body(data=PartOut.model_validate(row).model_dump())


@router.put("/{part_id}")
def update_part(part_id: str, body: PartUpdate, db: Session = Depends(get_db)):
    row = svc.update_part(db, part_id, **body.model_dump(exclude_unset=True))
    return success_body(data=PartOut.model_validate(row).model_dump())


@router.delete("/{part_id}")
def delete_part(part_id: str, db: Session = Depends(get_db)):
    row = svc.delete_part(db, part_id)
    return success_body(data=PartOut.model_validate(row).model_dump())
