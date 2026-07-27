from decimal import Decimal


def _create_part(client):
    return client.post(
        "/api/parts",
        json={"part_number": "TAKE-001", "name": "盘点零件", "unit": "个"},
    ).json()["data"]


def _quantity(client, part_id):
    return Decimal(str(client.get(f"/api/stock/{part_id}").json()["data"]["quantity"]))


def test_stock_take_posts_difference_after_period_movements(app_client):
    part = _create_part(app_client)
    app_client.post(
        "/api/orders/purchases",
        json={
            "items": [{"part_id": part["id"], "quantity": 10, "purchase_price": 500}]
        },
    )
    take = app_client.post("/api/stock-takes", json={"scope_type": "all"}).json()["data"]
    assert take["items"][0]["book_quantity"] == 10

    app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": part["id"], "quantity": 2, "sale_price": 800}]},
    )
    assert _quantity(app_client, part["id"]) == Decimal("8")

    updated = app_client.put(
        f"/api/stock-takes/{take['id']}/items",
        json={"items": [{"part_id": part["id"], "actual_quantity": 9}]},
    )
    assert updated.status_code == 200

    posted = app_client.post(f"/api/stock-takes/{take['id']}/post")
    assert posted.status_code == 200
    data = posted.json()["data"]
    assert data["status"] == "posted"
    assert data["items"][0]["diff_quantity"] == 1
    assert _quantity(app_client, part["id"]) == Decimal("9")

    duplicate = app_client.post(f"/api/stock-takes/{take['id']}/post")
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "BUSINESS_STOCK_TAKE_POSTED"


def test_stock_take_requires_all_actual_quantities(app_client):
    _create_part(app_client)
    take = app_client.post("/api/stock-takes", json={}).json()["data"]
    response = app_client.post(f"/api/stock-takes/{take['id']}/post")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BUSINESS_STOCK_TAKE_INCOMPLETE"
