from __future__ import annotations

import importlib.util
import sqlite3
import sys
from contextlib import closing
from decimal import Decimal
from pathlib import Path

from app.services.part_service import create_part
from app.services.stock_service import append_ledger_entry


def _load_reconcile_module():
    path = Path(__file__).resolve().parents[3] / "scripts" / "reconcile.py"
    spec = importlib.util.spec_from_file_location("autostock_reconcile", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _create_part_with_stock(db_session):
    part = create_part(
        db_session,
        part_number="REC-001",
        oe_number=None,
        name="对账测试零件",
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
    append_ledger_entry(
        db_session,
        part_id=part.id,
        change_type="opening",
        quantity=Decimal("12.5"),
        source_type="opening",
        source_id=part.id,
        unit_cost=500,
    )
    db_session.commit()
    return part


def test_reconcile_passes_for_consistent_database(app_client, db_path):
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        _create_part_with_stock(db)

    module = _load_reconcile_module()
    total, count, mismatches = module.reconcile_database(db_path)
    assert total == 1
    assert count == 0
    assert mismatches == []


def test_reconcile_reports_intentional_mismatch(app_client, db_path):
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        part = _create_part_with_stock(db)

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            "UPDATE stock_snapshot SET quantity = quantity + 2 WHERE part_id = ?",
            (part.id,),
        )
        connection.commit()

    module = _load_reconcile_module()
    total, count, mismatches = module.reconcile_database(db_path)
    assert total == 1
    assert count == 1
    assert mismatches[0].part_id == part.id
    assert mismatches[0].difference == Decimal("2.000")


def test_order_ledger_semantic_audit_detects_wrong_void_direction(app_client, db_path):
    part = app_client.post(
        "/api/parts",
        json={
            "part_number": "REC-DIRECTION",
            "name": "方向对账零件",
            "unit": "件",
            "purchase_price": 500,
            "sale_price": 800,
        },
    ).json()["data"]
    purchase = app_client.post(
        "/api/orders/purchases",
        json={"items": [{"part_id": part["id"], "quantity": 5, "purchase_price": 500}]},
    ).json()["data"]
    purchase_return = app_client.post(
        f"/api/orders/purchases/{purchase['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 2}]},
    ).json()["data"]
    assert app_client.post(
        f"/api/orders/purchases/{purchase_return['id']}/void"
    ).status_code == 200

    module = _load_reconcile_module()
    assert module.audit_order_ledger_directions(db_path) == []

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            UPDATE stock_ledger
            SET quantity = -ABS(quantity)
            WHERE source_type = 'purchase_item_void'
            """
        )
        connection.commit()

    mismatches = module.audit_order_ledger_directions(db_path)
    assert len(mismatches) == 1
    assert mismatches[0].order_type == "purchase_return"
    assert mismatches[0].actual_quantity == Decimal("-2")
    assert mismatches[0].expected_quantity == Decimal("2")
