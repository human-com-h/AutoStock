from datetime import UTC, datetime, timedelta


def test_pairing_exchange_and_bootstrap(app_client):
    part = app_client.post(
        "/api/parts",
        json={
            "part_number": "MOBILE-001",
            "name": "手机端测试零件",
            "unit": "个",
            "purchase_price": 1200,
            "sale_price": 1800,
        },
    ).json()["data"]
    app_client.post(
        "/api/orders/purchases",
        json={
            "items": [{"part_id": part["id"], "quantity": 5, "purchase_price": 1200}]
        },
    )

    pairing = app_client.post("/api/pairing/code")
    assert pairing.status_code == 200
    code = pairing.json()["data"]["code"]
    assert len(code) == 6
    pairing_url = pairing.json()["data"]["pairing_urls"][0]
    assert f"#/setup?pair={code}" in pairing_url
    qr = app_client.get("/api/pairing/qr", params={"content": pairing_url})
    assert qr.status_code == 200
    assert qr.headers["content-type"] == "image/png"
    assert qr.content.startswith(b"\x89PNG")

    exchange = app_client.post(
        "/api/auth/pair",
        json={
            "code": code,
            "device_name": "测试手机",
            "client_time": datetime.now(UTC).isoformat(),
        },
    )
    assert exchange.status_code == 200
    data = exchange.json()["data"]
    headers = {"Authorization": f"Bearer {data['device_token']}"}

    page = app_client.get(
        "/api/mobile/bootstrap/parts?limit=1",
        headers=headers,
    )
    assert page.status_code == 200
    result = page.json()["data"]
    assert result["total"] == 1
    assert result["items"][0]["part"]["part_number"] == "MOBILE-001"
    assert result["items"][0]["snapshot"]["quantity"] == 5

    orders = app_client.get("/api/mobile/bootstrap/orders", headers=headers)
    assert len(orders.json()["data"]["purchase_orders"]) == 1
    assert len(orders.json()["data"]["stock_ledgers"]) == 1

    reused = app_client.post(
        "/api/pairing/exchange",
        json={"code": code, "device_name": "重复手机"},
    )
    assert reused.status_code == 400


def test_pairing_rejects_clock_skew(app_client):
    pairing = app_client.post("/api/pairing/code").json()["data"]
    response = app_client.post(
        "/api/auth/pair",
        json={
            "code": pairing["code"],
            "device_name": "时间错误的手机",
            "client_time": (datetime.now(UTC) - timedelta(minutes=3)).isoformat(),
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BUSINESS_DEVICE_TIME_SKEW"
