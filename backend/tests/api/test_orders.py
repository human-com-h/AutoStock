from datetime import timedelta
from decimal import Decimal

from app.core.time import business_date_str, business_now


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
        json={"items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]},
    )
    assert purchase.status_code == 200
    assert purchase.json()["data"]["total_amount"] == 5000
    assert purchase.json()["data"]["order_date"] == business_date_str()
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


def test_backfilled_orders_use_business_date_and_post_inventory_now(app_client):
    part = _create_part(app_client, "BACKFILL-ORDER")
    historical_date = (business_now().date() - timedelta(days=7)).isoformat()

    purchase = app_client.post(
        "/api/orders/purchases",
        json={
            "order_date": historical_date,
            "items": [{"part_id": part["id"], "quantity": 8, "purchase_price": 500}],
        },
    )
    assert purchase.status_code == 200
    assert purchase.json()["data"]["order_date"] == historical_date

    sale = app_client.post(
        "/api/orders/sales",
        json={
            "order_date": historical_date,
            "items": [{"part_id": part["id"], "quantity": 3, "sale_price": 800}],
        },
    )
    assert sale.status_code == 200
    assert sale.json()["data"]["order_date"] == historical_date
    assert _snapshot(app_client, part["id"]) == Decimal("5")

    history = app_client.get(f"/api/stock/{part['id']}/history").json()["data"]
    assert history["entries"][0]["remark"] == (
        f"补录历史单据，业务日期 {historical_date}"
    )
    assert history["entries"][1]["remark"] == (
        f"补录历史单据，业务日期 {historical_date}"
    )


def test_order_date_cannot_be_in_the_future(app_client):
    part = _create_part(app_client, "FUTURE-ORDER")
    future_date = (business_now().date() + timedelta(days=1)).isoformat()

    purchase = app_client.post(
        "/api/orders/purchases",
        json={
            "order_date": future_date,
            "items": [{"part_id": part["id"], "quantity": 1, "purchase_price": 500}],
        },
    )
    sale = app_client.post(
        "/api/orders/sales",
        json={
            "order_date": future_date,
            "items": [{"part_id": part["id"], "quantity": 1, "sale_price": 800}],
        },
    )
    assert purchase.status_code == 422
    assert sale.status_code == 422
    assert app_client.get("/api/orders/purchases").json()["data"] == []
    assert app_client.get("/api/orders/sales").json()["data"] == []
    history = app_client.get(f"/api/stock/{part['id']}/history").json()["data"]
    assert history["current_quantity"] == 0
    assert history["total"] == 0


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
        json={"items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]},
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
        json={"items": [{"part_id": part["id"], "quantity": 6, "purchase_price": 500}]},
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
        json={"items": [{"part_id": part["id"], "quantity": 5, "purchase_price": 500}]},
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


def test_same_day_order_already_pulled_by_mobile_uses_reversal(app_client):
    part = _create_part(app_client, "SYNCED-VOID")
    purchase = app_client.post(
        "/api/orders/purchases",
        json={"items": [{"part_id": part["id"], "quantity": 5, "purchase_price": 500}]},
    ).json()["data"]
    code = app_client.post("/api/pairing/code").json()["data"]["code"]
    device = app_client.post(
        "/api/auth/pair",
        json={"code": code, "device_name": "撤销边界测试手机"},
    ).json()["data"]
    headers = {"Authorization": f"Bearer {device['device_token']}"}
    pulled = app_client.get(
        "/api/sync/pull",
        params={"since_rev": device["server_rev"], "limit": 500},
        headers=headers,
    )
    assert pulled.status_code == 200

    assert app_client.post(f"/api/orders/purchases/{purchase['id']}/void").status_code == 200
    original = app_client.get(f"/api/orders/purchases/{purchase['id']}").json()["data"]
    assert original["reversed_by"] is not None
    assert _snapshot(app_client, part["id"]) == Decimal("0")


def test_voiding_return_orders_restores_inventory_and_average_cost(app_client):
    part = _create_part(app_client, "RETURN-VOID")
    purchase = app_client.post(
        "/api/orders/purchases",
        json={"items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]},
    ).json()["data"]
    sale = app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": part["id"], "quantity": 4, "sale_price": 800}]},
    ).json()["data"]

    purchase_return = app_client.post(
        f"/api/orders/purchases/{purchase['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 3}]},
    ).json()["data"]
    assert _snapshot(app_client, part["id"]) == Decimal("3")
    assert app_client.post(
        f"/api/orders/purchases/{purchase_return['id']}/void"
    ).status_code == 200
    assert _snapshot(app_client, part["id"]) == Decimal("6")

    sale_return = app_client.post(
        f"/api/orders/sales/{sale['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 2}]},
    ).json()["data"]
    assert _snapshot(app_client, part["id"]) == Decimal("8")
    assert app_client.post(f"/api/orders/sales/{sale_return['id']}/void").status_code == 200
    snapshot = app_client.get(f"/api/stock/{part['id']}").json()["data"]
    assert Decimal(str(snapshot["quantity"])) == Decimal("6")
    assert snapshot["avg_cost"] == 500


def test_historical_return_reversal_releases_returnable_quantity(app_client):
    part = _create_part(app_client, "RETURN-REVERSE")
    purchase = app_client.post(
        "/api/orders/purchases",
        json={"items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]},
    ).json()["data"]
    purchase_return = app_client.post(
        f"/api/orders/purchases/{purchase['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 3}]},
    ).json()["data"]

    from app.db.session import SessionLocal
    from app.models.orders import PurchaseOrder

    with SessionLocal() as db:
        row = db.get(PurchaseOrder, purchase_return["id"])
        row.order_date = "2026-01-01"
        db.commit()

    assert app_client.post(
        f"/api/orders/purchases/{purchase_return['id']}/void"
    ).status_code == 200
    reversed_return = app_client.get(
        f"/api/orders/purchases/{purchase_return['id']}"
    ).json()["data"]
    assert reversed_return["reversed_by"] is not None
    correction = app_client.get(
        f"/api/orders/purchases/{reversed_return['reversed_by']}"
    ).json()["data"]
    assert correction["order_type"] == "purchase"
    assert _snapshot(app_client, part["id"]) == Decimal("10")

    replacement = app_client.post(
        f"/api/orders/purchases/{purchase['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 10}]},
    )
    assert replacement.status_code == 200
    assert _snapshot(app_client, part["id"]) == Decimal("0")


def test_original_order_with_active_return_cannot_be_voided(app_client):
    part = _create_part(app_client, "RETURN-PARENT")
    purchase = app_client.post(
        "/api/orders/purchases",
        json={"items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]},
    ).json()["data"]
    sale = app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": part["id"], "quantity": 4, "sale_price": 800}]},
    ).json()["data"]
    app_client.post(
        f"/api/orders/purchases/{purchase['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 1}]},
    )
    app_client.post(
        f"/api/orders/sales/{sale['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 1}]},
    )

    for kind, order in (("purchases", purchase), ("sales", sale)):
        response = app_client.post(f"/api/orders/{kind}/{order['id']}/void")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BUSINESS_ORDER_HAS_ACTIVE_RETURNS"
    assert _snapshot(app_client, part["id"]) == Decimal("6")


def test_outbound_returns_and_reversals_respect_negative_stock_setting(app_client):
    part = _create_part(app_client, "RETURN-STOCK-GUARD")
    from app.db.session import SessionLocal
    from app.services.settings_service import set_setting

    with SessionLocal() as db:
        set_setting(db, "allow_negative_stock", "0")

    purchase = app_client.post(
        "/api/orders/purchases",
        json={"items": [{"part_id": part["id"], "quantity": 5, "purchase_price": 500}]},
    ).json()["data"]
    sale = app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": part["id"], "quantity": 5, "sale_price": 800}]},
    )
    assert sale.status_code == 200

    purchase_return = app_client.post(
        f"/api/orders/purchases/{purchase['id']}/returns",
        json={"items": [{"part_id": part["id"], "quantity": 1}]},
    )
    assert purchase_return.status_code == 400
    assert purchase_return.json()["error"]["code"] == "BUSINESS_STOCK_INSUFFICIENT"

    void_purchase = app_client.post(f"/api/orders/purchases/{purchase['id']}/void")
    assert void_purchase.status_code == 400
    assert void_purchase.json()["error"]["code"] == "BUSINESS_STOCK_INSUFFICIENT"
    assert _snapshot(app_client, part["id"]) == Decimal("0")


def test_order_input_rejects_duplicate_parts_and_excess_precision(app_client):
    part = _create_part(app_client, "ORDER-VALIDATION")
    duplicate = app_client.post(
        "/api/orders/purchases",
        json={
            "items": [
                {"part_id": part["id"], "quantity": 1, "purchase_price": 500},
                {"part_id": part["id"], "quantity": 2, "purchase_price": 500},
            ]
        },
    )
    assert duplicate.status_code == 422

    excessive_precision = app_client.post(
        "/api/orders/purchases",
        json={
            "items": [
                {"part_id": part["id"], "quantity": 0.0001, "purchase_price": 500}
            ]
        },
    )
    assert excessive_precision.status_code == 422
    assert app_client.get("/api/orders/purchases").json()["data"] == []


def test_order_lists_can_be_filtered_by_supplier_and_customer(app_client):
    part = _create_part(app_client, "PARTNER-001")
    supplier_a = app_client.post("/api/suppliers", json={"name": "甲供应商"}).json()["data"]
    supplier_b = app_client.post("/api/suppliers", json={"name": "乙供应商"}).json()["data"]
    customer_a = app_client.post(
        "/api/customers",
        json={"name": "甲客户", "location": "城北"},
    ).json()["data"]
    customer_b = app_client.post(
        "/api/customers",
        json={"name": "乙客户", "location": "城南"},
    ).json()["data"]

    for supplier in (supplier_a, supplier_b):
        response = app_client.post(
            "/api/orders/purchases",
            json={
                "supplier_id": supplier["id"],
                "items": [{"part_id": part["id"], "quantity": 5, "purchase_price": 500}],
            },
        )
        assert response.status_code == 200

    for customer in (customer_a, customer_b):
        response = app_client.post(
            "/api/orders/sales",
            json={
                "customer_id": customer["id"],
                "items": [{"part_id": part["id"], "quantity": 1, "sale_price": 800}],
            },
        )
        assert response.status_code == 200

    purchases = app_client.get(
        "/api/orders/purchases",
        params={"supplier_id": supplier_a["id"], "limit": 500},
    ).json()["data"]
    assert len(purchases) == 1
    assert purchases[0]["supplier_id"] == supplier_a["id"]

    sales = app_client.get(
        "/api/orders/sales",
        params={"customer_id": customer_b["id"], "limit": 500},
    ).json()["data"]
    assert len(sales) == 1
    assert sales[0]["customer_id"] == customer_b["id"]


def test_purchase_and_sales_orders_can_download_black_and_white_pdf(app_client):
    print_settings = app_client.get("/api/settings").json()["data"]
    print_settings.update(
        {
            "print_payment_account": "测试银行 123456",
            "print_wechat": "PRINT-WECHAT",
            "print_warranty_period": "三包期内凭单退换",
            "print_reviewer": "测试复核员",
            "print_custom_fields": [
                {
                    "label": "运输方式",
                    "value": "",
                    "visible": True,
                    "handwritten": True,
                }
            ],
        }
    )
    assert app_client.put("/api/settings", json=print_settings).status_code == 200

    part = _create_part(app_client, "PRINT-001")
    supplier = app_client.post(
        "/api/suppliers",
        json={
            "name": "测试供应商",
            "contact": "供货联系人",
            "phone": "13800000001",
            "address": "测试供应商地址",
        },
    ).json()["data"]
    customer = app_client.post(
        "/api/customers",
        json={
            "name": "测试客户",
            "phone": "13800000002",
            "location": "测试客户地址",
        },
    ).json()["data"]

    purchase = app_client.post(
        "/api/orders/purchases",
        json={
            "supplier_id": supplier["id"],
            "items": [{"part_id": part["id"], "quantity": 5, "purchase_price": 500}],
            "remark": "采购打印测试",
        },
    ).json()["data"]
    sale = app_client.post(
        "/api/orders/sales",
        json={
            "customer_id": customer["id"],
            "items": [{"part_id": part["id"], "quantity": 2, "sale_price": 800}],
            "remark": "销售打印测试",
        },
    ).json()["data"]

    for kind, order in (("purchases", purchase), ("sales", sale)):
        response = app_client.get(f"/api/orders/{kind}/{order['id']}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")
        assert len(response.content) > 5_000
