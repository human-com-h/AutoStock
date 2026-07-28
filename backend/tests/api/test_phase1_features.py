from io import BytesIO

from openpyxl import load_workbook


def _part(client, number="FEATURE-001"):
    response = client.post(
        "/api/parts",
        json={
            "part_number": number,
            "name": "阶段一测试零件",
            "unit": "个",
            "purchase_price": 500,
            "sale_price": 800,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_settings_apply_to_new_sales_orders(app_client):
    current = app_client.get("/api/settings")
    assert current.status_code == 200
    updated = app_client.put(
        "/api/settings",
        json={
            "shop_name": "测试汽配店",
            "default_unit": "件",
            "allow_negative_stock": False,
            "stale_days": 90,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["shop_name"] == "测试汽配店"

    part = _part(app_client)
    blocked = app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": part["id"], "quantity": 1, "sale_price": 800}]},
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "BUSINESS_STOCK_INSUFFICIENT"


def test_dashboard_and_rankings_use_real_orders(app_client):
    part = _part(app_client)
    app_client.post(
        "/api/orders/purchases",
        json={
            "items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]
        },
    )
    app_client.post(
        "/api/orders/sales",
        json={
            "customer_name": "测试客户",
            "items": [{"part_id": part["id"], "quantity": 2, "sale_price": 800}],
        },
    )
    dashboard = app_client.get("/api/reports/dashboard").json()["data"]
    assert dashboard["today_sales"] == 1600
    assert dashboard["today_profit"] == 600
    assert dashboard["inventory_amount"] == 4000

    rankings = app_client.get("/api/reports/rankings").json()["data"]
    assert rankings["parts"][0]["part_id"] == part["id"]
    assert rankings["parts"][0]["sales"] == 1600
    assert rankings["customers"][0] == {"name": "测试客户", "sales": 1600}


def test_reconcile_endpoint_detects_snapshot_difference(app_client):
    part = _part(app_client)
    app_client.post(
        "/api/orders/purchases",
        json={
            "items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]
        },
    )
    clean = app_client.get("/api/stock/reconcile").json()["data"]
    assert clean == {
        "ok": True,
        "checked_count": 1,
        "mismatch_count": 0,
        "differences": [],
    }

    from app.db.session import SessionLocal
    from app.models.stock import StockSnapshot

    with SessionLocal() as db:
        snapshot = db.get(StockSnapshot, part["id"])
        snapshot.quantity = 9
        db.commit()

    mismatch = app_client.get("/api/stock/reconcile").json()["data"]
    assert mismatch["ok"] is False
    assert mismatch["mismatch_count"] == 1
    assert mismatch["differences"][0]["difference"] == -1


def test_excel_template_import_and_exports(app_client):
    template = app_client.get("/api/excel/template/parts")
    assert template.status_code == 200
    workbook = load_workbook(BytesIO(template.content))
    assert workbook.active["A1"].value == "零件编号"

    imported = app_client.post(
        "/api/excel/import/parts",
        files={
            "file": (
                "parts.xlsx",
                template.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert imported.status_code == 200
    assert imported.json()["data"]["imported"] == 1
    inventory = app_client.get("/api/stock").json()["data"]
    assert inventory[0]["quantity"] == 10

    parts_export = app_client.get("/api/excel/export/parts")
    inventory_export = app_client.get("/api/excel/export/inventory")
    assert parts_export.content[:2] == b"PK"
    assert inventory_export.content[:2] == b"PK"


def test_order_ledger_and_summary_exports(app_client):
    part = _part(app_client)
    app_client.post(
        "/api/orders/purchases",
        json={"items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]},
    )
    app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": part["id"], "quantity": 2, "sale_price": 800}]},
    )
    exports = {
        "purchase": app_client.get("/api/excel/export/orders/purchases"),
        "sales": app_client.get("/api/excel/export/orders/sales"),
        "ledger": app_client.get("/api/excel/export/ledger"),
        "summary": app_client.get("/api/excel/export/summary"),
    }
    assert all(response.status_code == 200 for response in exports.values())
    assert all(response.content[:2] == b"PK" for response in exports.values())

    summary = load_workbook(BytesIO(exports["summary"].content)).active
    assert summary["A2"].value == part["part_number"]
    assert summary["D2"].value == 10
    assert summary["F2"].value == 2
    assert summary["I2"].value == 8


def test_backup_create_list_and_restore_roundtrip(app_client):
    first = _part(app_client, "BACKUP-001")
    created = app_client.post("/api/backups")
    assert created.status_code == 200
    name = created.json()["data"]["name"]
    assert name in {row["name"] for row in app_client.get("/api/backups").json()["data"]}

    _part(app_client, "BACKUP-002")
    from app.services import backup_service

    backup_service.restore_backup(name)

    from app.db.session import SessionLocal
    from app.models.master_data import Part

    with SessionLocal() as db:
        numbers = {row.part_number for row in db.query(Part).all()}
    assert first["part_number"] in numbers
    assert "BACKUP-002" not in numbers
