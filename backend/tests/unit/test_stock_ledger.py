from decimal import Decimal

import pytest

from app.services.part_service import create_part
from app.services.stock_service import append_ledger_entry, get_snapshot, recalculate_all


@pytest.fixture()
def db_session(app_client):  # noqa: ARG001
    """借用 app_client fixture 完成迁移与引擎切换，返回可直接用的 Session。"""
    from app.db.session import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


def _make_part(db, part_number="P900"):
    return create_part(
        db,
        part_number=part_number,
        oe_number=None,
        name="测试件",
        spec=None,
        brand_id=None,
        category_id=None,
        supplier_id=None,
        unit="个",
        purchase_price=0,
        sale_price=0,
        min_stock=0,
        max_stock=None,
        location=None,
        vehicle_models=None,
        remark=None,
    )


def test_append_in_then_out_updates_snapshot(db_session):
    part = _make_part(db_session)

    append_ledger_entry(
        db_session,
        part_id=part.id,
        change_type="purchase",
        quantity=Decimal("10"),
        source_type="purchase_item",
        source_id="src-1",
        unit_cost=500,
    )
    db_session.commit()
    snap = get_snapshot(db_session, part.id)
    assert snap.quantity == Decimal("10")
    assert snap.avg_cost == 500

    append_ledger_entry(
        db_session,
        part_id=part.id,
        change_type="purchase",
        quantity=Decimal("10"),
        source_type="purchase_item",
        source_id="src-2",
        unit_cost=700,
    )
    db_session.commit()
    snap = get_snapshot(db_session, part.id)
    assert snap.quantity == Decimal("20")
    assert snap.avg_cost == 600

    append_ledger_entry(
        db_session,
        part_id=part.id,
        change_type="sale",
        quantity=Decimal("-5"),
        source_type="sales_item",
        source_id="src-3",
    )
    db_session.commit()
    snap = get_snapshot(db_session, part.id)
    assert snap.quantity == Decimal("15")
    assert snap.avg_cost == 600  # 出库不改均价


def test_duplicate_source_is_idempotent(db_session):
    part = _make_part(db_session, part_number="P901")

    first = append_ledger_entry(
        db_session,
        part_id=part.id,
        change_type="purchase",
        quantity=Decimal("10"),
        source_type="purchase_item",
        source_id="dup-1",
        unit_cost=500,
    )
    db_session.commit()
    assert first is not None

    second = append_ledger_entry(
        db_session,
        part_id=part.id,
        change_type="purchase",
        quantity=Decimal("10"),
        source_type="purchase_item",
        source_id="dup-1",
        unit_cost=500,
    )
    db_session.commit()
    assert second is None

    snap = get_snapshot(db_session, part.id)
    assert snap.quantity == Decimal("10")  # 没有被重复记账


def test_recalculate_all_matches_incremental_result(db_session):
    part = _make_part(db_session, part_number="P902")

    append_ledger_entry(
        db_session,
        part_id=part.id,
        change_type="purchase",
        quantity=Decimal("10"),
        source_type="purchase_item",
        source_id="r-1",
        unit_cost=500,
        occurred_at="2026-01-01T00:00:00+00:00",
    )
    append_ledger_entry(
        db_session,
        part_id=part.id,
        change_type="purchase",
        quantity=Decimal("10"),
        source_type="purchase_item",
        source_id="r-2",
        unit_cost=700,
        occurred_at="2026-01-02T00:00:00+00:00",
    )
    append_ledger_entry(
        db_session,
        part_id=part.id,
        change_type="sale",
        quantity=Decimal("-8"),
        source_type="sales_item",
        source_id="r-3",
        occurred_at="2026-01-03T00:00:00+00:00",
    )
    db_session.commit()
    before = get_snapshot(db_session, part.id)
    before_quantity, before_avg_cost = before.quantity, before.avg_cost

    recalculate_all(db_session)

    after = get_snapshot(db_session, part.id)
    assert after.quantity == before_quantity
    assert after.avg_cost == before_avg_cost


def test_rejects_unknown_change_type(db_session):
    part = _make_part(db_session, part_number="P903")
    with pytest.raises(ValueError):
        append_ledger_entry(
            db_session,
            part_id=part.id,
            change_type="unknown",
            quantity=Decimal("1"),
            source_type="x",
            source_id="y",
        )
