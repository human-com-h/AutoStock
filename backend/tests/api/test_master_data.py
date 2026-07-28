def test_category_crud(app_client):
    resp = app_client.post("/api/categories", json={"name": "刹车系统", "sort_no": 1})
    assert resp.status_code == 200
    cat = resp.json()["data"]
    assert cat["is_active"] == 1

    child = app_client.post(
        "/api/categories", json={"name": "刹车片", "parent_id": cat["id"], "sort_no": 1}
    ).json()["data"]
    assert child["parent_id"] == cat["id"]

    listed = app_client.get("/api/categories").json()["data"]
    assert len(listed) == 2

    disabled = app_client.put(f"/api/categories/{cat['id']}", json={"is_active": 0}).json()["data"]
    assert disabled["is_active"] == 0


def test_brand_duplicate_name_rejected(app_client):
    first = app_client.post("/api/brands", json={"name": "博世", "remark": "德系"})
    assert first.status_code == 200

    dup = app_client.post("/api/brands", json={"name": "博世"})
    assert dup.status_code == 400
    assert dup.json()["error"]["code"] == "BUSINESS_BRAND_DUPLICATE"


def test_brand_part_count_reflects_parts_table(app_client):
    brand = app_client.post("/api/brands", json={"name": "马牌"}).json()["data"]
    listed = app_client.get("/api/brands").json()["data"]
    matched = next(b for b in listed if b["id"] == brand["id"])
    assert matched["part_count"] == 0


def test_supplier_and_customer_crud(app_client):
    supplier = app_client.post(
        "/api/suppliers", json={"name": "华东汽配", "contact": "张三", "phone": "13800000000"}
    ).json()["data"]
    assert supplier["name"] == "华东汽配"

    updated = app_client.put(f"/api/suppliers/{supplier['id']}", json={"phone": "13900000000"})
    assert updated.json()["data"]["phone"] == "13900000000"

    customer = app_client.post("/api/customers", json={"name": "散客"}).json()["data"]
    assert customer["is_active"] == 1

    listed = app_client.get("/api/customers").json()["data"]
    assert any(c["id"] == customer["id"] for c in listed)


def test_update_nonexistent_returns_business_not_found(app_client):
    resp = app_client.put("/api/categories/does-not-exist", json={"name": "x"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "BUSINESS_NOT_FOUND"


def test_customer_location_can_be_created_updated_and_listed(app_client):
    created = app_client.post(
        "/api/customers",
        json={"name": "城北修理厂", "phone": "13800000001", "location": "城北"},
    )
    assert created.status_code == 200
    customer = created.json()["data"]
    assert customer["location"] == "城北"

    updated = app_client.put(
        f"/api/customers/{customer['id']}",
        json={"location": "开发区"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["location"] == "开发区"

    listed = app_client.get("/api/customers").json()["data"]
    matched = next(row for row in listed if row["id"] == customer["id"])
    assert matched["location"] == "开发区"
