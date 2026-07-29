"""采购单/销售单业务逻辑：单事务写入主表+明细+流水+快照，红冲/当日撤销（§5.2-5.4, §12）。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError
from app.core.time import business_date_str
from app.db.write_helpers import DEFAULT_DEVICE_ID, bump_version, new_row_kwargs
from app.models.master_data import Customer, Part, Supplier
from app.models.orders import PurchaseItem, PurchaseOrder, SalesItem, SalesOrder
from app.models.stock import StockLedger, StockSnapshot
from app.models.sync import Device
from app.services.history_service import add_history
from app.services.order_no_service import generate_order_no
from app.services.settings_service import get_allow_negative_stock
from app.services.stock_service import append_ledger_entry, check_available_stock

_TODAY = business_date_str
_PURCHASE_DIRECTIONS = {"purchase": Decimal("1"), "purchase_return": Decimal("-1")}
_SALES_DIRECTIONS = {"sale": Decimal("-1"), "sale_return": Decimal("1")}


def _ensure_unique_parts(items: list[dict]) -> None:
    part_ids = [item["part_id"] for item in items]
    if len(part_ids) != len(set(part_ids)):
        raise BusinessAppError(
            "同一张单据中不能重复添加同一零件",
            code="BUSINESS_DUPLICATE_ORDER_ITEM",
        )


def _resolve_order_date(value: str | None) -> str:
    """校验业务日期；库存实际过账时间仍使用当前 UTC 时间。"""
    normalized = value or _TODAY()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise BusinessAppError(
            "业务日期格式不正确", code="BUSINESS_ORDER_DATE_INVALID"
        ) from exc
    if parsed > date.fromisoformat(_TODAY()):
        raise BusinessAppError(
            "业务日期不能晚于今天", code="BUSINESS_ORDER_DATE_FUTURE"
        )
    return parsed.isoformat()


def _backfill_ledger_remark(order_date: str) -> str | None:
    if order_date == _TODAY():
        return None
    return f"补录历史单据，业务日期 {order_date}"


def _ledger_unit_cost(
    db: Session,
    *,
    source_type: str,
    source_id: str,
    fallback: int,
) -> int:
    value = db.execute(
        select(StockLedger.unit_cost).where(
            StockLedger.source_type == source_type,
            StockLedger.source_id == source_id,
        )
    ).scalar_one_or_none()
    return int(value) if value is not None else fallback


def _snapshot_avg_cost(db: Session, part_id: str) -> int:
    snapshot = db.get(StockSnapshot, part_id)
    return snapshot.avg_cost if snapshot is not None else 0


def _sales_item_unit_cost(db: Session, item: SalesItem) -> int:
    quantity = Decimal(str(item.quantity))
    fallback = (
        int(
            (Decimal(item.cost_amount) / quantity).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        if quantity
        else 0
    )
    cost = _ledger_unit_cost(
        db,
        source_type="sales_item",
        source_id=item.id,
        fallback=fallback,
    )
    if cost == 0 and item.cost_amount == 0:
        return _snapshot_avg_cost(db, item.part_id)
    return cost


def _ensure_outbound_stock(
    db: Session,
    quantities_by_part: dict[str, Decimal],
) -> None:
    if get_allow_negative_stock(db):
        return
    for part_id, quantity in quantities_by_part.items():
        if quantity <= 0:
            continue
        if check_available_stock(db, part_id, quantity) < 0:
            part = db.get(Part, part_id)
            name = part.name if part is not None else part_id
            raise BusinessAppError(
                f"零件「{name}」库存不足，无法执行该操作",
                code="BUSINESS_STOCK_INSUFFICIENT",
            )


def _outbound_totals(items: list[PurchaseItem | SalesItem]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for item in items:
        totals[item.part_id] = totals.get(item.part_id, Decimal("0")) + Decimal(
            str(item.quantity)
        )
    return totals


def _line_amount(quantity: Decimal, unit_price: int) -> int:
    """数量（最多三位小数）乘以分单价，按统一规则四舍五入到分。"""
    return int((quantity * unit_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _get_active_part(db: Session, part_id: str) -> Part:
    part = db.get(Part, part_id)
    if part is None or part.is_deleted or not part.is_active:
        raise BusinessAppError("零件不存在或已停用", code="BUSINESS_PART_UNAVAILABLE")
    return part


def _ensure_active_partner(
    db: Session,
    model: type[Customer] | type[Supplier],
    row_id: str | None,
    label: str,
) -> None:
    if row_id is None:
        return
    row = db.get(model, row_id)
    if row is None or row.is_deleted or not row.is_active:
        raise BusinessAppError(
            f"{label}不存在或已停用",
            code="BUSINESS_PARTNER_UNAVAILABLE",
        )


def create_purchase_order(
    db: Session,
    *,
    supplier_id: str | None,
    order_date: str | None = None,
    items: list[dict],
    remark: str | None,
) -> PurchaseOrder:
    _ensure_unique_parts(items)
    _ensure_active_partner(db, Supplier, supplier_id, "供应商")
    resolved_order_date = _resolve_order_date(order_date)
    order_no = generate_order_no(db, "CG")
    order_kwargs = new_row_kwargs(db)
    order = PurchaseOrder(
        order_no=order_no,
        supplier_id=supplier_id,
        order_date=resolved_order_date,
        total_amount=0,
        paid_amount=0,
        order_type="purchase",
        remark=remark,
        **order_kwargs,
    )
    db.add(order)
    db.flush()

    total_amount = 0
    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
        part = _get_active_part(db, item["part_id"])
        quantity = Decimal(str(item["quantity"]))
        if quantity <= 0:
            raise BusinessAppError("入库数量必须为正数", code="BUSINESS_INVALID_QUANTITY")
        price = item["purchase_price"]
        amount = _line_amount(quantity, price)

        item_kwargs = new_row_kwargs(db)
        purchase_item = PurchaseItem(
            order_id=order.id,
            part_id=part.id,
            quantity=quantity,
            purchase_price=price,
            amount=amount,
            remark=item.get("remark"),
            **item_kwargs,
        )
        db.add(purchase_item)
        db.flush()

        append_ledger_entry(
            db,
            part_id=part.id,
            change_type="purchase",
            quantity=quantity,
            source_type="purchase_item",
            source_id=purchase_item.id,
            unit_cost=price,
            occurred_at=occurred_at,
            remark=_backfill_ledger_remark(resolved_order_date),
        )
        if part.purchase_price != price:
            part.purchase_price = price
            bump_version(db, part)
        total_amount += amount

    order.total_amount = total_amount
    add_history(
        db,
        action="create",
        entity_type="purchase_order",
        entity_id=order.id,
        entity_label=order.order_no,
        summary=(
            f"{'补录' if resolved_order_date != _TODAY() else '新建'}采购单"
            f"「{order.order_no}」，业务日期 {resolved_order_date}，"
            f"金额 {total_amount / 100:.2f} 元"
        ),
        after={
            "order_no": order.order_no,
            "order_type": order.order_type,
            "order_date": resolved_order_date,
            "total_amount": total_amount,
        },
    )
    db.commit()
    db.refresh(order)
    return order


def create_sales_order(
    db: Session,
    *,
    customer_id: str | None,
    customer_name: str | None,
    order_date: str | None = None,
    items: list[dict],
    remark: str | None,
) -> SalesOrder:
    _ensure_unique_parts(items)
    _ensure_active_partner(db, Customer, customer_id, "客户")
    resolved_order_date = _resolve_order_date(order_date)
    order_no = generate_order_no(db, "XS")
    allow_negative = get_allow_negative_stock(db)

    order_kwargs = new_row_kwargs(db)
    order = SalesOrder(
        order_no=order_no,
        customer_id=customer_id,
        customer_name=customer_name,
        order_date=resolved_order_date,
        total_amount=0,
        received_amount=0,
        order_type="sale",
        remark=remark,
        **order_kwargs,
    )
    db.add(order)
    db.flush()

    total_amount = 0
    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
        part = _get_active_part(db, item["part_id"])
        quantity = Decimal(str(item["quantity"]))
        if quantity <= 0:
            raise BusinessAppError("出库数量必须为正数", code="BUSINESS_INVALID_QUANTITY")

        available_after = check_available_stock(db, part.id, quantity)
        if available_after < 0 and not allow_negative:
            raise BusinessAppError(
                f"零件「{part.name}」库存不足，无法出库", code="BUSINESS_STOCK_INSUFFICIENT"
            )

        price = item["sale_price"]
        amount = _line_amount(quantity, price)

        item_kwargs = new_row_kwargs(db)
        sales_item = SalesItem(
            order_id=order.id,
            part_id=part.id,
            quantity=quantity,
            sale_price=price,
            amount=amount,
            cost_amount=0,
            remark=item.get("remark"),
            **item_kwargs,
        )
        db.add(sales_item)
        db.flush()

        ledger = append_ledger_entry(
            db,
            part_id=part.id,
            change_type="sale",
            quantity=-quantity,
            source_type="sales_item",
            source_id=sales_item.id,
            occurred_at=occurred_at,
            remark=_backfill_ledger_remark(resolved_order_date),
        )
        if ledger is not None:
            sales_item.cost_amount = _line_amount(quantity, ledger.unit_cost)
        if part.sale_price != price:
            part.sale_price = price
            bump_version(db, part)
        total_amount += amount

    order.total_amount = total_amount
    add_history(
        db,
        action="create",
        entity_type="sales_order",
        entity_id=order.id,
        entity_label=order.order_no,
        summary=(
            f"{'补录' if resolved_order_date != _TODAY() else '新建'}销售单"
            f"「{order.order_no}」，业务日期 {resolved_order_date}，"
            f"金额 {total_amount / 100:.2f} 元"
        ),
        after={
            "order_no": order.order_no,
            "order_type": order.order_type,
            "order_date": resolved_order_date,
            "total_amount": total_amount,
        },
    )
    db.commit()
    db.refresh(order)
    return order


def list_purchase_orders(
    db: Session,
    limit: int = 100,
    supplier_id: str | None = None,
) -> list[PurchaseOrder]:
    stmt = (
        select(PurchaseOrder)
        .where(PurchaseOrder.is_deleted == 0)
    )
    if supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    stmt = stmt.order_by(PurchaseOrder.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


def get_purchase_order(db: Session, order_id: str) -> PurchaseOrder:
    order = db.get(PurchaseOrder, order_id)
    if order is None or order.is_deleted:
        raise BusinessAppError("采购单不存在", code="BUSINESS_NOT_FOUND")
    return order


def list_sales_orders(
    db: Session,
    limit: int = 100,
    customer_id: str | None = None,
) -> list[SalesOrder]:
    stmt = (
        select(SalesOrder)
        .where(SalesOrder.is_deleted == 0)
    )
    if customer_id:
        stmt = stmt.where(SalesOrder.customer_id == customer_id)
    stmt = stmt.order_by(SalesOrder.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


def get_sales_order(db: Session, order_id: str) -> SalesOrder:
    order = db.get(SalesOrder, order_id)
    if order is None or order.is_deleted:
        raise BusinessAppError("销售单不存在", code="BUSINESS_NOT_FOUND")
    return order


def get_purchase_items(db: Session, order_id: str) -> list[PurchaseItem]:
    stmt = select(PurchaseItem).where(
        PurchaseItem.order_id == order_id,
        PurchaseItem.is_deleted == 0,
    )
    return list(db.execute(stmt).scalars())


def get_sales_items(db: Session, order_id: str) -> list[SalesItem]:
    stmt = select(SalesItem).where(
        SalesItem.order_id == order_id,
        SalesItem.is_deleted == 0,
    )
    return list(db.execute(stmt).scalars())


def _returned_purchase_quantity(db: Session, source_order_id: str, part_id: str) -> Decimal:
    value = db.execute(
        select(func.coalesce(func.sum(PurchaseItem.quantity), 0))
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseItem.order_id)
        .where(
            PurchaseOrder.source_order_id == source_order_id,
            PurchaseOrder.order_type == "purchase_return",
            PurchaseOrder.is_deleted == 0,
            PurchaseOrder.reversed_by.is_(None),
            PurchaseItem.part_id == part_id,
            PurchaseItem.is_deleted == 0,
        )
    ).scalar_one()
    return Decimal(str(value))


def create_purchase_return(
    db: Session,
    *,
    source_order_id: str,
    items: list[dict],
    remark: str | None,
) -> PurchaseOrder:
    _ensure_unique_parts(items)
    source = get_purchase_order(db, source_order_id)
    if (
        source.order_type != "purchase"
        or source.source_order_id is not None
        or source.reversed_by is not None
    ):
        raise BusinessAppError("该采购单不可退货", code="BUSINESS_RETURN_NOT_ALLOWED")

    original_items = {item.part_id: item for item in get_purchase_items(db, source.id)}
    return_order = PurchaseOrder(
        order_no=generate_order_no(db, "CG"),
        supplier_id=source.supplier_id,
        order_date=_TODAY(),
        total_amount=0,
        paid_amount=0,
        order_type="purchase_return",
        source_order_id=source.id,
        remark=remark,
        **new_row_kwargs(db),
    )
    db.add(return_order)
    db.flush()

    total_amount = 0
    occurred_at = datetime.now(UTC).isoformat()
    for request_item in items:
        original = original_items.get(request_item["part_id"])
        if original is None:
            raise BusinessAppError("退货零件不属于原采购单", code="BUSINESS_RETURN_ITEM_INVALID")
        quantity = Decimal(str(request_item["quantity"]))
        remaining = Decimal(str(original.quantity)) - _returned_purchase_quantity(
            db, source.id, original.part_id
        )
        if quantity <= 0 or quantity > remaining:
            raise BusinessAppError("退货数量超过可退数量", code="BUSINESS_RETURN_QUANTITY_INVALID")
        _ensure_outbound_stock(db, {original.part_id: quantity})
        amount = _line_amount(quantity, original.purchase_price)
        row = PurchaseItem(
            order_id=return_order.id,
            part_id=original.part_id,
            quantity=quantity,
            purchase_price=original.purchase_price,
            amount=amount,
            remark=request_item.get("remark"),
            **new_row_kwargs(db),
        )
        db.add(row)
        db.flush()
        append_ledger_entry(
            db,
            part_id=row.part_id,
            change_type="purchase_return",
            quantity=-quantity,
            source_type="purchase_item",
            source_id=row.id,
            occurred_at=occurred_at,
        )
        total_amount += amount

    return_order.total_amount = total_amount
    add_history(
        db,
        action="return",
        entity_type="purchase_order",
        entity_id=return_order.id,
        entity_label=return_order.order_no,
        summary=f"采购退货「{return_order.order_no}」，来源 {source.order_no}",
        after={
            "order_no": return_order.order_no,
            "source_order_id": source.id,
            "total_amount": total_amount,
        },
    )
    db.commit()
    db.refresh(return_order)
    return return_order


def _returned_sales_quantity(db: Session, source_order_id: str, part_id: str) -> Decimal:
    value = db.execute(
        select(func.coalesce(func.sum(SalesItem.quantity), 0))
        .join(SalesOrder, SalesOrder.id == SalesItem.order_id)
        .where(
            SalesOrder.source_order_id == source_order_id,
            SalesOrder.order_type == "sale_return",
            SalesOrder.is_deleted == 0,
            SalesOrder.reversed_by.is_(None),
            SalesItem.part_id == part_id,
            SalesItem.is_deleted == 0,
        )
    ).scalar_one()
    return Decimal(str(value))


def create_sales_return(
    db: Session,
    *,
    source_order_id: str,
    items: list[dict],
    remark: str | None,
) -> SalesOrder:
    _ensure_unique_parts(items)
    source = get_sales_order(db, source_order_id)
    if (
        source.order_type != "sale"
        or source.source_order_id is not None
        or source.reversed_by is not None
    ):
        raise BusinessAppError("该销售单不可退货", code="BUSINESS_RETURN_NOT_ALLOWED")

    original_items = {item.part_id: item for item in get_sales_items(db, source.id)}
    return_order = SalesOrder(
        order_no=generate_order_no(db, "XS"),
        customer_id=source.customer_id,
        customer_name=source.customer_name,
        order_date=_TODAY(),
        total_amount=0,
        received_amount=0,
        order_type="sale_return",
        source_order_id=source.id,
        remark=remark,
        **new_row_kwargs(db),
    )
    db.add(return_order)
    db.flush()

    total_amount = 0
    occurred_at = datetime.now(UTC).isoformat()
    for request_item in items:
        original = original_items.get(request_item["part_id"])
        if original is None:
            raise BusinessAppError("退货零件不属于原销售单", code="BUSINESS_RETURN_ITEM_INVALID")
        quantity = Decimal(str(request_item["quantity"]))
        remaining = Decimal(str(original.quantity)) - _returned_sales_quantity(
            db, source.id, original.part_id
        )
        if quantity <= 0 or quantity > remaining:
            raise BusinessAppError("退货数量超过可退数量", code="BUSINESS_RETURN_QUANTITY_INVALID")
        amount = _line_amount(quantity, original.sale_price)
        original_unit_cost = _sales_item_unit_cost(db, original)
        row = SalesItem(
            order_id=return_order.id,
            part_id=original.part_id,
            quantity=quantity,
            sale_price=original.sale_price,
            amount=amount,
            cost_amount=_line_amount(quantity, original_unit_cost),
            remark=request_item.get("remark"),
            **new_row_kwargs(db),
        )
        db.add(row)
        db.flush()
        append_ledger_entry(
            db,
            part_id=row.part_id,
            change_type="sale_return",
            quantity=quantity,
            source_type="sales_item",
            source_id=row.id,
            unit_cost=original_unit_cost,
            occurred_at=occurred_at,
        )
        total_amount += amount

    return_order.total_amount = total_amount
    add_history(
        db,
        action="return",
        entity_type="sales_order",
        entity_id=return_order.id,
        entity_label=return_order.order_no,
        summary=f"销售退货「{return_order.order_no}」，来源 {source.order_no}",
        after={
            "order_no": return_order.order_no,
            "source_order_id": source.id,
            "total_amount": total_amount,
        },
    )
    db.commit()
    db.refresh(return_order)
    return return_order


def _is_same_day_unsynced(
    db: Session,
    order: PurchaseOrder | SalesOrder,
) -> bool:
    """仅本机当日单据且尚未被任何启用设备拉取时允许直接撤销（§5.4）。"""
    order_day = order.order_date
    if order_day != _TODAY() or order.device_id != DEFAULT_DEVICE_ID:
        return False
    pulled = db.execute(
        select(Device.id).where(
            Device.is_enabled == 1,
            Device.last_pull_rev >= order.rev,
        )
    ).first()
    return pulled is None


def _purchase_has_active_returns(db: Session, order_id: str) -> bool:
    return (
        db.execute(
            select(PurchaseOrder.id).where(
                PurchaseOrder.source_order_id == order_id,
                PurchaseOrder.order_type == "purchase_return",
                PurchaseOrder.is_deleted == 0,
                PurchaseOrder.reversed_by.is_(None),
            )
        ).first()
        is not None
    )


def _sales_has_active_returns(db: Session, order_id: str) -> bool:
    return (
        db.execute(
            select(SalesOrder.id).where(
                SalesOrder.source_order_id == order_id,
                SalesOrder.order_type == "sale_return",
                SalesOrder.is_deleted == 0,
                SalesOrder.reversed_by.is_(None),
            )
        ).first()
        is not None
    )


def _unlink_purchase_reversal_parent(db: Session, order: PurchaseOrder) -> None:
    if order.source_order_id is None:
        return
    parent = db.get(PurchaseOrder, order.source_order_id)
    if parent is not None and parent.reversed_by == order.id:
        parent.reversed_by = None
        bump_version(db, parent)


def _unlink_sales_reversal_parent(db: Session, order: SalesOrder) -> None:
    if order.source_order_id is None:
        return
    parent = db.get(SalesOrder, order.source_order_id)
    if parent is not None and parent.reversed_by == order.id:
        parent.reversed_by = None
        bump_version(db, parent)


def void_purchase_order(db: Session, order_id: str) -> PurchaseOrder:
    order = db.get(PurchaseOrder, order_id)
    if order is None or order.is_deleted:
        raise BusinessAppError("采购单不存在", code="BUSINESS_NOT_FOUND")
    if order.reversed_by is not None:
        raise BusinessAppError("该单据已被红冲，不能重复作废", code="BUSINESS_ALREADY_REVERSED")
    if order.order_type not in _PURCHASE_DIRECTIONS:
        raise BusinessAppError("采购单业务类型无效", code="BUSINESS_ORDER_TYPE_INVALID")
    if order.order_type == "purchase" and _purchase_has_active_returns(db, order.id):
        raise BusinessAppError(
            "原采购单已有未撤销的退货单，请先撤销退货单",
            code="BUSINESS_ORDER_HAS_ACTIVE_RETURNS",
        )

    if _is_same_day_unsynced(db, order):
        return _delete_purchase_order_and_rollback(db, order)
    return _reverse_purchase_order(db, order)


def _delete_purchase_order_and_rollback(db: Session, order: PurchaseOrder) -> PurchaseOrder:
    items = (
        db.query(PurchaseItem)
        .filter(PurchaseItem.order_id == order.id, PurchaseItem.is_deleted == 0)
        .all()
    )
    compensation_direction = -_PURCHASE_DIRECTIONS[order.order_type]
    if compensation_direction < 0:
        _ensure_outbound_stock(db, _outbound_totals(items))

    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
        quantity = compensation_direction * Decimal(str(item.quantity))
        adjusts_value = quantity < 0
        append_ledger_entry(
            db,
            part_id=item.part_id,
            change_type="purchase" if quantity > 0 else "purchase_return",
            quantity=quantity,
            source_type=(
                "purchase_item_void_value" if adjusts_value else "purchase_item_void"
            ),
            source_id=item.id,
            unit_cost=(
                _snapshot_avg_cost(db, item.part_id)
                if order.order_type == "purchase_return"
                else item.purchase_price
            ),
            occurred_at=occurred_at,
            remark="同日撤销回滚",
            adjust_avg_on_out=adjusts_value,
        )
        item.is_deleted = 1
        bump_version(db, item)
    order.is_deleted = 1
    bump_version(db, order)
    _unlink_purchase_reversal_parent(db, order)
    add_history(
        db,
        action="void",
        entity_type="purchase_order",
        entity_id=order.id,
        entity_label=order.order_no,
        summary=f"撤销当日未同步采购单「{order.order_no}」",
        after={"order_no": order.order_no, "is_deleted": 1},
    )
    db.commit()
    db.refresh(order)
    return order


def _reverse_purchase_order(db: Session, order: PurchaseOrder) -> PurchaseOrder:
    """生成方向相反的采购域红冲单，并在原单记录 reversed_by（§5.4）。"""
    items = (
        db.query(PurchaseItem)
        .filter(PurchaseItem.order_id == order.id, PurchaseItem.is_deleted == 0)
        .all()
    )
    reversal_direction = -_PURCHASE_DIRECTIONS[order.order_type]
    if reversal_direction < 0:
        _ensure_outbound_stock(db, _outbound_totals(items))
    reversal_type = "purchase" if reversal_direction > 0 else "purchase_return"

    reversal_no = generate_order_no(db, "CG")
    reversal = PurchaseOrder(
        order_no=reversal_no,
        supplier_id=order.supplier_id,
        order_date=_TODAY(),
        total_amount=order.total_amount,
        paid_amount=0,
        order_type=reversal_type,
        source_order_id=order.id,
        remark=f"红冲原单 {order.order_no}",
        **new_row_kwargs(db),
    )
    db.add(reversal)
    db.flush()

    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
        quantity = reversal_direction * Decimal(str(item.quantity))
        adjusts_value = quantity < 0
        reversal_item = PurchaseItem(
            order_id=reversal.id,
            part_id=item.part_id,
            quantity=item.quantity,
            purchase_price=item.purchase_price,
            amount=item.amount,
            remark="红冲",
            **new_row_kwargs(db),
        )
        db.add(reversal_item)
        db.flush()
        append_ledger_entry(
            db,
            part_id=item.part_id,
            change_type="purchase" if quantity > 0 else "purchase_return",
            quantity=quantity,
            source_type=(
                "purchase_item_reversal_value"
                if adjusts_value
                else "purchase_item_reversal"
            ),
            source_id=reversal_item.id,
            unit_cost=(
                _snapshot_avg_cost(db, item.part_id)
                if order.order_type == "purchase_return"
                else item.purchase_price
            ),
            occurred_at=occurred_at,
            remark="红冲",
            adjust_avg_on_out=adjusts_value,
        )

    order.reversed_by = reversal.id
    bump_version(db, order)
    _unlink_purchase_reversal_parent(db, order)
    add_history(
        db,
        action="reverse",
        entity_type="purchase_order",
        entity_id=order.id,
        entity_label=order.order_no,
        summary=f"红冲采购单「{order.order_no}」，生成 {reversal.order_no}",
        after={"order_no": order.order_no, "reversed_by": reversal.id},
    )
    db.commit()
    db.refresh(order)
    return order


def void_sales_order(db: Session, order_id: str) -> SalesOrder:
    order = db.get(SalesOrder, order_id)
    if order is None or order.is_deleted:
        raise BusinessAppError("销售单不存在", code="BUSINESS_NOT_FOUND")
    if order.reversed_by is not None:
        raise BusinessAppError("该单据已被红冲，不能重复作废", code="BUSINESS_ALREADY_REVERSED")
    if order.order_type not in _SALES_DIRECTIONS:
        raise BusinessAppError("销售单业务类型无效", code="BUSINESS_ORDER_TYPE_INVALID")
    if order.order_type == "sale" and _sales_has_active_returns(db, order.id):
        raise BusinessAppError(
            "原销售单已有未撤销的退货单，请先撤销退货单",
            code="BUSINESS_ORDER_HAS_ACTIVE_RETURNS",
        )

    if _is_same_day_unsynced(db, order):
        return _delete_sales_order_and_rollback(db, order)
    return _reverse_sales_order(db, order)


def _delete_sales_order_and_rollback(db: Session, order: SalesOrder) -> SalesOrder:
    items = (
        db.query(SalesItem)
        .filter(SalesItem.order_id == order.id, SalesItem.is_deleted == 0)
        .all()
    )
    compensation_direction = -_SALES_DIRECTIONS[order.order_type]
    if compensation_direction < 0:
        _ensure_outbound_stock(db, _outbound_totals(items))

    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
        quantity = compensation_direction * Decimal(str(item.quantity))
        adjusts_value = quantity < 0
        append_ledger_entry(
            db,
            part_id=item.part_id,
            change_type="sale_return" if quantity > 0 else "sale",
            quantity=quantity,
            source_type="sales_item_void_value" if adjusts_value else "sales_item_void",
            source_id=item.id,
            unit_cost=_sales_item_unit_cost(db, item),
            occurred_at=occurred_at,
            remark="同日撤销回滚",
            adjust_avg_on_out=adjusts_value,
        )
        item.is_deleted = 1
        bump_version(db, item)
    order.is_deleted = 1
    bump_version(db, order)
    _unlink_sales_reversal_parent(db, order)
    add_history(
        db,
        action="void",
        entity_type="sales_order",
        entity_id=order.id,
        entity_label=order.order_no,
        summary=f"撤销当日未同步销售单「{order.order_no}」",
        after={"order_no": order.order_no, "is_deleted": 1},
    )
    db.commit()
    db.refresh(order)
    return order


def _reverse_sales_order(db: Session, order: SalesOrder) -> SalesOrder:
    """生成方向相反的销售域红冲单，并在原单记录 reversed_by（§5.4）。"""
    items = (
        db.query(SalesItem)
        .filter(SalesItem.order_id == order.id, SalesItem.is_deleted == 0)
        .all()
    )
    reversal_direction = -_SALES_DIRECTIONS[order.order_type]
    if reversal_direction < 0:
        _ensure_outbound_stock(db, _outbound_totals(items))
    reversal_type = "sale_return" if reversal_direction > 0 else "sale"

    reversal_no = generate_order_no(db, "XS")
    reversal = SalesOrder(
        order_no=reversal_no,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        order_date=_TODAY(),
        total_amount=order.total_amount,
        received_amount=0,
        order_type=reversal_type,
        source_order_id=order.id,
        remark=f"红冲原单 {order.order_no}",
        **new_row_kwargs(db),
    )
    db.add(reversal)
    db.flush()

    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
        quantity = reversal_direction * Decimal(str(item.quantity))
        unit_cost = _sales_item_unit_cost(db, item)
        adjusts_value = quantity < 0
        reversal_item = SalesItem(
            order_id=reversal.id,
            part_id=item.part_id,
            quantity=item.quantity,
            sale_price=item.sale_price,
            amount=item.amount,
            cost_amount=item.cost_amount,
            remark="红冲",
            **new_row_kwargs(db),
        )
        db.add(reversal_item)
        db.flush()
        append_ledger_entry(
            db,
            part_id=item.part_id,
            change_type="sale_return" if quantity > 0 else "sale",
            quantity=quantity,
            source_type=(
                "sales_item_reversal_value"
                if adjusts_value
                else "sales_item_reversal"
            ),
            source_id=reversal_item.id,
            unit_cost=unit_cost,
            occurred_at=occurred_at,
            remark="红冲",
            adjust_avg_on_out=adjusts_value,
        )

    order.reversed_by = reversal.id
    bump_version(db, order)
    _unlink_sales_reversal_parent(db, order)
    add_history(
        db,
        action="reverse",
        entity_type="sales_order",
        entity_id=order.id,
        entity_label=order.order_no,
        summary=f"红冲销售单「{order.order_no}」，生成 {reversal.order_no}",
        after={"order_no": order.order_no, "reversed_by": reversal.id},
    )
    db.commit()
    db.refresh(order)
    return order
