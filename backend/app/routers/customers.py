from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.schemas.master_data import CustomerCreate, CustomerOut, CustomerUpdate
from app.services import master_data_service as svc

router = APIRouter(
    prefix="/api/customers", tags=["customers"], dependencies=[Depends(require_auth)]
)


@router.get("")
def list_customers(db: Session = Depends(get_db)):
    rows = svc.list_customers(db)
    return success_body(data=[CustomerOut.model_validate(r).model_dump() for r in rows])


@router.post("")
def create_customer(body: CustomerCreate, db: Session = Depends(get_db)):
    row = svc.create_customer(db, **body.model_dump())
    return success_body(data=CustomerOut.model_validate(row).model_dump())


@router.put("/{customer_id}")
def update_customer(customer_id: str, body: CustomerUpdate, db: Session = Depends(get_db)):
    row = svc.update_customer(db, customer_id, **body.model_dump(exclude_unset=True))
    return success_body(data=CustomerOut.model_validate(row).model_dump())
