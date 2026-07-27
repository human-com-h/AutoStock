"""系统设置读写（键值表 app_setting），供负库存开关、预警阈值等使用（§1.5.1）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.db.write_helpers import bump_version, new_row_kwargs
from app.models.settings import AppSetting

ALLOW_NEGATIVE_STOCK_KEY = "allow_negative_stock"


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    return row.value if row is not None else default


def set_setting(db: Session, key: str, value: str) -> AppSetting:
    row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    if row is None:
        row = AppSetting(key=key, value=value, **new_row_kwargs(db))
        db.add(row)
    else:
        row.value = value
        bump_version(db, row)
    db.commit()
    return row


def get_allow_negative_stock(db: Session) -> bool:
    raw = get_setting(db, ALLOW_NEGATIVE_STOCK_KEY)
    if raw is None:
        return app_settings.allow_negative_stock_default
    return raw == "1"
