from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.certs import discover_private_ipv4_addresses
from app.core.config import settings
from app.core.errors import BusinessAppError
from app.core.security import (
    create_device_token,
    get_or_create_device_secret,
)
from app.db.write_helpers import bump_version, new_row_kwargs
from app.models.settings import AppSetting
from app.models.sync import ChangeSeq, Device

_CODE_HASH_KEY = "pairing_code_hash"
_CODE_EXPIRES_KEY = "pairing_code_expires_at"


def _setting(db: Session, key: str) -> AppSetting | None:
    return db.query(AppSetting).filter(AppSetting.key == key).one_or_none()


def _set_setting_in_transaction(db: Session, key: str, value: str) -> None:
    row = _setting(db, key)
    if row is None:
        row = AppSetting(key=key, value=value, **new_row_kwargs(db))
        db.add(row)
    else:
        row.value = value
        bump_version(db, row)


def _code_hash(code: str, secret: str) -> str:
    return hashlib.sha256(f"{code}:{secret}".encode()).hexdigest()


def create_pairing_code(db: Session) -> dict:
    secret = get_or_create_device_secret(db)
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    _set_setting_in_transaction(db, _CODE_HASH_KEY, _code_hash(code, secret))
    _set_setting_in_transaction(db, _CODE_EXPIRES_KEY, expires_at.isoformat())
    db.commit()
    addresses = discover_private_ipv4_addresses() or ("127.0.0.1",)
    server_urls = [f"https://{address}:{settings.port_https}" for address in addresses]
    return {
        "code": code,
        "expires_at": expires_at.isoformat(),
        "server_time": datetime.now(UTC).isoformat(),
        "server_urls": server_urls,
        "pairing_urls": [f"{url}/m/#/setup?pair={code}" for url in server_urls],
        "ca_download_urls": [
            f"http://{address}:{settings.port_http}/ca.crt" for address in addresses
        ],
    }


def exchange_pairing_code(
    db: Session,
    code: str,
    device_name: str,
    client_time: str | None = None,
) -> dict:
    secret = get_or_create_device_secret(db)
    stored_hash = _setting(db, _CODE_HASH_KEY)
    expires = _setting(db, _CODE_EXPIRES_KEY)
    now = datetime.now(UTC)
    if (
        stored_hash is None
        or expires is None
        or not stored_hash.value
        or not expires.value
        or not secrets.compare_digest(stored_hash.value, _code_hash(code, secret))
        or datetime.fromisoformat(expires.value) < now
    ):
        raise BusinessAppError("配对码无效或已过期", code="BUSINESS_PAIRING_CODE_INVALID")

    if client_time:
        try:
            parsed_client_time = datetime.fromisoformat(client_time.replace("Z", "+00:00"))
            if parsed_client_time.tzinfo is None:
                parsed_client_time = parsed_client_time.replace(tzinfo=UTC)
        except ValueError as exc:
            raise BusinessAppError(
                "手机时间格式不正确，请检查系统时间后重试",
                code="BUSINESS_DEVICE_TIME_INVALID",
            ) from exc
        if abs((now - parsed_client_time.astimezone(UTC)).total_seconds()) > 120:
            raise BusinessAppError(
                "手机与电脑时间相差超过 2 分钟，请先校准手机时间",
                code="BUSINESS_DEVICE_TIME_SKEW",
            )

    device = Device(
        name=device_name.strip(),
        device_type="mobile",
        token_hash="pending",
        last_sync_at=None,
        last_pull_rev=0,
        is_enabled=1,
        **new_row_kwargs(db),
    )
    db.add(device)
    db.flush()
    token = create_device_token(db, device.id)
    device.token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored_hash.value = ""
    expires.value = ""
    bump_version(db, stored_hash)
    bump_version(db, expires)
    db.commit()
    change_seq = db.get(ChangeSeq, 1)
    return {
        "device_id": device.id,
        "device_token": token,
        "device_name": device.name,
        "server_time": now.isoformat(),
        "server_rev": change_seq.current_rev if change_seq else 0,
    }
