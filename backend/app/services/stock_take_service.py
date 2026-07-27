"""库存盘点：冻结账面数、记录实盘数并按期间变动过账。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessAppError
from app.db.write_helpers import bump_version, new_row_kwargs
from app.models.master_data import Part
from app.models.stock import StockLedger, StockSnapshot, StockTake, StockTakeItem
from app.models.sync import ChangeSeq
from app.services.order_no_service import generate_order_no
from app.services.stock_service import append_ledger_entry


def create_stock_take(
    db: Session,
    *,
    scope_type: str = "all",
    scope_value: str | None = None,
    remark: str | None = None,
) -> StockTake:
    take = StockTake(
        take_no=generate_order_no(db, "PD"),
        scope_type=scope_type,
        scope_value=scope_value,
        status="draft",
        started_at=datetime.now(UTC).isoformat(),
        remark=remark,
        **new_row_kwargs(db),
    )
    db.add(take)
    db.flush()

    stmt = (
        select(Part, StockSnapshot)
        .outerjoin(StockSnapshot, StockSnapshot.part_id == Part.id)
        .where(Part.is_deleted == 0, Part.is_active == 1)
    )
    if scope_type == "category" and scope_value:
        stmt = stmt.where(Part.category_id == scope_value)
    elif scope_type == "location" and scope_value:
        stmt = stmt.where(Part.location == scope_value)
    elif scope_type != "all":
        raise BusinessAppError("不支持的盘点范围", code="BUSINESS_STOCK_TAKE_SCOPE_INVALID")

    change_seq = db.get(ChangeSeq, 1)
    book_rev = change_seq.current_rev if change_seq else 0
    for part, snapshot in db.execute(stmt):
        db.add(
            StockTakeItem(
                take_id=take.id,
                part_id=part.id,
                book_quantity=Decimal(str(snapshot.quantity)) if snapshot else Decimal("0"),
                book_rev=book_rev,
                actual_quantity=None,
                diff_quantity=None,
                diff_amount=None,
                **new_row_kwargs(db),
            )
        )
    db.commit()
    db.refresh(take)
    return take


def get_stock_take(db: Session, take_id: str) -> StockTake:
    take = db.get(StockTake, take_id)
    if take is None or take.is_deleted:
        raise BusinessAppError("盘点单不存在", code="BUSINESS_NOT_FOUND")
    return take


def list_stock_takes(db: Session, limit: int = 100) -> list[StockTake]:
    stmt = (
        select(StockTake)
        .where(StockTake.is_deleted == 0)
        .order_by(StockTake.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def list_stock_take_items(db: Session, take_id: str) -> list[StockTakeItem]:
    stmt = select(StockTakeItem).where(
        StockTakeItem.take_id == take_id,
        StockTakeItem.is_deleted == 0,
    )
    return list(db.execute(stmt).scalars())


def update_actual_quantities(
    db: Session,
    take_id: str,
    quantities: list[dict],
) -> StockTake:
    take = get_stock_take(db, take_id)
    if take.status != "draft":
        raise BusinessAppError("盘点单已过账，不能修改", code="BUSINESS_STOCK_TAKE_POSTED")
    rows = {row.part_id: row for row in list_stock_take_items(db, take.id)}
    for value in quantities:
        row = rows.get(value["part_id"])
        if row is None:
            raise BusinessAppError("零件不在本次盘点范围", code="BUSINESS_STOCK_TAKE_ITEM_INVALID")
        actual = Decimal(str(value["actual_quantity"]))
        if actual < 0:
            raise BusinessAppError("实盘数量不能为负", code="BUSINESS_INVALID_QUANTITY")
        row.actual_quantity = actual
        bump_version(db, row)
    db.commit()
    db.refresh(take)
    return take


def post_stock_take(db: Session, take_id: str) -> StockTake:
    take = get_stock_take(db, take_id)
    if take.status != "draft":
        raise BusinessAppError("盘点单已过账", code="BUSINESS_STOCK_TAKE_POSTED")
    items = list_stock_take_items(db, take.id)
    if any(item.actual_quantity is None for item in items):
        raise BusinessAppError("仍有零件未填写实盘数量", code="BUSINESS_STOCK_TAKE_INCOMPLETE")

    occurred_at = datetime.now(UTC).isoformat()
    for item in items:
        period_change = db.execute(
            select(func.coalesce(func.sum(StockLedger.quantity), 0)).where(
                StockLedger.part_id == item.part_id,
                StockLedger.rev > item.book_rev,
            )
        ).scalar_one()
        current_book = Decimal(str(item.book_quantity)) + Decimal(str(period_change))
        diff = Decimal(str(item.actual_quantity)) - current_book
        snapshot = db.get(StockSnapshot, item.part_id)
        avg_cost = snapshot.avg_cost if snapshot else 0
        item.diff_quantity = diff
        item.diff_amount = int(diff * avg_cost)
        bump_version(db, item)
        if diff:
            append_ledger_entry(
                db,
                part_id=item.part_id,
                change_type="adjust",
                quantity=diff,
                source_type="stock_take_item",
                source_id=item.id,
                unit_cost=avg_cost,
                occurred_at=occurred_at,
                remark=f"盘点单 {take.take_no}",
            )
    take.status = "posted"
    take.posted_at = occurred_at
    bump_version(db, take)
    db.commit()
    db.refresh(take)
    return take
