"""操作历史记录、查询和主数据历史版本恢复。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError
from app.core.pinyin import pinyin_initials
from app.db.write_helpers import bump_version, new_row_kwargs
from app.models.history import OperationHistory
from app.models.master_data import Brand, Category, Customer, Part, Supplier

ENTITY_CONFIG: dict[str, tuple[type, tuple[str, ...]]] = {
    "part": (
        Part,
        (
            "part_number",
            "oe_number",
            "name",
            "spec",
            "brand_id",
            "category_id",
            "supplier_id",
            "unit",
            "purchase_price",
            "sale_price",
            "min_stock",
            "max_stock",
            "location",
            "vehicle_models",
            "remark",
            "is_active",
            "is_deleted",
        ),
    ),
    "category": (Category, ("name", "parent_id", "sort_no", "is_active", "is_deleted")),
    "brand": (Brand, ("name", "remark", "is_active", "is_deleted")),
    "supplier": (
        Supplier,
        ("name", "contact", "phone", "address", "remark", "is_active", "is_deleted"),
    ),
    "customer": (
        Customer,
        ("name", "phone", "location", "remark", "is_active", "is_deleted"),
    ),
}

ENTITY_LABELS = {
    "part": "零件",
    "category": "分类",
    "brand": "品牌",
    "supplier": "供应商",
    "customer": "客户",
    "purchase_order": "采购单",
    "sales_order": "销售单",
    "stock_take": "盘点单",
}
HISTORY_DETAIL_RETENTION_DAYS = 365


def _json_default(value: Any):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"不支持的历史值类型：{type(value).__name__}")


def snapshot_row(row: Any, fields: tuple[str, ...] | None = None) -> dict[str, Any]:
    if fields is None:
        fields = tuple(column.key for column in inspect(row).mapper.column_attrs)
    return {field: getattr(row, field) for field in fields}


def add_history(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    entity_label: str,
    summary: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    restored_from_id: str | None = None,
) -> OperationHistory:
    compact_expired_history_details(db)
    row = OperationHistory(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        summary=summary,
        before_json=(
            json.dumps(before, ensure_ascii=False, default=_json_default) if before else None
        ),
        after_json=json.dumps(after, ensure_ascii=False, default=_json_default) if after else None,
        actor="本机用户",
        restored_from_id=restored_from_id,
        **new_row_kwargs(db),
    )
    db.add(row)
    return row


def compact_expired_history_details(db: Session) -> None:
    """保留审计摘要，但清除一年前的大体积前后快照，使其不可再恢复。"""
    cutoff = (datetime.now(UTC) - timedelta(days=HISTORY_DETAIL_RETENTION_DAYS)).isoformat()
    db.execute(
        update(OperationHistory)
        .where(
            OperationHistory.created_at < cutoff,
            (OperationHistory.before_json.is_not(None) | OperationHistory.after_json.is_not(None)),
        )
        .values(before_json=None, after_json=None)
    )


def add_master_history(
    db: Session,
    *,
    action: str,
    entity_type: str,
    row: Any,
    before: dict[str, Any] | None,
    summary: str,
) -> OperationHistory:
    config = ENTITY_CONFIG.get(entity_type)
    if config is None:
        raise ValueError(f"不支持的主数据类型：{entity_type}")
    after = snapshot_row(row, config[1])
    label = getattr(row, "name", None) or getattr(row, "part_number", row.id)
    return add_history(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=row.id,
        entity_label=str(label),
        summary=summary,
        before=before,
        after=after,
    )


def list_history(
    db: Session,
    *,
    entity_type: str | None = None,
    action: str | None = None,
    limit: int = 200,
) -> list[OperationHistory]:
    stmt = select(OperationHistory).where(OperationHistory.is_deleted == 0)
    if entity_type:
        stmt = stmt.where(OperationHistory.entity_type == entity_type)
    if action:
        stmt = stmt.where(OperationHistory.action == action)
    return list(
        db.execute(stmt.order_by(OperationHistory.created_at.desc()).limit(limit)).scalars()
    )


def history_detail(row: OperationHistory) -> dict[str, Any]:
    return {
        "id": row.id,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_type_label": ENTITY_LABELS.get(row.entity_type, row.entity_type),
        "entity_id": row.entity_id,
        "entity_label": row.entity_label,
        "summary": row.summary,
        "before": json.loads(row.before_json) if row.before_json else None,
        "after": json.loads(row.after_json) if row.after_json else None,
        "actor": row.actor,
        "created_at": row.created_at,
        "restored_from_id": row.restored_from_id,
        "can_restore": row.entity_type in ENTITY_CONFIG and row.before_json is not None,
    }


def _validate_unique_restore(db: Session, entity_type: str, target: Any, values: dict) -> None:
    if entity_type == "part":
        duplicate = db.execute(
            select(Part.id).where(
                Part.part_number == values["part_number"],
                Part.is_deleted == 0,
                Part.id != target.id,
            )
        ).scalar_one_or_none()
        if duplicate:
            raise BusinessAppError(
                f"无法恢复：零件编号「{values['part_number']}」已被其他零件使用",
                code="BUSINESS_HISTORY_RESTORE_CONFLICT",
            )
    elif entity_type == "brand":
        duplicate = db.execute(
            select(Brand.id).where(
                Brand.name == values["name"],
                Brand.is_deleted == 0,
                Brand.id != target.id,
            )
        ).scalar_one_or_none()
        if duplicate:
            raise BusinessAppError(
                f"无法恢复：品牌名称「{values['name']}」已被使用",
                code="BUSINESS_HISTORY_RESTORE_CONFLICT",
            )


def restore_history(db: Session, history_id: str) -> OperationHistory:
    source = db.get(OperationHistory, history_id)
    if source is None or source.is_deleted:
        raise BusinessAppError("操作记录不存在", code="BUSINESS_NOT_FOUND")
    config = ENTITY_CONFIG.get(source.entity_type)
    if config is None or source.before_json is None:
        raise BusinessAppError(
            "这条操作记录不能直接恢复，可使用单据红冲或整库还原点",
            code="BUSINESS_HISTORY_NOT_RESTORABLE",
        )
    model, fields = config
    target = db.get(model, source.entity_id)
    if target is None:
        raise BusinessAppError("原始资料不存在，不能定向恢复", code="BUSINESS_NOT_FOUND")

    restore_values = json.loads(source.before_json)
    _validate_unique_restore(db, source.entity_type, target, restore_values)
    current = snapshot_row(target, fields)
    for field in fields:
        if field in restore_values:
            setattr(target, field, restore_values[field])
    if source.entity_type == "part":
        target.pinyin = pinyin_initials(target.name)
    bump_version(db, target)
    restored = add_history(
        db,
        action="restore",
        entity_type=source.entity_type,
        entity_id=target.id,
        entity_label=str(
            getattr(target, "name", None) or getattr(target, "part_number", target.id)
        ),
        summary=f"恢复到 {source.created_at} 操作前的版本",
        before=current,
        after=snapshot_row(target, fields),
        restored_from_id=source.id,
    )
    db.commit()
    db.refresh(restored)
    return restored
