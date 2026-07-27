"""登录会话与密码哈希（§8.1）。

阶段一只做 PC 本机登录：PBKDF2 密码哈希存 app_setting，会话用签名 Cookie（itsdangerous），
127.0.0.1 请求可按配置免登录。手机端 device_token 配对鉴权属于阶段二/三范围，暂不实现，
但本模块的 require_auth 依赖从现在起就挂在所有业务路由上，不留"以后再补鉴权"的缺口。
"""

from __future__ import annotations

import hashlib
import os
import secrets

from fastapi import Depends, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import UnauthorizedAppError
from app.db.session import get_db
from app.models.settings import AppSetting

_PBKDF2_ITERATIONS = 260_000
_SESSION_SECRET_KEY = "session_secret"
_PASSWORD_HASH_KEY = "login_password_hash"


def _get_setting(db: Session, key: str) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    return row.value if row else None


def _set_setting(db: Session, key: str, value: str) -> None:
    from app.core.ulid import new_ulid

    row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    if row is None:
        row = AppSetting(id=new_ulid(), key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, _digest_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    candidate = hash_password(password, salt=salt)
    return secrets.compare_digest(candidate, stored_hash)


def get_or_create_session_secret(db: Session) -> str:
    value = _get_setting(db, _SESSION_SECRET_KEY)
    if value is None:
        value = secrets.token_hex(32)
        _set_setting(db, _SESSION_SECRET_KEY, value)
    return value


def get_password_hash(db: Session) -> str | None:
    return _get_setting(db, _PASSWORD_HASH_KEY)


def set_password(db: Session, password: str) -> None:
    _set_setting(db, _PASSWORD_HASH_KEY, hash_password(password))


def _serializer(db: Session) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_or_create_session_secret(db), salt="autostock-session")


def create_session_token(db: Session) -> str:
    return _serializer(db).dumps({"authenticated": True})


def verify_session_token(db: Session, token: str) -> bool:
    max_age = settings.session_max_age_days * 24 * 3600
    try:
        data = _serializer(db).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return False
    return bool(data.get("authenticated"))


def _is_localhost(request: Request) -> bool:
    client_host = request.client.host if request.client else None
    return client_host in ("127.0.0.1", "::1", "localhost")


def require_auth(request: Request, db: Session = Depends(get_db)) -> None:
    """业务路由的鉴权依赖。未登录访问一律拒绝，不因局域网环境豁免（§8.1、CLAUDE.md 第 8 条）。"""
    if settings.localhost_auto_login and _is_localhost(request):
        return
    token = request.cookies.get(settings.session_cookie_name)
    if not token or not verify_session_token(db, token):
        raise UnauthorizedAppError()
