from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.schemas.master_data import SupplierCreate, SupplierOut, SupplierUpdate
from app.services import master_data_service as svc

router = APIRouter(
    prefix="/api/suppliers", tags=["suppliers"], dependencies=[Depends(require_auth)]
)


@router.get("")
def list_suppliers(db: Session = Depends(get_db)):
    rows = svc.list_suppliers(db)
    return success_body(data=[SupplierOut.model_validate(r).model_dump() for r in rows])


@router.post("")
def create_supplier(body: SupplierCreate, db: Session = Depends(get_db)):
    row = svc.create_supplier(db, **body.model_dump())
    return success_body(data=SupplierOut.model_validate(row).model_dump())


@router.put("/{supplier_id}")
def update_supplier(supplier_id: str, body: SupplierUpdate, db: Session = Depends(get_db)):
    row = svc.update_supplier(db, supplier_id, **body.model_dump(exclude_unset=True))
    return success_body(data=SupplierOut.model_validate(row).model_dump())
