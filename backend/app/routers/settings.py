from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError, success_body
from app.core.security import get_password_hash, require_auth, set_password, verify_password
from app.db.session import get_db
from app.schemas.settings import PasswordChange, SettingsUpdate
from app.services import settings_service as svc

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_auth)],
)


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    return success_body(data=svc.get_public_settings(db))


@router.put("")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    return success_body(data=svc.update_public_settings(db, payload.model_dump()))


@router.put("/password")
def change_password(payload: PasswordChange, db: Session = Depends(get_db)):
    stored = get_password_hash(db)
    if stored is not None and not verify_password(payload.current_password, stored):
        raise BusinessAppError("当前密码不正确", code="BUSINESS_PASSWORD_INCORRECT")
    set_password(db, payload.new_password)
    return success_body(data={"ok": True})
