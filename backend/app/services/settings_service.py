"""系统设置读写（键值表 app_setting），供负库存开关、预警阈值等使用（§1.5.1）。"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.db.write_helpers import bump_version, new_row_kwargs
from app.models.settings import AppSetting

ALLOW_NEGATIVE_STOCK_KEY = "allow_negative_stock"
DEFAULT_PRINT_CUSTOM_FIELDS = [
    {"label": "运输方式", "value": "", "visible": True, "handwritten": True},
    {"label": "运费承担", "value": "", "visible": True, "handwritten": True},
    {"label": "物流单号", "value": "", "visible": True, "handwritten": True},
]
PUBLIC_DEFAULTS = {
    "shop_name": "AutoStock 汽配店",
    "default_unit": "个",
    "allow_negative_stock": "1",
    "stale_days": "180",
    "shop_phone": "",
    "shop_address": "",
    "business_scope": "",
    "print_notice": "商品如有质量问题，请及时联系我们处理。",
    "print_warehouse": "主仓库",
    "print_operator": "管理员",
    "settlement_method": "现结",
    "print_payment_account": "",
    "print_wechat": "",
    "print_warranty_period": "",
    "print_reviewer": "",
    "print_custom_fields": json.dumps(DEFAULT_PRINT_CUSTOM_FIELDS, ensure_ascii=False),
}


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


def _parse_print_custom_fields(raw: str | None) -> list[dict]:
    try:
        fields = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return [field.copy() for field in DEFAULT_PRINT_CUSTOM_FIELDS]
    if not isinstance(fields, list):
        return [field.copy() for field in DEFAULT_PRINT_CUSTOM_FIELDS]

    normalized = []
    for field in fields[:5]:
        if not isinstance(field, dict):
            continue
        label = str(field.get("label") or "").strip()
        if not label:
            continue
        normalized.append(
            {
                "label": label[:20],
                "value": str(field.get("value") or "")[:100],
                "visible": bool(field.get("visible", True)),
                "handwritten": bool(field.get("handwritten", False)),
            }
        )
    return normalized


def get_public_settings(db: Session) -> dict:
    values = {key: get_setting(db, key, default) for key, default in PUBLIC_DEFAULTS.items()}
    return {
        "shop_name": values["shop_name"],
        "default_unit": values["default_unit"],
        "allow_negative_stock": values["allow_negative_stock"] == "1",
        "stale_days": int(values["stale_days"] or 180),
        "shop_phone": values["shop_phone"],
        "shop_address": values["shop_address"],
        "business_scope": values["business_scope"],
        "print_notice": values["print_notice"],
        "print_warehouse": values["print_warehouse"],
        "print_operator": values["print_operator"],
        "settlement_method": values["settlement_method"],
        "print_payment_account": values["print_payment_account"],
        "print_wechat": values["print_wechat"],
        "print_warranty_period": values["print_warranty_period"],
        "print_reviewer": values["print_reviewer"],
        "print_custom_fields": _parse_print_custom_fields(values["print_custom_fields"]),
    }


def update_public_settings(db: Session, values: dict) -> dict:
    serialized = {
        "shop_name": values["shop_name"],
        "default_unit": values["default_unit"],
        "allow_negative_stock": "1" if values["allow_negative_stock"] else "0",
        "stale_days": str(values["stale_days"]),
        "shop_phone": values["shop_phone"],
        "shop_address": values["shop_address"],
        "business_scope": values["business_scope"],
        "print_notice": values["print_notice"],
        "print_warehouse": values["print_warehouse"],
        "print_operator": values["print_operator"],
        "settlement_method": values["settlement_method"],
        "print_payment_account": values["print_payment_account"],
        "print_wechat": values["print_wechat"],
        "print_warranty_period": values["print_warranty_period"],
        "print_reviewer": values["print_reviewer"],
        "print_custom_fields": json.dumps(values["print_custom_fields"], ensure_ascii=False),
    }
    for key, value in serialized.items():
        row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
        if row is None:
            db.add(AppSetting(key=key, value=value, **new_row_kwargs(db)))
        else:
            row.value = value
            bump_version(db, row)
    db.commit()
    return get_public_settings(db)
