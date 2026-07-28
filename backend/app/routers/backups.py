from fastapi import APIRouter, Depends

from app.core.errors import BusinessAppError, success_body
from app.core.security import require_auth
from app.schemas.backup import RestoreRequest
from app.services import backup_service

router = APIRouter(
    prefix="/api/backups",
    tags=["backups"],
    dependencies=[Depends(require_auth)],
)


@router.get("")
def list_backups():
    return success_body(data=backup_service.list_backups())


@router.post("")
def create_backup():
    return success_body(data=backup_service.create_backup())


@router.post("/restore")
def restore_backup(payload: RestoreRequest):
    if payload.confirm != "RESTORE":
        raise BusinessAppError("请输入 RESTORE 确认恢复", code="VALIDATION_RESTORE_CONFIRM")
    try:
        result = backup_service.restore_backup(payload.name)
    except FileNotFoundError as exc:
        raise BusinessAppError(str(exc), code="BUSINESS_BACKUP_NOT_FOUND") from exc
    return success_body(data=result)
