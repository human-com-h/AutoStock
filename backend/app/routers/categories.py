from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.schemas.master_data import CategoryCreate, CategoryOut, CategoryUpdate
from app.services import master_data_service as svc

router = APIRouter(
    prefix="/api/categories", tags=["categories"], dependencies=[Depends(require_auth)]
)


@router.get("")
def list_categories(db: Session = Depends(get_db)):
    rows = svc.list_categories(db)
    return success_body(data=[CategoryOut.model_validate(r).model_dump() for r in rows])


@router.post("")
def create_category(body: CategoryCreate, db: Session = Depends(get_db)):
    row = svc.create_category(db, name=body.name, parent_id=body.parent_id, sort_no=body.sort_no)
    return success_body(data=CategoryOut.model_validate(row).model_dump())


@router.put("/{category_id}")
def update_category(category_id: str, body: CategoryUpdate, db: Session = Depends(get_db)):
    row = svc.update_category(db, category_id, **body.model_dump(exclude_unset=True))
    return success_body(data=CategoryOut.model_validate(row).model_dump())
