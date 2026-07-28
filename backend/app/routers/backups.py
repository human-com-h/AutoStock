import json
import sqlite3
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.errors import BusinessAppError, success_body
from app.core.security import require_auth
from app.schemas.backup import BackupCreateRequest, RestoreRequest
from app.services import backup_service

router = APIRouter(
    prefix="/api/backups",
    tags=["backups"],
    dependencies=[Depends(require_auth)],
)


@router.get("")
def list_backups():
    return success_body(data=backup_service.list_backups())


@router.get("/retention-policy")
def get_retention_policy():
    return success_body(data=backup_service.retention_policy())


@router.post("")
def create_backup(payload: BackupCreateRequest | None = None):
    label = payload.label if payload else None
    try:
        return success_body(
            data=backup_service.create_backup(
                "manual",
                label=label,
                reason="manual",
            )
        )
    except (ValueError, sqlite3.DatabaseError) as exc:
        raise BusinessAppError(str(exc), code="BUSINESS_BACKUP_INVALID") from exc


@router.post("/restore")
def restore_backup(payload: RestoreRequest):
    if payload.confirm != "RESTORE":
        raise BusinessAppError("请输入 RESTORE 确认恢复", code="VALIDATION_RESTORE_CONFIRM")
    try:
        result = backup_service.restore_backup(payload.name)
    except FileNotFoundError as exc:
        raise BusinessAppError(str(exc), code="BUSINESS_BACKUP_NOT_FOUND") from exc
    except ValueError as exc:
        raise BusinessAppError(str(exc), code="BUSINESS_BACKUP_INVALID") from exc
    return success_body(data=result)


@router.get("/migration/export")
def export_migration_package():
    filename, content = backup_service.create_migration_package()
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(
        BytesIO(content),
        media_type="application/zip",
        headers=headers,
    )


@router.post("/migration/import")
async def import_migration_package(request: Request):
    content = await request.body()
    if len(content) > 1024 * 1024 * 1024:
        raise BusinessAppError("迁移包不能超过 1GB", code="VALIDATION_MIGRATION_TOO_LARGE")
    try:
        result = backup_service.import_migration_package(content)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise BusinessAppError(str(exc), code="BUSINESS_MIGRATION_INVALID") from exc
    return success_body(data=result)
