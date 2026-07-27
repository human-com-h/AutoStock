def _create_part(client, **overrides):
    body = {
        "part_number": "P001",
        "oe_number": "OE-123, OE-456",
        "name": "刹车片",
        "unit": "副",
        "purchase_price": 1000,
        "sale_price": 1500,
    }
    body.update(overrides)
    return client.post("/api/parts", json=body)


def test_create_part_generates_pinyin_and_normalizes_oe(app_client):
    resp = _create_part(app_client)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["pinyin"] == "SCP"
    assert data["oe_number"] == "OE-123,OE-456"
    assert data["is_active"] == 1


def test_duplicate_part_number_rejected(app_client):
    _create_part(app_client)
    dup = _create_part(app_client, name="刹车盘")
    assert dup.status_code == 400
    assert dup.json()["error"]["code"] == "BUSINESS_PART_NUMBER_DUPLICATE"


def test_search_by_part_number_oe_name_and_pinyin(app_client):
    _create_part(app_client)

    for kw in ("P001", "OE-123", "刹车片", "SCP"):
        found = app_client.get("/api/parts", params={"keyword": kw}).json()["data"]
        assert len(found) == 1, f"keyword {kw} should match"
        assert found[0]["part_number"] == "P001"

    empty = app_client.get("/api/parts", params={"keyword": "不存在"}).json()["data"]
    assert empty == []


def test_update_part_renames_pinyin_and_checks_uniqueness(app_client):
    part = _create_part(app_client).json()["data"]
    other = _create_part(app_client, part_number="P002", name="雨刷").json()["data"]

    renamed = app_client.put(f"/api/parts/{part['id']}", json={"name": "刹车皮"}).json()["data"]
    assert renamed["pinyin"] == "SCP"

    dup = app_client.put(f"/api/parts/{part['id']}", json={"part_number": "P002"})
    assert dup.status_code == 400
    assert dup.json()["error"]["code"] == "BUSINESS_PART_NUMBER_DUPLICATE"
    assert other["part_number"] == "P002"


def test_delete_without_ledger_history_soft_deletes(app_client):
    part = _create_part(app_client).json()["data"]
    resp = app_client.delete(f"/api/parts/{part['id']}")
    assert resp.status_code == 200

    listed = app_client.get("/api/parts").json()["data"]
    assert listed == []

    missing = app_client.get(f"/api/parts/{part['id']}")
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "BUSINESS_NOT_FOUND"
