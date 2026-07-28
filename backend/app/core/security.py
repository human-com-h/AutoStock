"""登录会话与密码哈希（§8.1）。

PC 本机使用签名会话 Cookie，手机端使用配对后下发的长期 device_token。
require_auth 同时接受两种凭据，所有业务路由都必须挂载该依赖。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode

from fastapi import Depends, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import UnauthorizedAppError
from app.db.session import get_db
from app.models.settings import AppSetting
from app.models.sync import Device

_PBKDF2_ITERATIONS = 260_000
_SESSION_SECRET_KEY = "session_secret"
_PASSWORD_HASH_KEY = "login_password_hash"
_DEVICE_TOKEN_SECRET_KEY = "device_token_secret"


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


def _b64encode(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def get_or_create_device_secret(db: Session) -> str:
    value = _get_setting(db, _DEVICE_TOKEN_SECRET_KEY)
    if value is None:
        value = secrets.token_hex(32)
        _set_setting(db, _DEVICE_TOKEN_SECRET_KEY, value)
    return value


def create_device_token(db: Session, device_id: str) -> str:
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64encode(
        json.dumps({"sub": device_id, "iat": int(time.time())}).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    signature = hmac.new(
        get_or_create_device_secret(db).encode(),
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{header}.{payload}.{_b64encode(signature)}"


def verify_device_token(db: Session, token: str) -> Device | None:
    try:
        header, payload, signature = token.split(".", 2)
        signing_input = f"{header}.{payload}".encode()
        expected = hmac.new(
            get_or_create_device_secret(db).encode(),
            signing_input,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            return None
        data = json.loads(_b64decode(payload))
        device = db.get(Device, data["sub"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if (
        device is None
        or not device.is_enabled
        or not secrets.compare_digest(
            device.token_hash,
            hashlib.sha256(token.encode()).hexdigest(),
        )
    ):
        return None
    return device


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return request.headers.get("X-Device-Token")


def require_device_auth(request: Request, db: Session = Depends(get_db)) -> Device:
    token = _bearer_token(request)
    device = verify_device_token(db, token) if token else None
    if device is None:
        raise UnauthorizedAppError()
    return device


def _is_localhost(request: Request) -> bool:
    client_host = request.client.host if request.client else None
    return client_host in ("127.0.0.1", "::1", "localhost")


def require_auth(request: Request, db: Session = Depends(get_db)) -> None:
    """业务路由的鉴权依赖。未登录访问一律拒绝，不因局域网环境豁免（§8.1、CLAUDE.md 第 8 条）。"""
    if settings.localhost_auto_login and _is_localhost(request):
        return
    device_token = _bearer_token(request)
    if device_token and verify_device_token(db, device_token):
        return
    token = request.cookies.get(settings.session_cookie_name)
    if not token or not verify_session_token(db, token):
        raise UnauthorizedAppError()
