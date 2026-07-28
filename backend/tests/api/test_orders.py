from decimal import Decimal


def _create_part(client, number="ORD-001"):
    response = client.post(
        "/api/parts",
        json={
            "part_number": number,
            "name": "订单测试零件",
            "unit": "个",
            "purchase_price": 500,
            "sale_price": 800,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def _snapshot(client, part_id):
    return Decimal(str(client.get(f"/api/stock/{part_id}").json()["data"]["quantity"]))


def test_purchase_and_sale_api_complete_inventory_and_cost_flow(app_client):
    part = _create_part(app_client)
    purchase = app_client.post(
        "/api/orders/purchases",
        json={
            "items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]
        },
    )
    assert purchase.status_code == 200
    assert purchase.json()["data"]["total_amount"] == 5000
    assert _snapshot(app_client, part["id"]) == Decimal("10")

    sale = app_client.post(
        "/api/orders/sales",
        json={
            "customer_name": "散客",
            "items": [{"part_id": part["id"], "quantity": 3, "sale_price": 800}],
        },
    )
    assert sale.status_code == 200
    sale_data = sale.json()["data"]
    assert sale_data["total_amount"] == 2400
    assert sale_data["items"][0]["cost_amount"] == 1500
    assert _snapshot(app_client, part["id"]) == Decimal("7")

    assert len(app_client.get("/api/orders/purchases").json()["data"]) == 1
    assert len(app_client.get("/api/orders/sales").json()["data"]) == 1


def test_sale_rejects_negative_stock_and_rolls_back_entire_order(app_client):
    part = _create_part(app_client)
    from app.db.session import SessionLocal
    from app.services.settings_service import set_setting

    with SessionLocal() as db:
        set_setting(db, "allow_negative_stock", "0")

    response = app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": part["id"], "quantity": 1, "sale_price": 800}]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BUSINESS_STOCK_INSUFFICIENT"
    assert app_client.get("/api/orders/sales").json()["data"] == []


def test_purchase_and_sale_returns_are_linked_and_quantity_limited(app_client):
    part = _create_part(app_client)
    purchase = app_client.post(
        "/api/orders/purchases",
        json={
            "items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]
        },
    ).json()["data"]
    sale = app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": part["id"], "quantity": 4, "sale_price": 800}]},
    ).json()["data"]

    sale_return = app_client.post(
        f"/api/orders/sales/{sale['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 2}]},
    )
    assert sale_return.status_code == 200
    assert sale_return.json()["data"]["source_order_id"] == sale["id"]
    assert sale_return.json()["data"]["order_type"] == "sale_return"
    assert _snapshot(app_client, part["id"]) == Decimal("8")

    purchase_return = app_client.post(
        f"/api/orders/purchases/{purchase['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 3}]},
    )
    assert purchase_return.status_code == 200
    assert purchase_return.json()["data"]["source_order_id"] == purchase["id"]
    assert _snapshot(app_client, part["id"]) == Decimal("5")

    too_many = app_client.post(
        f"/api/orders/purchases/{purchase['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 8}]},
    )
    assert too_many.status_code == 400
    assert too_many.json()["error"]["code"] == "BUSINESS_RETURN_QUANTITY_INVALID"
    assert _snapshot(app_client, part["id"]) == Decimal("5")


def test_same_day_void_uses_compensating_ledger_and_restores_stock(app_client):
    part = _create_part(app_client)
    purchase = app_client.post(
        "/api/orders/purchases",
        json={
            "items": [{"part_id": part["id"], "quantity": 6, "purchase_price": 500}]
        },
    ).json()["data"]
    sale = app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": part["id"], "quantity": 2, "sale_price": 800}]},
    ).json()["data"]

    assert app_client.post(f"/api/orders/sales/{sale['id']}/void").status_code == 200
    assert _snapshot(app_client, part["id"]) == Decimal("6")
    assert app_client.post(f"/api/orders/purchases/{purchase['id']}/void").status_code == 200
    assert _snapshot(app_client, part["id"]) == Decimal("0")


def test_historical_order_void_generates_reversal_order(app_client):
    part = _create_part(app_client)
    purchase = app_client.post(
        "/api/orders/purchases",
        json={
            "items": [{"part_id": part["id"], "quantity": 5, "purchase_price": 500}]
        },
    ).json()["data"]

    from app.db.session import SessionLocal
    from app.models.orders import PurchaseOrder

    with SessionLocal() as db:
        row = db.get(PurchaseOrder, purchase["id"])
        row.order_date = "2026-01-01"
        db.commit()

    response = app_client.post(f"/api/orders/purchases/{purchase['id']}/void")
    assert response.status_code == 200
    original = app_client.get(f"/api/orders/purchases/{purchase['id']}").json()["data"]
    assert original["reversed_by"] is not None
    reversals = [
        row
        for row in app_client.get("/api/orders/purchases").json()["data"]
        if row["source_order_id"] == purchase["id"]
    ]
    assert len(reversals) == 1
    assert reversals[0]["order_type"] == "purchase_return"
    assert _snapshot(app_client, part["id"]) == Decimal("0")
