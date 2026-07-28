from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError, success_body
from app.core.security import require_auth, require_device_auth
from app.db.session import get_db
from app.models.sync import Device
from app.schemas.sync import ConflictResolve, DeviceUpdate, SyncPush
from app.services import backup_service, sync_service

router = APIRouter(tags=["sync"])


@router.post("/api/sync/push")
def push(
    body: SyncPush,
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
):
    try:
        backup_service.create_backup(
            "pre_sync",
            label=f"设备 {device.name or device.id} 同步前",
            reason=f"before_sync:{device.id}",
        )
    except (ValueError, OSError, sqlite3.DatabaseError) as exc:
        raise BusinessAppError(
            f"同步前保护点创建失败，已取消本次同步：{exc}",
            code="BUSINESS_PRE_SYNC_BACKUP_FAILED",
        ) from exc
    return success_body(
        data=sync_service.push_changes(
            db,
            device=device,
            request_device_id=body.device_id,
            client_batch_id=body.client_batch_id,
            changes=body.changes,
        )
    )


@router.get("/api/sync/pull")
def pull(
    since_rev: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=500),
    device: Device = Depends(require_device_auth),
    db: Session = Depends(get_db),
):
    return success_body(
        data=sync_service.pull_changes(
            db,
            device=device,
            since_rev=since_rev,
            limit=limit,
        )
    )


@router.get("/api/sync/summary", dependencies=[Depends(require_auth)])
def summary(db: Session = Depends(get_db)):
    return success_body(data=sync_service.sync_summary(db))


@router.get("/api/sync/logs", dependencies=[Depends(require_auth)])
def logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return success_body(data=sync_service.list_logs(db, limit=limit))


@router.get("/api/sync/conflicts", dependencies=[Depends(require_auth)])
def conflicts(
    unresolved_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return success_body(
        data=sync_service.list_conflicts(
            db,
            unresolved_only=unresolved_only,
            limit=limit,
        )
    )


@router.post(
    "/api/sync/conflicts/{conflict_id}/resolve",
    dependencies=[Depends(require_auth)],
)
def resolve_conflict(
    conflict_id: str,
    body: ConflictResolve,
    db: Session = Depends(get_db),
):
    return success_body(
        data=sync_service.resolve_conflict(db, conflict_id, action=body.action)
    )


@router.get("/api/devices", dependencies=[Depends(require_auth)])
def devices(db: Session = Depends(get_db)):
    return success_body(data=sync_service.list_devices(db))


@router.put("/api/devices/{device_id}", dependencies=[Depends(require_auth)])
def update_device(
    device_id: str,
    body: DeviceUpdate,
    db: Session = Depends(get_db),
):
    return success_body(
        data=sync_service.set_device_enabled(db, device_id, body.is_enabled)
    )
