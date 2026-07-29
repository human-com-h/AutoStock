"""Hub 同步协议：批次推送、增量拉取、LWW、冲突与设备管理（§7）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError, SyncAppError
from app.db.write_helpers import bump_version, new_row_kwargs
from app.models.master_data import Brand, Category, Customer, Part, Supplier
from app.models.orders import PurchaseItem, PurchaseOrder, SalesItem, SalesOrder
from app.models.stock import StockLedger, StockSnapshot
from app.models.sync import ChangeSeq, Device, SyncConflict, SyncLog
from app.schemas.sync import SyncChange
from app.services.settings_service import get_allow_negative_stock
from app.services.stock_service import append_ledger_entry, check_available_stock
from app.sync.change_seq import next_rev

MASTER_MODELS = {
    "part": Part,
    "brand": Brand,
    "category": Category,
    "supplier": Supplier,
    "customer": Customer,
}
ORDER_MODELS = {
    "purchase_order": PurchaseOrder,
    "sales_order": SalesOrder,
}
ITEM_MODELS = {
    "purchase_item": PurchaseItem,
    "sales_item": SalesItem,
}
PULL_MODELS = {
    **MASTER_MODELS,
    **ORDER_MODELS,
    **ITEM_MODELS,
    "stock_ledger": StockLedger,
}
_COMMON_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "rev",
    "version",
    "device_id",
    "is_deleted",
}
_SERVER_MANAGED_FIELDS = {"rev", "device_id"}
_PRIORITY = {
    **{name: 10 for name in MASTER_MODELS},
    **{name: 20 for name in ORDER_MODELS},
    **{name: 30 for name in ITEM_MODELS},
    "stock_ledger": 40,
}
_SYNC_ORDER_LEDGER_RULES = {
    "purchase": ("purchase", Decimal("1")),
    "purchase_return": ("purchase_return", Decimal("-1")),
    "sale": ("sale", Decimal("-1")),
    "sale_return": ("sale_return", Decimal("1")),
}


def _sync_order_group_key(change: SyncChange) -> tuple[str, str] | None:
    if change.table == "purchase_order":
        return ("purchase", str(change.row.get("id") or ""))
    if change.table == "sales_order":
        return ("sales", str(change.row.get("id") or ""))
    if change.table == "purchase_item":
        return ("purchase", str(change.row.get("order_id") or ""))
    if change.table == "sales_item":
        return ("sales", str(change.row.get("order_id") or ""))
    return None


def _group_sync_changes(
    changes: list[SyncChange],
) -> list[list[tuple[int, SyncChange]]]:
    indexed = list(enumerate(changes))
    item_groups = {
        str(change.row.get("id") or ""): key
        for _index, change in indexed
        if (key := _sync_order_group_key(change)) is not None
        and change.table in ITEM_MODELS
    }
    grouped: dict[tuple[str, str], list[tuple[int, SyncChange]]] = {}
    assigned: set[int] = set()

    for index, change in indexed:
        key = _sync_order_group_key(change)
        if key is None and change.table == "stock_ledger":
            key = item_groups.get(str(change.row.get("source_id") or ""))
        if key is None:
            continue
        grouped.setdefault(key, []).append((index, change))
        assigned.add(index)

    units = list(grouped.values())
    units.extend([[(index, change)] for index, change in indexed if index not in assigned])
    for unit in units:
        unit.sort(key=lambda item: (_PRIORITY.get(item[1].table, 99), item[0]))
    units.sort(
        key=lambda unit: (
            min(_PRIORITY.get(change.table, 99) for _index, change in unit),
            min(index for index, _change in unit),
        )
    )
    return units


def _validate_sync_order_group(unit: list[tuple[int, SyncChange]]) -> None:
    tables = {change.table for _index, change in unit}
    order_tables = tables & ORDER_MODELS.keys()
    item_tables = tables & ITEM_MODELS.keys()
    if not order_tables and not item_tables:
        return
    if len(order_tables) != 1 or len(item_tables) != 1:
        raise ValueError("移动端单据必须连同主表、明细和库存流水完整上传")

    order_table = next(iter(order_tables))
    item_table = next(iter(item_tables))
    expected_item_table = "purchase_item" if order_table == "purchase_order" else "sales_item"
    if item_table != expected_item_table:
        raise ValueError("移动端单据主表与明细类型不一致")

    orders = [change for _index, change in unit if change.table == order_table]
    items = [change for _index, change in unit if change.table == item_table]
    ledgers = [change for _index, change in unit if change.table == "stock_ledger"]
    if len(orders) != 1 or not items or len(ledgers) != len(items):
        raise ValueError("移动端单据必须包含一张主表、至少一条明细及逐条库存流水")

    order_id = str(orders[0].row.get("id") or "")
    item_ids = [str(change.row.get("id") or "") for change in items]
    if any(str(change.row.get("order_id") or "") != order_id for change in items):
        raise ValueError("移动端单据明细关联的主表不一致")
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("移动端单据包含重复明细")
    ledger_sources = [str(change.row.get("source_id") or "") for change in ledgers]
    if sorted(ledger_sources) != sorted(item_ids):
        raise ValueError("移动端单据明细与库存流水不是一一对应")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_time(value: str | None) -> datetime:
    if not value:
        raise ValueError("缺少 updated_at")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"{type(value).__name__} 不能序列化")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_default, sort_keys=True)


def dump_row(row: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        data[column.name] = float(value) if isinstance(value, Decimal) else value
    return data


def _current_rev(db: Session) -> int:
    row = db.get(ChangeSeq, 1)
    return row.current_rev if row else 0


def _external_fields(
    db: Session,
    model: Any,
    row: dict[str, Any],
    device_id: str,
    *,
    updated_at: str | None = None,
) -> dict[str, Any]:
    row_id = row.get("id")
    if not isinstance(row_id, str) or len(row_id) != 26:
        raise ValueError("业务行 id 必须是 26 位 ULID")
    values = {
        column.name: row[column.name]
        for column in model.__table__.columns
        if column.name in row and column.name not in _SERVER_MANAGED_FIELDS
    }
    values.update(
        {
            "id": row_id,
            "created_at": row.get("created_at") or _now(),
            "updated_at": updated_at or row.get("updated_at") or _now(),
            "rev": next_rev(db),
            "version": max(1, int(row.get("version", 1))),
            "device_id": device_id,
            "is_deleted": int(row.get("is_deleted", 0)),
        }
    )
    return values


def _changed_values(model: Any, row: dict[str, Any]) -> dict[str, Any]:
    return {
        column.name: row[column.name]
        for column in model.__table__.columns
        if column.name in row
        and column.name not in {"id", "created_at", "rev", "device_id"}
    }


def _record_conflict(
    db: Session,
    *,
    device_id: str,
    table_name: str,
    row_id: str,
    local_value: dict[str, Any],
    remote_value: dict[str, Any],
    resolution: str,
    conflict_type: str = "lww",
    clock_skew: bool = False,
) -> SyncConflict:
    fields = new_row_kwargs(db)
    fields["device_id"] = device_id
    conflict = SyncConflict(
        table_name=table_name,
        row_id=row_id,
        local_value=_json_dumps(local_value),
        remote_value=_json_dumps(remote_value),
        resolution=resolution,
        conflict_type=conflict_type,
        clock_skew=int(clock_skew),
        resolved_by=None,
        resolved_at=None,
        **fields,
    )
    db.add(conflict)
    db.flush()
    return conflict


def _effective_remote_time(
    change: SyncChange,
    received_at: datetime,
) -> tuple[datetime, bool]:
    remote_time = _parse_time(change.client_updated_at or change.row.get("updated_at"))
    skew = abs((received_at - remote_time).total_seconds()) > 300
    return (received_at if skew else remote_time), skew


def _apply_master_change(
    db: Session,
    change: SyncChange,
    device: Device,
    received_at: datetime,
    merge_map: dict[str, str],
) -> dict[str, Any] | None:
    model = MASTER_MODELS[change.table]
    remote = dict(change.row)
    if change.op == "delete":
        remote["is_deleted"] = 1
    row_id = remote.get("id")
    effective_time, clock_skew = _effective_remote_time(change, received_at)
    remote["updated_at"] = effective_time.isoformat()
    existing = db.get(model, row_id)

    if model is Part and existing is None:
        part_number = str(remote.get("part_number") or "").strip()
        if not part_number:
            raise ValueError("零件编号不能为空")
        master = db.execute(
            select(Part).where(
                Part.part_number == part_number,
                Part.merged_into.is_(None),
                Part.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if master is not None and master.id != row_id:
            remote["merged_into"] = master.id
            remote["is_active"] = 0
            remote["is_deleted"] = 1
            alias = Part(**_external_fields(db, Part, remote, device.id))
            db.add(alias)
            db.flush()
            merge_map[row_id] = master.id
            _record_conflict(
                db,
                device_id=device.id,
                table_name="part",
                row_id=row_id,
                local_value=dump_row(master),
                remote_value=remote,
                resolution="local_win",
                conflict_type="part_number_collision",
                clock_skew=clock_skew,
            )
            return {
                "table": "part",
                "id": row_id,
                "resolution": "merged",
                "merged_into": master.id,
                "server_row": dump_row(master),
                "clock_skew": clock_skew,
            }

    if existing is None:
        created = model(**_external_fields(
            db,
            model,
            remote,
            device.id,
            updated_at=effective_time.isoformat(),
        ))
        db.add(created)
        db.flush()
        if clock_skew:
            _record_conflict(
                db,
                device_id=device.id,
                table_name=change.table,
                row_id=row_id,
                local_value={},
                remote_value=remote,
                resolution="remote_win",
                conflict_type="clock_skew",
                clock_skew=True,
            )
            return {
                "table": change.table,
                "id": row_id,
                "resolution": "remote_win",
                "server_row": dump_row(created),
                "clock_skew": True,
            }
        return None

    local = dump_row(existing)
    local_time = _parse_time(existing.updated_at)
    remote_wins = effective_time > local_time
    resolution = "remote_win" if remote_wins else "local_win"
    conflict = _record_conflict(
        db,
        device_id=device.id,
        table_name=change.table,
        row_id=row_id,
        local_value=local,
        remote_value=remote,
        resolution=resolution,
        clock_skew=clock_skew,
    )
    if remote_wins:
        for key, value in _changed_values(model, remote).items():
            setattr(existing, key, value)
        existing.updated_at = effective_time.isoformat()
        existing.version = max(existing.version + 1, int(remote.get("version", 1)))
        existing.device_id = device.id
        existing.rev = next_rev(db)
        db.flush()
    return {
        "conflict_id": conflict.id,
        "table": change.table,
        "id": row_id,
        "resolution": resolution,
        "server_row": dump_row(existing),
        "clock_skew": clock_skew,
    }


def _next_order_number(db: Session, model: Any, order_no: str) -> str:
    candidate = order_no
    suffix = 2
    while db.execute(select(model.id).where(model.order_no == candidate)).scalar_one_or_none():
        candidate = f"{order_no}-{suffix}"
        suffix += 1
    return candidate


def _nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} 必须是大于等于 0 的整数分")
    return value


def _apply_order_change(
    db: Session,
    change: SyncChange,
    device: Device,
) -> dict[str, Any] | None:
    model = ORDER_MODELS[change.table]
    remote = dict(change.row)
    row_id = remote.get("id")
    existing = db.get(model, row_id)
    if existing is not None:
        return None
    order_no = str(remote.get("order_no") or "").strip()
    if not order_no:
        raise ValueError("单号不能为空")
    allowed_types = (
        {"purchase", "purchase_return"}
        if model is PurchaseOrder
        else {"sale", "sale_return"}
    )
    if remote.get("order_type") not in allowed_types:
        raise ValueError("单据业务类型无效")
    try:
        datetime.strptime(str(remote.get("order_date") or ""), "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("单据日期必须是 YYYY-MM-DD") from exc
    _nonnegative_int(remote.get("total_amount"), "单据总额")
    if model is PurchaseOrder:
        _nonnegative_int(remote.get("paid_amount"), "已付金额")
        partner_id = remote.get("supplier_id")
        if partner_id and db.get(Supplier, partner_id) is None:
            raise ValueError("采购单关联供应商不存在")
    else:
        _nonnegative_int(remote.get("received_amount"), "已收金额")
        partner_id = remote.get("customer_id")
        if partner_id and db.get(Customer, partner_id) is None:
            raise ValueError("销售单关联客户不存在")
    if remote.get("reversed_by") is not None:
        raise ValueError("手机端不能直接写入单据红冲关系")
    source_order_id = remote.get("source_order_id")
    if source_order_id and db.get(model, source_order_id) is None:
        raise ValueError("退货/红冲单关联的来源单据不存在")

    renamed = _next_order_number(db, model, order_no)
    conflict: dict[str, Any] | None = None
    if renamed != order_no:
        remote["order_no"] = renamed
        record = _record_conflict(
            db,
            device_id=device.id,
            table_name=change.table,
            row_id=row_id,
            local_value={"order_no": order_no},
            remote_value=remote,
            resolution="remote_win",
            conflict_type="order_number_collision",
        )
        conflict = {
            "conflict_id": record.id,
            "table": change.table,
            "id": row_id,
            "resolution": "renamed",
            "original_order_no": order_no,
            "server_order_no": renamed,
        }
    created = model(**_external_fields(db, model, remote, device.id))
    db.add(created)
    db.flush()
    return conflict


def _apply_item_change(
    db: Session,
    change: SyncChange,
    device: Device,
    merge_map: dict[str, str],
) -> None:
    model = ITEM_MODELS[change.table]
    remote = dict(change.row)
    row_id = remote.get("id")
    if db.get(model, row_id) is not None:
        return
    if remote.get("part_id") in merge_map:
        remote["part_id"] = merge_map[remote["part_id"]]
    parent_model = PurchaseOrder if model is PurchaseItem else SalesOrder
    parent = db.get(parent_model, remote.get("order_id"))
    if parent is None:
        raise ValueError("关联单据不存在")
    allowed_types = (
        {"purchase", "purchase_return"}
        if model is PurchaseItem
        else {"sale", "sale_return"}
    )
    if parent.order_type not in allowed_types:
        raise ValueError("单据主表与明细类型不一致")
    part = db.get(Part, remote.get("part_id"))
    if (
        part is None
        or part.merged_into is not None
        or part.is_deleted
        or not part.is_active
    ):
        raise ValueError("关联零件不存在、已停用或已合并")
    duplicate = db.execute(
        select(model.id).where(
            model.order_id == parent.id,
            model.part_id == part.id,
            model.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ValueError("同一张单据中不能重复添加同一零件")

    try:
        quantity = Decimal(str(remote.get("quantity")))
    except InvalidOperation as exc:
        raise ValueError("单据数量格式无效") from exc
    if quantity <= 0 or quantity.as_tuple().exponent < -3:
        raise ValueError("单据数量必须大于 0 且最多保留三位小数")
    price_field = "purchase_price" if model is PurchaseItem else "sale_price"
    price = _nonnegative_int(remote.get(price_field), "单价")
    amount = _nonnegative_int(remote.get("amount"), "明细金额")
    expected_amount = int(
        (quantity * price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    if amount != expected_amount:
        raise ValueError("单据明细金额与数量、单价不一致")
    if model is SalesItem:
        _nonnegative_int(remote.get("cost_amount"), "成本金额")

    created = model(**_external_fields(db, model, remote, device.id))
    db.add(created)
    db.flush()


def _validate_applied_order_total(
    db: Session,
    unit: list[tuple[int, SyncChange]],
) -> None:
    for _index, change in unit:
        if change.table == "purchase_order":
            order = db.get(PurchaseOrder, change.row.get("id"))
            item_model = PurchaseItem
        elif change.table == "sales_order":
            order = db.get(SalesOrder, change.row.get("id"))
            item_model = SalesItem
        else:
            continue
        if order is None:
            raise ValueError("同步单据主表未写入")
        item_total = db.execute(
            select(func.coalesce(func.sum(item_model.amount), 0)).where(
                item_model.order_id == order.id,
                item_model.is_deleted == 0,
            )
        ).scalar_one()
        if int(item_total) != order.total_amount:
            raise ValueError("单据总额与明细金额合计不一致")


def _apply_ledger_change(
    db: Session,
    change: SyncChange,
    device: Device,
    merge_map: dict[str, str],
) -> None:
    remote = dict(change.row)
    if remote.get("part_id") in merge_map:
        remote["part_id"] = merge_map[remote["part_id"]]
    if db.get(StockLedger, remote.get("id")) is not None:
        return
    part = db.get(Part, remote.get("part_id"))
    if part is None or part.merged_into is not None:
        raise ValueError("库存流水关联零件不存在或已合并")
    source_type = remote.get("source_type")
    if source_type == "purchase_item":
        item = db.get(PurchaseItem, remote.get("source_id"))
        parent = db.get(PurchaseOrder, item.order_id) if item is not None else None
    elif source_type == "sales_item":
        item = db.get(SalesItem, remote.get("source_id"))
        parent = db.get(SalesOrder, item.order_id) if item is not None else None
    else:
        raise ValueError("手机端库存流水来源类型无效")
    if item is None or parent is None:
        raise ValueError("库存流水关联的单据明细不存在")
    if item.part_id != remote["part_id"]:
        raise ValueError("库存流水与单据明细关联的零件不一致")

    rule = _SYNC_ORDER_LEDGER_RULES.get(parent.order_type)
    if rule is None:
        raise ValueError("库存流水关联的单据业务类型无效")
    expected_change_type, direction = rule
    try:
        quantity = Decimal(str(remote["quantity"]))
    except (InvalidOperation, KeyError) as exc:
        raise ValueError("库存流水数量格式无效") from exc
    expected_quantity = direction * Decimal(str(item.quantity))
    if remote.get("change_type") != expected_change_type or quantity != expected_quantity:
        raise ValueError("库存流水方向或数量与单据明细不一致")
    if quantity < 0 and not get_allow_negative_stock(db):
        if check_available_stock(db, part.id, -quantity) < 0:
            raise BusinessAppError(
                f"零件「{part.name}」库存不足，无法同步出库",
                code="BUSINESS_STOCK_INSUFFICIENT",
            )

    unit_cost = int(remote.get("unit_cost") or 0)
    if source_type == "purchase_item":
        unit_cost = item.purchase_price if quantity > 0 else unit_cost
    elif unit_cost == 0:
        snapshot = db.get(StockSnapshot, part.id)
        unit_cost = snapshot.avg_cost if snapshot is not None else 0

    remote["device_id"] = device.id
    entry = append_ledger_entry(
        db,
        part_id=remote["part_id"],
        change_type=remote["change_type"],
        quantity=quantity,
        source_type=source_type,
        source_id=remote["source_id"],
        unit_cost=unit_cost,
        remark=remote.get("remark"),
        occurred_at=remote.get("occurred_at"),
        external_row=remote,
    )
    if entry is None:
        return
    if entry.source_type == "sales_item":
        item.cost_amount = int(
            (abs(Decimal(str(item.quantity))) * entry.unit_cost).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        bump_version(db, item)
        if part.sale_price != item.sale_price:
            part.sale_price = item.sale_price
            bump_version(db, part)
    elif entry.source_type == "purchase_item" and part.purchase_price != item.purchase_price:
        part.purchase_price = item.purchase_price
        bump_version(db, part)
    db.flush()


def _apply_change(
    db: Session,
    change: SyncChange,
    device: Device,
    received_at: datetime,
    merge_map: dict[str, str],
) -> dict[str, Any] | None:
    if change.table in MASTER_MODELS:
        return _apply_master_change(db, change, device, received_at, merge_map)
    if change.table in ORDER_MODELS:
        return _apply_order_change(db, change, device)
    if change.table in ITEM_MODELS:
        _apply_item_change(db, change, device, merge_map)
        return None
    if change.table == "stock_ledger":
        _apply_ledger_change(db, change, device, merge_map)
        return None
    raise ValueError(f"不支持同步表 {change.table}")


def push_changes(
    db: Session,
    *,
    device: Device,
    request_device_id: str,
    client_batch_id: str,
    changes: list[SyncChange],
) -> dict[str, Any]:
    if request_device_id != device.id:
        raise SyncAppError("请求设备与令牌不匹配", code="SYNC_DEVICE_MISMATCH")
    duplicate = db.execute(
        select(SyncLog).where(
            SyncLog.device_id == device.id,
            SyncLog.direction == "push",
            SyncLog.client_batch_id == client_batch_id,
        )
    ).scalar_one_or_none()
    if duplicate is not None and duplicate.response_json:
        return json.loads(duplicate.response_json)
    if duplicate is not None:
        db.delete(duplicate)
        db.flush()

    started_at = _now()
    received_at = datetime.now(UTC)
    from_rev = _current_rev(db)
    accepted = 0
    rejected: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    merge_map: dict[str, str] = {}
    units = _group_sync_changes(changes)

    try:
        for unit in units:
            unit_conflicts: list[dict[str, Any]] = []
            try:
                with db.begin_nested():
                    _validate_sync_order_group(unit)
                    for _index, change in unit:
                        conflict = _apply_change(
                            db,
                            change,
                            device,
                            received_at,
                            merge_map,
                        )
                        if conflict is not None:
                            unit_conflicts.append(conflict)
                    _validate_applied_order_total(db, unit)
                    db.flush()
                accepted += len(unit)
                conflicts.extend(unit_conflicts)
            except (ValueError, KeyError, TypeError, IntegrityError, BusinessAppError) as exc:
                for _index, change in unit:
                    rejected.append(
                        {
                            "table": change.table,
                            "id": change.row.get("id", ""),
                            "reason": str(exc),
                        }
                    )

        device.last_sync_at = _now()
        bump_version(db, device)
        log_fields = new_row_kwargs(db)
        log_fields["device_id"] = device.id
        log = SyncLog(
            direction="push",
            client_batch_id=client_batch_id,
            started_at=started_at,
            finished_at=_now(),
            pushed_count=accepted,
            pulled_count=0,
            conflict_count=len(conflicts),
            from_rev=from_rev,
            to_rev=0,
            result="partial" if rejected else "success",
            message=f"接收 {accepted} 项，拒绝 {len(rejected)} 项",
            response_json=None,
            **log_fields,
        )
        db.add(log)
        db.flush()
        log.to_rev = _current_rev(db)
        response = {
            "batch_id": client_batch_id,
            "accepted": accepted,
            "rejected": rejected,
            "conflicts": conflicts,
            "server_rev": _current_rev(db),
        }
        log.response_json = _json_dumps(response)
        db.commit()
        return response
    except Exception as exc:
        db.rollback()
        try:
            failed_fields = new_row_kwargs(db)
            failed_fields["device_id"] = device.id
            db.add(
                SyncLog(
                    direction="push",
                    client_batch_id=client_batch_id,
                    started_at=started_at,
                    finished_at=_now(),
                    pushed_count=0,
                    pulled_count=0,
                    conflict_count=0,
                    from_rev=from_rev,
                    to_rev=_current_rev(db),
                    result="failed",
                    message=str(exc)[:500],
                    response_json=None,
                    **failed_fields,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        raise


def _page_changes(
    db: Session,
    since_rev: int,
    limit: int,
) -> tuple[list[dict[str, Any]], bool]:
    candidates: list[tuple[int, str, Any]] = []
    for table_name, model in PULL_MODELS.items():
        rows = db.execute(
            select(model)
            .where(model.rev > since_rev)
            .order_by(model.rev)
            .limit(limit + 1)
        ).scalars()
        candidates.extend((row.rev, table_name, row) for row in rows)
    candidates.sort(key=lambda item: (item[0], item[1]))
    has_more = len(candidates) > limit
    page = candidates[:limit]
    return [
        {
            "table": table_name,
            "op": "delete" if row.is_deleted else "upsert",
            "row": dump_row(row),
            "rev": rev,
        }
        for rev, table_name, row in page
    ], has_more


def pull_changes(
    db: Session,
    *,
    device: Device,
    since_rev: int,
    limit: int,
) -> dict[str, Any]:
    started_at = _now()
    current = _current_rev(db)
    if since_rev > current:
        raise SyncAppError("同步游标大于服务端版本，请重新初始化", code="SYNC_CURSOR_INVALID")
    changes, has_more = _page_changes(db, since_rev, limit)
    row_next_rev = changes[-1]["rev"] if changes else since_rev
    part_ids: set[str] = set()
    for change in changes:
        row = change["row"]
        if change["table"] == "part":
            part_ids.add(row["id"])
        elif "part_id" in row:
            part_ids.add(row["part_id"])
    snapshots = []
    if part_ids:
        for snapshot in db.execute(
            select(StockSnapshot).where(StockSnapshot.part_id.in_(part_ids))
        ).scalars():
            snapshots.append(dump_row(snapshot))

    device.last_pull_rev = max(device.last_pull_rev, row_next_rev)
    device.last_sync_at = _now()
    bump_version(db, device)
    log_fields = new_row_kwargs(db)
    log_fields["device_id"] = device.id
    log = SyncLog(
        direction="pull",
        client_batch_id=None,
        started_at=started_at,
        finished_at=_now(),
        pushed_count=0,
        pulled_count=len(changes),
        conflict_count=0,
        from_rev=since_rev,
        to_rev=row_next_rev,
        result="success",
        message=f"下发 {len(changes)} 项",
        response_json=None,
        **log_fields,
    )
    db.add(log)
    db.flush()
    next_rev_value = row_next_rev if has_more else _current_rev(db)
    device.last_pull_rev = max(device.last_pull_rev, next_rev_value)
    log.to_rev = next_rev_value
    response = {
        "changes": changes,
        "next_rev": next_rev_value,
        "has_more": has_more,
        "snapshots": snapshots,
    }
    db.commit()
    return response


def list_devices(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(select(Device).order_by(Device.created_at.desc())).scalars()
    return [
        {
            **dump_row(row),
            "token_hash": None,
        }
        for row in rows
    ]


def set_device_enabled(db: Session, device_id: str, enabled: bool) -> dict[str, Any]:
    row = db.get(Device, device_id)
    if row is None:
        raise BusinessAppError("设备不存在", code="BUSINESS_NOT_FOUND")
    row.is_enabled = int(enabled)
    bump_version(db, row)
    db.commit()
    result = dump_row(row)
    result["token_hash"] = None
    return result


def list_logs(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = db.execute(
        select(SyncLog).order_by(SyncLog.started_at.desc()).limit(limit)
    ).scalars()
    return [dump_row(row) | {"response_json": None} for row in rows]


def list_conflicts(
    db: Session,
    *,
    unresolved_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(SyncConflict)
    if unresolved_only:
        stmt = stmt.where(SyncConflict.resolved_at.is_(None))
    rows = db.execute(
        stmt.order_by(SyncConflict.created_at.desc()).limit(limit)
    ).scalars()
    result = []
    for row in rows:
        item = dump_row(row)
        item["local_value"] = json.loads(row.local_value)
        item["remote_value"] = json.loads(row.remote_value)
        result.append(item)
    return result


def _restore_conflict_snapshot(
    db: Session,
    conflict: SyncConflict,
    snapshot: dict[str, Any],
) -> None:
    model = MASTER_MODELS.get(conflict.table_name)
    if model is None:
        raise BusinessAppError("该类冲突只能确认，不能回填", code="BUSINESS_SYNC_NOT_RESTORABLE")
    target_id = snapshot.get("id") or conflict.row_id
    row = db.get(model, target_id)
    if row is None:
        values = _external_fields(
            db,
            model,
            snapshot,
            snapshot.get("device_id") or "pc-local",
            updated_at=_now(),
        )
        row = model(**values)
        db.add(row)
    else:
        for key, value in _changed_values(model, snapshot).items():
            setattr(row, key, value)
        row.updated_at = _now()
        row.version += 1
        row.rev = next_rev(db)
    db.flush()


def resolve_conflict(
    db: Session,
    conflict_id: str,
    *,
    action: str,
) -> dict[str, Any]:
    conflict = db.get(SyncConflict, conflict_id)
    if conflict is None:
        raise BusinessAppError("冲突记录不存在", code="BUSINESS_NOT_FOUND")
    if action == "restore_local":
        _restore_conflict_snapshot(db, conflict, json.loads(conflict.local_value))
    elif action == "restore_remote":
        _restore_conflict_snapshot(db, conflict, json.loads(conflict.remote_value))
    conflict.resolution = "manual" if action != "keep_current" else conflict.resolution
    conflict.resolved_by = "pc-user"
    conflict.resolved_at = _now()
    bump_version(db, conflict)
    db.commit()
    result = dump_row(conflict)
    result["local_value"] = json.loads(conflict.local_value)
    result["remote_value"] = json.loads(conflict.remote_value)
    return result


def sync_summary(db: Session) -> dict[str, int]:
    return {
        "devices": db.execute(select(func.count(Device.id))).scalar_one(),
        "enabled_devices": db.execute(
            select(func.count(Device.id)).where(Device.is_enabled == 1)
        ).scalar_one(),
        "unresolved_conflicts": db.execute(
            select(func.count(SyncConflict.id)).where(SyncConflict.resolved_at.is_(None))
        ).scalar_one(),
        "logs": db.execute(select(func.count(SyncLog.id))).scalar_one(),
    }
