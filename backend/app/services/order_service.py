"""采购单/销售单业务逻辑：单事务写入主表+明细+流水+快照，红冲/当日撤销（§5.2-5.4, §12）。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError
from app.core.time import business_date_str
from app.db.write_helpers import DEFAULT_DEVICE_ID, new_row_kwargs
from app.models.master_data import Part
from app.models.orders import PurchaseItem, PurchaseOrder, SalesItem, SalesOrder
from app.services.order_no_service import generate_order_no
from app.services.settings_service import get_allow_negative_stock
from app.services.stock_service import append_ledger_entry, check_available_stock

_TODAY = business_date_str


def _line_amount(quantity: Decimal, unit_price: int) -> int:
    """数量（最多三位小数）乘以分单价，按统一规则四舍五入到分。"""
    return int((quantity * unit_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _get_active_part(db: Session, part_id: str) -> Part:
    part = db.get(Part, part_id)
    if part is None or part.is_deleted or not part.is_active:
        raise BusinessAppError("零件不存在或已停用", code="BUSINESS_PART_UNAVAILABLE")
    return part


def create_purchase_order(
    db: Session,
    *,
    supplier_id: str | None,
    items: list[dict],
    remark: str | None,
) -> PurchaseOrder:
    order_no = generate_order_no(db, "CG")
    order_kwargs = new_row_kwargs(db)
    order = PurchaseOrder(
        order_no=order_no,
        supplier_id=supplier_id,
        order_date=_TODAY(),
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
        )
        part.purchase_price = price
        total_amount += amount

    order.total_amount = total_amount
    db.commit()
    db.refresh(order)
    return order


def create_sales_order(
    db: Session,
    *,
    customer_id: str | None,
    customer_name: str | None,
    items: list[dict],
    remark: str | None,
) -> SalesOrder:
    order_no = generate_order_no(db, "XS")
    allow_negative = get_allow_negative_stock(db)

    order_kwargs = new_row_kwargs(db)
    order = SalesOrder(
        order_no=order_no,
        customer_id=customer_id,
        customer_name=customer_name,
        order_date=_TODAY(),
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
        )
        if ledger is not None:
            sales_item.cost_amount = _line_amount(quantity, ledger.unit_cost)
        part.sale_price = price
        total_amount += amount

    order.total_amount = total_amount
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
    source = get_purchase_order(db, source_order_id)
    if source.order_type != "purchase" or source.reversed_by is not None:
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
            unit_cost=row.purchase_price,
            occurred_at=occurred_at,
        )
        total_amount += amount

    return_order.total_amount = total_amount
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
    source = get_sales_order(db, source_order_id)
    if source.order_type != "sale" or source.reversed_by is not None:
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
        original_unit_cost = int(
            (Decimal(original.cost_amount) / Decimal(str(original.quantity))).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
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
    db.commit()
    db.refresh(return_order)
    return return_order


def _is_same_day_unsynced(order: PurchaseOrder | SalesOrder) -> bool:
    """当日且未同步（device_id 仍是本机默认值，未被同步流程改写）才可直接撤销（§5.4）。"""
    order_day = order.order_date
    return order_day == _TODAY() and order.device_id == DEFAULT_DEVICE_ID


def void_purchase_order(db: Session, order_id: str) -> PurchaseOrder:
    order = db.get(PurchaseOrder, order_id)
    if order is None or order.is_deleted:
        raise BusinessAppError("采购单不存在", code="BUSINESS_NOT_FOUND")
    if order.reversed_by is not None:
        raise BusinessAppError("该单据已被红冲，不能重复作废", code="BUSINESS_ALREADY_REVERSED")

    if _is_same_day_unsynced(order):
        return _delete_purchase_order_and_rollback(db, order)
    return _reverse_purchase_order(db, order)


def _delete_purchase_order_and_rollback(db: Session, order: PurchaseOrder) -> PurchaseOrder:
    items = db.query(PurchaseItem).filter(PurchaseItem.order_id == order.id).all()
    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
        append_ledger_entry(
            db,
            part_id=item.part_id,
            change_type="purchase_return",
            quantity=-Decimal(str(item.quantity)),
            source_type="purchase_item_void",
            source_id=item.id,
            unit_cost=item.purchase_price,
            occurred_at=occurred_at,
            remark="同日撤销回滚",
        )
        item.is_deleted = 1
    order.is_deleted = 1
    db.commit()
    db.refresh(order)
    return order


def _reverse_purchase_order(db: Session, order: PurchaseOrder) -> PurchaseOrder:
    """生成一张 order_type=purchase_return 的红冲单，方向相反、原单标记 reversed_by（§5.4）。"""
    items = db.query(PurchaseItem).filter(PurchaseItem.order_id == order.id).all()

    reversal_no = generate_order_no(db, "CG")
    reversal = PurchaseOrder(
        order_no=reversal_no,
        supplier_id=order.supplier_id,
        order_date=_TODAY(),
        total_amount=order.total_amount,
        paid_amount=0,
        order_type="purchase_return",
        source_order_id=order.id,
        remark=f"红冲原单 {order.order_no}",
        **new_row_kwargs(db),
    )
    db.add(reversal)
    db.flush()

    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
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
            change_type="purchase_return",
            quantity=-Decimal(str(item.quantity)),
            source_type="purchase_item",
            source_id=reversal_item.id,
            unit_cost=item.purchase_price,
            occurred_at=occurred_at,
            remark="红冲",
        )

    order.reversed_by = reversal.id
    db.commit()
    db.refresh(order)
    return order


def void_sales_order(db: Session, order_id: str) -> SalesOrder:
    order = db.get(SalesOrder, order_id)
    if order is None or order.is_deleted:
        raise BusinessAppError("销售单不存在", code="BUSINESS_NOT_FOUND")
    if order.reversed_by is not None:
        raise BusinessAppError("该单据已被红冲，不能重复作废", code="BUSINESS_ALREADY_REVERSED")

    if _is_same_day_unsynced(order):
        return _delete_sales_order_and_rollback(db, order)
    return _reverse_sales_order(db, order)


def _delete_sales_order_and_rollback(db: Session, order: SalesOrder) -> SalesOrder:
    items = db.query(SalesItem).filter(SalesItem.order_id == order.id).all()
    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
        append_ledger_entry(
            db,
            part_id=item.part_id,
            change_type="sale_return",
            quantity=Decimal(str(item.quantity)),
            source_type="sales_item_void",
            source_id=item.id,
            occurred_at=occurred_at,
            remark="同日撤销回滚",
        )
        item.is_deleted = 1
    order.is_deleted = 1
    db.commit()
    db.refresh(order)
    return order


def _reverse_sales_order(db: Session, order: SalesOrder) -> SalesOrder:
    """生成一张 order_type=sale_return 的红冲单，方向相反、原单标记 reversed_by（§5.4）。"""
    items = db.query(SalesItem).filter(SalesItem.order_id == order.id).all()

    reversal_no = generate_order_no(db, "XS")
    reversal = SalesOrder(
        order_no=reversal_no,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        order_date=_TODAY(),
        total_amount=order.total_amount,
        received_amount=0,
        order_type="sale_return",
        source_order_id=order.id,
        remark=f"红冲原单 {order.order_no}",
        **new_row_kwargs(db),
    )
    db.add(reversal)
    db.flush()

    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
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
            change_type="sale_return",
            quantity=Decimal(str(item.quantity)),
            source_type="sales_item",
            source_id=reversal_item.id,
            unit_cost=(
                round(item.cost_amount / float(item.quantity)) if float(item.quantity) else 0
            ),
            occurred_at=occurred_at,
            remark="红冲",
        )

    order.reversed_by = reversal.id
    db.commit()
    db.refresh(order)
    return order
