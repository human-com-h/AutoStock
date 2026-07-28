"""单据号生成：CG/XS + yyyyMMdd + 4 位设备序列（§4.3, D-单号）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.time import business_now
from app.db.write_helpers import DEFAULT_DEVICE_ID, bump_version, new_row_kwargs
from app.models.settings import AppSetting

_DEVICE_SEQ_DIGITS = 4


def _counter_key(prefix: str, date_str: str) -> str:
    return f"order_seq:{DEFAULT_DEVICE_ID}:{prefix}:{date_str}"


def generate_order_no(db: Session, prefix: str) -> str:
    """在调用方所在事务内原子生成单号，同一天同前缀的序列号连续递增。"""
    date_str = business_now().strftime("%Y%m%d")
    key = _counter_key(prefix, date_str)

    row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    if row is None:
        seq = 1
        row = AppSetting(key=key, value=str(seq), **new_row_kwargs(db))
        db.add(row)
    else:
        seq = int(row.value or "0") + 1
        row.value = str(seq)
        bump_version(db, row)
    db.flush()

    return f"{prefix}{date_str}{seq:0{_DEVICE_SEQ_DIGITS}d}"
