from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.services import report_service

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    dependencies=[Depends(require_auth)],
)


@router.get("/dashboard")
def dashboard(
    days: int = Query(default=30, ge=1, le=366),
    db: Session = Depends(get_db),
):
    return success_body(data=report_service.dashboard(db, days))


@router.get("/rankings")
def rankings(db: Session = Depends(get_db)):
    return success_body(data=report_service.rankings(db))
