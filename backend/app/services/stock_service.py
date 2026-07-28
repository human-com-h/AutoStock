"""库存流水写入、快照更新、移动加权成本计算、库存重算（§4.4、§5.1）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError
from app.core.money import round_half_up
from app.db.write_helpers import new_row_kwargs
from app.models.stock import StockLedger, StockSnapshot
from app.sync.change_seq import next_rev

ALL_CHANGE_TYPES = frozenset(
    {"purchase", "sale", "purchase_return", "sale_return", "adjust", "opening"}
)


def weighted_average_cost_after_in(
    current_quantity: Decimal,
    current_avg_cost: int,
    in_quantity: Decimal,
    in_unit_cost: int,
) -> int:
    """计算入库后的新移动加权平均成本（分），四舍五入到整数分。

    与 packages/shared/src/rules/weighted-cost.ts 的 weightedAverageCostAfterIn 保持算法一致。
    若新库存 <= 0（原库存为负数吃掉了本次入库），新均价直接取本次入库单价，避免除以非正数。
    """
    if in_quantity <= 0:
        raise ValueError("入库数量必须为正数")
    new_quantity = current_quantity + in_quantity
    if new_quantity <= 0:
        return in_unit_cost
    total_cost = current_quantity * current_avg_cost + in_quantity * in_unit_cost
    return round_half_up(float(total_cost / new_quantity))


def _get_or_create_snapshot(db: Session, part_id: str) -> StockSnapshot:
    snapshot = db.get(StockSnapshot, part_id)
    if snapshot is None:
        snapshot = StockSnapshot(part_id=part_id, quantity=Decimal("0"), avg_cost=0, calc_rev=0)
        db.add(snapshot)
        db.flush()
    return snapshot


def append_ledger_entry(
    db: Session,
    *,
    part_id: str,
    change_type: str,
    quantity: Decimal,
    source_type: str,
    source_id: str,
    unit_cost: int | None = None,
    remark: str | None = None,
    occurred_at: str | None = None,
    external_row: dict | None = None,
) -> StockLedger | None:
    """写入一条库存流水并同步更新快照，全程在调用方事务内完成（§4.4、§12）。

    `quantity` 按方向带正负号：入库/退货入/盘盈为正，出库/退货出/盘亏为负。
    幂等：`(source_type, source_id)` 已存在时静默跳过（重复推送不重复记账，§7.3）。
    返回 None 表示该来源已记账过，调用方不应再更新其他状态。
    """
    if change_type not in ALL_CHANGE_TYPES:
        raise ValueError(f"未知的库存变动类型: {change_type}")
    if quantity == 0:
        raise ValueError("库存流水数量不能为 0")

    existing = db.execute(
        select(StockLedger.id).where(
            StockLedger.source_type == source_type, StockLedger.source_id == source_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    snapshot = _get_or_create_snapshot(db, part_id)

    if quantity > 0:
        # 入库方向：按移动加权平均法重算均价
        cost = unit_cost or 0
        new_avg_cost = weighted_average_cost_after_in(
            current_quantity=Decimal(str(snapshot.quantity)),
            current_avg_cost=snapshot.avg_cost,
            in_quantity=quantity,
            in_unit_cost=cost,
        )
        snapshot.avg_cost = new_avg_cost
        entry_unit_cost = cost
        snapshot.last_in_at = occurred_at or datetime.now(UTC).isoformat()
    else:
        # 出库方向：按当前均价固化成本，均价本身不变
        entry_unit_cost = unit_cost if unit_cost is not None else snapshot.avg_cost
        snapshot.last_out_at = occurred_at or datetime.now(UTC).isoformat()

    snapshot.quantity = Decimal(str(snapshot.quantity)) + quantity
    snapshot.calc_rev += 1

    if external_row is None:
        common_fields = new_row_kwargs(db)
    else:
        common_fields = {
            "id": external_row["id"],
            "created_at": external_row.get("created_at") or datetime.now(UTC).isoformat(),
            "updated_at": external_row.get("updated_at") or datetime.now(UTC).isoformat(),
            "rev": next_rev(db),
            "version": max(1, int(external_row.get("version", 1))),
            "device_id": external_row["device_id"],
            "is_deleted": 0,
        }

    ledger = StockLedger(
        part_id=part_id,
        change_type=change_type,
        quantity=quantity,
        unit_cost=entry_unit_cost,
        source_type=source_type,
        source_id=source_id,
        occurred_at=occurred_at or datetime.now(UTC).isoformat(),
        remark=remark,
        **common_fields,
    )
    db.add(ledger)
    db.flush()
    return ledger


def check_available_stock(db: Session, part_id: str, out_quantity: Decimal) -> Decimal:
    """返回出库后的可用库存（可能为负）。

    是否阻止负库存由调用方按 allow_negative_stock 设置决定。
    """
    snapshot = _get_or_create_snapshot(db, part_id)
    return Decimal(str(snapshot.quantity)) - out_quantity


def recalculate_all(db: Session) -> None:
    """从 stock_ledger 重算全部 stock_snapshot（§1.2.4 手工触发的重算入口）。

    按 part_id 分组、按 occurred_at 顺序重放流水，重新计算移动加权均价与数量。
    """
    db.execute(
        update(StockSnapshot).values(
            quantity=Decimal("0"),
            avg_cost=0,
            last_in_at=None,
            last_out_at=None,
            calc_rev=StockSnapshot.calc_rev + 1,
        )
    )
    part_ids = [row[0] for row in db.execute(select(StockLedger.part_id).distinct())]
    for part_id in part_ids:
        entries = list(
            db.execute(
                select(StockLedger)
                .where(StockLedger.part_id == part_id)
                .order_by(StockLedger.occurred_at, StockLedger.rev)
            ).scalars()
        )
        quantity = Decimal("0")
        avg_cost = 0
        last_in_at: str | None = None
        last_out_at: str | None = None
        for entry in entries:
            qty = Decimal(str(entry.quantity))
            if qty > 0:
                avg_cost = weighted_average_cost_after_in(
                    current_quantity=quantity,
                    current_avg_cost=avg_cost,
                    in_quantity=qty,
                    in_unit_cost=entry.unit_cost,
                )
                last_in_at = entry.occurred_at
            else:
                last_out_at = entry.occurred_at
            quantity += qty

        snapshot = _get_or_create_snapshot(db, part_id)
        snapshot.quantity = quantity
        snapshot.avg_cost = avg_cost
        snapshot.last_in_at = last_in_at
        snapshot.last_out_at = last_out_at
        snapshot.calc_rev += 1
    db.commit()


def reconcile_inventory(db: Session) -> dict:
    """只读比对库存快照与流水汇总，不自动修改任何业务数据。"""
    ledger_totals = {
        part_id: Decimal(str(quantity or 0))
        for part_id, quantity in db.execute(
            select(StockLedger.part_id, func.sum(StockLedger.quantity)).group_by(
                StockLedger.part_id
            )
        )
    }
    snapshots = {
        row.part_id: Decimal(str(row.quantity))
        for row in db.execute(select(StockSnapshot)).scalars()
    }
    part_ids = sorted(set(ledger_totals) | set(snapshots))

    from app.models.master_data import Part

    part_rows = {
        row.id: row
        for row in db.execute(select(Part).where(Part.id.in_(part_ids))).scalars()
    } if part_ids else {}
    differences = []
    for part_id in part_ids:
        ledger_quantity = ledger_totals.get(part_id, Decimal("0"))
        snapshot_quantity = snapshots.get(part_id, Decimal("0"))
        if ledger_quantity == snapshot_quantity:
            continue
        part = part_rows.get(part_id)
        differences.append(
            {
                "part_id": part_id,
                "part_number": part.part_number if part else "",
                "name": part.name if part else "未知零件",
                "ledger_quantity": float(ledger_quantity),
                "snapshot_quantity": float(snapshot_quantity),
                "difference": float(snapshot_quantity - ledger_quantity),
            }
        )
    return {
        "ok": not differences,
        "checked_count": len(part_ids),
        "mismatch_count": len(differences),
        "differences": differences,
    }


def list_inventory(
    db: Session,
    *,
    keyword: str | None = None,
    brand_id: str | None = None,
    category_id: str | None = None,
    location: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """库存组合查询：编号、名称、品牌、分类和货位。"""
    from app.models.master_data import Part

    stmt = (
        select(Part, StockSnapshot)
        .outerjoin(StockSnapshot, StockSnapshot.part_id == Part.id)
        .where(Part.is_deleted == 0)
    )
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                Part.part_number.like(like),
                Part.oe_number.like(like),
                Part.name.like(like),
                Part.pinyin.like(f"%{keyword.upper()}%"),
            )
        )
    if brand_id:
        stmt = stmt.where(Part.brand_id == brand_id)
    if category_id:
        stmt = stmt.where(Part.category_id == category_id)
    if location:
        stmt = stmt.where(Part.location.like(f"%{location}%"))
    stmt = stmt.order_by(Part.part_number).limit(limit)

    return [
        {
            "part_id": part.id,
            "part_number": part.part_number,
            "name": part.name,
            "brand_id": part.brand_id,
            "category_id": part.category_id,
            "location": part.location,
            "unit": part.unit,
            "quantity": float(snapshot.quantity) if snapshot else 0,
            "avg_cost": snapshot.avg_cost if snapshot else 0,
            "stock_amount": round(
                (float(snapshot.quantity) if snapshot else 0)
                * (snapshot.avg_cost if snapshot else 0)
            ),
            "min_stock": float(part.min_stock),
            "max_stock": float(part.max_stock) if part.max_stock is not None else None,
        }
        for part, snapshot in db.execute(stmt)
    ]


def get_snapshot(db: Session, part_id: str) -> StockSnapshot:
    snapshot = db.get(StockSnapshot, part_id)
    if snapshot is None:
        raise BusinessAppError("该零件尚无库存记录", code="BUSINESS_NOT_FOUND")
    return snapshot


STALE_DAYS_DEFAULT = 180


def list_snapshots_with_alerts(db: Session, stale_days: int = STALE_DAYS_DEFAULT) -> list[dict]:
    """库存预警四类（§5.6）：库存不足、库存积压、长期未动销、负库存。"""
    from app.models.master_data import Part

    stmt = (
        select(Part, StockSnapshot)
        .outerjoin(StockSnapshot, StockSnapshot.part_id == Part.id)
        .where(Part.is_deleted == 0)
    )
    stale_before = datetime.now(UTC) - timedelta(days=stale_days)
    results = []
    for part, snapshot in db.execute(stmt):
        quantity = Decimal(str(snapshot.quantity)) if snapshot else Decimal("0")
        avg_cost = snapshot.avg_cost if snapshot else 0
        min_stock = Decimal(str(part.min_stock))
        alerts: list[str] = []
        if quantity < 0:
            alerts.append("negative")
        if min_stock > 0 and quantity <= min_stock:
            alerts.append("low")
        if part.max_stock is not None and quantity > Decimal(str(part.max_stock)):
            alerts.append("excess")
        if quantity > 0:
            last_out_at = snapshot.last_out_at if snapshot else None
            if last_out_at is None or datetime.fromisoformat(last_out_at) < stale_before:
                alerts.append("stale")
        if alerts:
            results.append(
                {
                    "part_id": part.id,
                    "part_number": part.part_number,
                    "name": part.name,
                    "quantity": float(quantity),
                    "avg_cost": avg_cost,
                    "min_stock": float(part.min_stock),
                    "max_stock": float(part.max_stock) if part.max_stock is not None else None,
                    "alerts": alerts,
                }
            )
    return results
