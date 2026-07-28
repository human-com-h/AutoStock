from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError, success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.schemas.history import HistoryRestoreRequest
from app.services import history_service

router = APIRouter(
    prefix="/api/history",
    tags=["history"],
    dependencies=[Depends(require_auth)],
)


@router.get("")
def list_history(
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = history_service.list_history(
        db,
        entity_type=entity_type,
        action=action,
        limit=limit,
    )
    return success_body(data=[history_service.history_detail(row) for row in rows])


@router.post("/{history_id}/restore")
def restore_history(
    history_id: str,
    payload: HistoryRestoreRequest,
    db: Session = Depends(get_db),
):
    if payload.confirm != "RESTORE":
        raise BusinessAppError(
            "请输入 RESTORE 确认恢复",
            code="VALIDATION_HISTORY_RESTORE_CONFIRM",
        )
    restored = history_service.restore_history(db, history_id)
    return success_body(data=history_service.history_detail(restored))
