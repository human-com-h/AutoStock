"""登录鉴权路由（§8.1，任务 1.5.1）。

首次使用没有密码时，先调用 /api/auth/setup 设置密码（仅在未设置过密码时可用），
此后走 /api/auth/login 校验密码换取会话 Cookie。127.0.0.1 请求可配置免登录（见 core/security）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BusinessAppError, success_body
from app.core.security import (
    get_password_hash,
    require_auth,
    set_password,
    verify_password,
)
from app.db.session import get_db
from app.schemas.auth import LoginRequest, SetPasswordRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    return success_body(data={"has_password": get_password_hash(db) is not None})


@router.post("/setup")
def setup_password(body: SetPasswordRequest, db: Session = Depends(get_db)):
    if get_password_hash(db) is not None:
        raise BusinessAppError(
            "已设置过登录密码，请使用修改密码功能", code="BUSINESS_PASSWORD_ALREADY_SET"
        )
    if len(body.password) < 4:
        raise BusinessAppError("密码至少 4 位", code="VALIDATION_PASSWORD_TOO_SHORT")
    set_password(db, body.password)
    return success_body(data={"ok": True})


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    stored_hash = get_password_hash(db)
    if stored_hash is None or not verify_password(body.password, stored_hash):
        raise BusinessAppError("密码不正确", code="BUSINESS_LOGIN_FAILED")
    from app.core.security import create_session_token

    token = create_session_token(db)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_max_age_days * 24 * 3600,
        httponly=True,
        samesite="lax",
    )
    return success_body(data={"ok": True})


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.session_cookie_name)
    return success_body(data={"ok": True})


@router.get("/me", dependencies=[Depends(require_auth)])
def me():
    return success_body(data={"authenticated": True})
