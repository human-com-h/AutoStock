"""零件业务逻辑：唯一编号校验、拼音生成、停用/删除边界、四路检索（§4.2, D3）。"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError
from app.core.pinyin import pinyin_initials
from app.db.write_helpers import bump_version, new_row_kwargs
from app.models.master_data import Part
from app.models.stock import StockLedger

OE_SEPARATOR = ","


def _normalize_oe_number(oe_number: str | None) -> str | None:
    if not oe_number:
        return None
    values = [v.strip() for v in oe_number.split(OE_SEPARATOR) if v.strip()]
    return OE_SEPARATOR.join(values) if values else None


def _check_part_number_unique(db: Session, part_number: str, exclude_id: str | None = None) -> None:
    stmt = select(Part).where(Part.part_number == part_number, Part.is_deleted == 0)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None and existing.id != exclude_id:
        raise BusinessAppError(
            f"零件编号「{part_number}」已存在", code="BUSINESS_PART_NUMBER_DUPLICATE"
        )


def create_part(db: Session, **fields) -> Part:
    part_number = fields["part_number"]
    _check_part_number_unique(db, part_number)
    fields["oe_number"] = _normalize_oe_number(fields.get("oe_number"))
    row = Part(**fields, pinyin=pinyin_initials(fields["name"]), **new_row_kwargs(db))
    db.add(row)
    db.commit()
    return row


def update_part(db: Session, part_id: str, **fields) -> Part:
    row = db.get(Part, part_id)
    if row is None or row.is_deleted:
        raise BusinessAppError("零件不存在", code="BUSINESS_NOT_FOUND")
    new_part_number = fields.get("part_number")
    if new_part_number is not None and new_part_number != row.part_number:
        _check_part_number_unique(db, new_part_number, exclude_id=part_id)
    if "oe_number" in fields:
        fields["oe_number"] = _normalize_oe_number(fields["oe_number"])
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    if "name" in fields and fields["name"] is not None:
        row.pinyin = pinyin_initials(row.name)
    bump_version(db, row)
    db.commit()
    return row


def _has_ledger_history(db: Session, part_id: str) -> bool:
    stmt = select(StockLedger.id).where(StockLedger.part_id == part_id).limit(1)
    return db.execute(stmt).scalar_one_or_none() is not None


def delete_part(db: Session, part_id: str) -> Part:
    """已产生流水的零件只能停用，未产生流水的才可软删除（D3）。"""
    row = db.get(Part, part_id)
    if row is None or row.is_deleted:
        raise BusinessAppError("零件不存在", code="BUSINESS_NOT_FOUND")
    if _has_ledger_history(db, part_id):
        row.is_active = 0
        bump_version(db, row)
        db.commit()
        return row
    row.is_deleted = 1
    bump_version(db, row)
    db.commit()
    return row


def search_parts(db: Session, keyword: str | None = None, limit: int = 50) -> list[Part]:
    """四路检索：编号 / OE号 / 名称 / 拼音首字母，不做扫码（D8）。"""
    stmt = select(Part).where(Part.is_deleted == 0)
    if keyword:
        like = f"%{keyword}%"
        upper_like = f"%{keyword.upper()}%"
        stmt = stmt.where(
            or_(
                Part.part_number.like(like),
                Part.oe_number.like(like),
                Part.name.like(like),
                Part.pinyin.like(upper_like),
            )
        )
    stmt = stmt.order_by(Part.part_number).limit(limit)
    return list(db.execute(stmt).scalars())


def get_part(db: Session, part_id: str) -> Part:
    row = db.get(Part, part_id)
    if row is None or row.is_deleted:
        raise BusinessAppError("零件不存在", code="BUSINESS_NOT_FOUND")
    return row
