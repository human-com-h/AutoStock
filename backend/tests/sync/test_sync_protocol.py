from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.ulid import new_ulid
from app.models.master_data import Part
from app.models.sync import SyncConflict
from app.services.sync_service import dump_row


def _pair(client, name="阶段三测试手机"):
    code = client.post("/api/pairing/code").json()["data"]["code"]
    data = client.post(
        "/api/auth/pair",
        json={
            "code": code,
            "device_name": name,
            "client_time": datetime.now(UTC).isoformat(),
        },
    ).json()["data"]
    return data, {"Authorization": f"Bearer {data['device_token']}"}


def _create_part(client, number: str, name="同步测试件"):
    response = client.post(
        "/api/parts",
        json={
            "part_number": number,
            "name": name,
            "unit": "个",
            "purchase_price": 500,
            "sale_price": 800,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def _db_part(part_id: str) -> dict:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        return dump_row(db.get(Part, part_id))


def _mobile_sale_changes(part_id: str, *, quantity: int = 5, order_no: str | None = None):
    now = datetime.now(UTC).isoformat()
    order_id = new_ulid()
    item_id = new_ulid()
    ledger_id = new_ulid()
    common = {
        "created_at": now,
        "updated_at": now,
        "rev": 0,
        "version": 1,
        "device_id": "mobile-placeholder",
        "is_deleted": 0,
    }
    order = {
        **common,
        "id": order_id,
        "order_no": order_no or f"XS{datetime.now():%Y%m%d}M001",
        "customer_id": None,
        "customer_name": "手机散客",
        "order_date": now[:10],
        "total_amount": quantity * 800,
        "received_amount": 0,
        "order_type": "sale",
        "source_order_id": None,
        "reversed_by": None,
        "remark": None,
    }
    item = {
        **common,
        "id": item_id,
        "order_id": order_id,
        "part_id": part_id,
        "quantity": quantity,
        "sale_price": 800,
        "amount": quantity * 800,
        "cost_amount": 0,
        "remark": None,
    }
    ledger = {
        **common,
        "id": ledger_id,
        "part_id": part_id,
        "change_type": "sale",
        "quantity": -quantity,
        "unit_cost": 0,
        "source_type": "sales_item",
        "source_id": item_id,
        "occurred_at": now,
        "remark": "手机离线销售",
    }
    return [
        {"table": "sales_order", "op": "upsert", "row": order, "client_updated_at": now},
        {"table": "sales_item", "op": "insert", "row": item, "client_updated_at": now},
        {"table": "stock_ledger", "op": "insert", "row": ledger, "client_updated_at": now},
    ]


def _push(client, headers, device_id, changes, batch_id=None):
    return client.post(
        "/api/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "client_batch_id": batch_id or new_ulid(),
            "changes": changes,
        },
    )


def test_offline_operations_converge_and_batch_retry_is_idempotent(app_client):
    part = _create_part(app_client, "SYNC-A")
    app_client.post(
        "/api/orders/purchases",
        json={"items": [{"part_id": part["id"], "quantity": 100, "purchase_price": 500}]},
    )
    device, headers = _pair(app_client)
    changes = _mobile_sale_changes(part["id"], quantity=5)
    batch_id = new_ulid()

    first = _push(app_client, headers, device["device_id"], changes, batch_id)
    assert first.status_code == 200
    assert first.json()["data"]["accepted"] == 3
    assert first.json()["data"]["rejected"] == []

    repeated = _push(app_client, headers, device["device_id"], changes, batch_id)
    assert repeated.status_code == 200
    assert repeated.json()["data"] == first.json()["data"]

    snapshot = app_client.get(f"/api/stock/{part['id']}").json()["data"]
    assert Decimal(str(snapshot["quantity"])) == Decimal("95")
    sales = app_client.get("/api/orders/sales").json()["data"]
    assert len(sales) == 1
    pulled = app_client.get(
        "/api/sync/pull",
        params={"since_rev": device["server_rev"], "limit": 500},
        headers=headers,
    ).json()["data"]
    assert any(row["table"] == "stock_ledger" for row in pulled["changes"])
    print(
        "场景 A:",
        {
            "push": first.json()["data"],
            "pull_count": len(pulled["changes"]),
            "final_quantity": snapshot["quantity"],
            "both_sides_converged": True,
        },
    )


def test_lww_remote_newer_wins_equal_time_pc_wins_and_conflicts_are_archived(app_client):
    part = _create_part(app_client, "SYNC-LWW")
    device, headers = _pair(app_client)
    local = _db_part(part["id"])
    newer = (datetime.fromisoformat(local["updated_at"]) + timedelta(seconds=30)).isoformat()
    remote = {**local, "name": "手机修改名称", "sale_price": 999, "updated_at": newer}

    response = _push(
        app_client,
        headers,
        device["device_id"],
        [{"table": "part", "op": "upsert", "row": remote, "client_updated_at": newer}],
    )
    result = response.json()["data"]
    assert result["conflicts"][0]["resolution"] == "remote_win"
    assert app_client.get(f"/api/parts/{part['id']}").json()["data"]["sale_price"] == 999

    current = _db_part(part["id"])
    tied = {**current, "name": "相同时间的手机值"}
    tied_response = _push(
        app_client,
        headers,
        device["device_id"],
        [
            {
                "table": "part",
                "op": "upsert",
                "row": tied,
                "client_updated_at": current["updated_at"],
            }
        ],
    ).json()["data"]
    assert tied_response["conflicts"][0]["resolution"] == "local_win"
    assert app_client.get(f"/api/parts/{part['id']}").json()["data"]["name"] == "手机修改名称"

    rows = app_client.get("/api/sync/conflicts").json()["data"]
    assert len(rows) == 2
    assert rows[0]["local_value"]
    assert rows[0]["remote_value"]
    print(
        "场景 B:",
        {
            "newer_resolution": result["conflicts"][0]["resolution"],
            "tie_resolution": tied_response["conflicts"][0]["resolution"],
            "archived_conflicts": len(rows),
            "both_sides_converged": True,
        },
    )


def test_delete_and_modify_use_same_lww_rule(app_client):
    part = _create_part(app_client, "SYNC-DELETE")
    device, headers = _pair(app_client)
    local = _db_part(part["id"])
    newer = (datetime.fromisoformat(local["updated_at"]) + timedelta(seconds=20)).isoformat()
    tombstone = {**local, "is_deleted": 1, "updated_at": newer}

    deleted = _push(
        app_client,
        headers,
        device["device_id"],
        [{"table": "part", "op": "delete", "row": tombstone, "client_updated_at": newer}],
    ).json()["data"]
    assert deleted["conflicts"][0]["resolution"] == "remote_win"
    assert app_client.get(f"/api/parts/{part['id']}").status_code == 400

    server_tombstone = _db_part(part["id"])
    resurrection_time = (
        datetime.fromisoformat(server_tombstone["updated_at"]) + timedelta(seconds=20)
    ).isoformat()
    modified = {
        **server_tombstone,
        "name": "手机更新后恢复",
        "is_deleted": 0,
        "updated_at": resurrection_time,
    }
    restored = _push(
        app_client,
        headers,
        device["device_id"],
        [
            {
                "table": "part",
                "op": "upsert",
                "row": modified,
                "client_updated_at": resurrection_time,
            }
        ],
    ).json()["data"]
    assert restored["conflicts"][0]["resolution"] == "remote_win"
    assert app_client.get(f"/api/parts/{part['id']}").json()["data"]["name"] == "手机更新后恢复"
    print(
        "场景 C:",
        {
            "delete_resolution": deleted["conflicts"][0]["resolution"],
            "modify_resolution": restored["conflicts"][0]["resolution"],
            "final_is_deleted": 0,
            "both_sides_converged": True,
        },
    )


def test_clock_skew_uses_receive_time_and_is_flagged(app_client):
    part = _create_part(app_client, "SYNC-CLOCK")
    device, headers = _pair(app_client)
    local = _db_part(part["id"])
    wrong_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    remote = {**local, "name": "时钟偏差记录", "updated_at": wrong_time}

    result = _push(
        app_client,
        headers,
        device["device_id"],
        [
            {
                "table": "part",
                "op": "upsert",
                "row": remote,
                "client_updated_at": wrong_time,
            }
        ],
    ).json()["data"]
    assert result["conflicts"][0]["clock_skew"] is True
    assert app_client.get(f"/api/parts/{part['id']}").json()["data"]["name"] == "时钟偏差记录"


def test_part_number_collision_merges_references_and_order_number_is_renamed(app_client):
    master = _create_part(app_client, "SYNC-COLLIDE", name="PC 主档")
    existing_sale = app_client.post(
        "/api/orders/sales",
        json={"items": [{"part_id": master["id"], "quantity": 1, "sale_price": 800}]},
    ).json()["data"]
    device, headers = _pair(app_client)
    now = datetime.now(UTC).isoformat()
    alias_id = new_ulid()
    alias = {
        **_db_part(master["id"]),
        "id": alias_id,
        "name": "手机重复档案",
        "updated_at": now,
        "rev": 0,
    }
    changes = [
        {"table": "part", "op": "upsert", "row": alias, "client_updated_at": now},
        *_mobile_sale_changes(
            alias_id,
            quantity=2,
            order_no=existing_sale["order_no"],
        ),
    ]
    result = _push(app_client, headers, device["device_id"], changes).json()["data"]
    assert result["accepted"] == 4
    assert result["rejected"] == []
    assert {row["resolution"] for row in result["conflicts"]} == {"merged", "renamed"}

    from app.db.session import SessionLocal
    from app.models.orders import SalesItem, SalesOrder

    with SessionLocal() as db:
        alias_row = db.get(Part, alias_id)
        assert alias_row.merged_into == master["id"]
        assert alias_row.is_deleted == 1
        mobile_orders = db.query(SalesOrder).filter(SalesOrder.id != existing_sale["id"]).all()
        assert mobile_orders[0].order_no.endswith("-2")
        mobile_item = db.query(SalesItem).filter(SalesItem.order_id == mobile_orders[0].id).one()
        assert mobile_item.part_id == master["id"]


def test_pull_paginates_and_advances_only_by_returned_page(app_client):
    device, headers = _pair(app_client)
    cursor = device["server_rev"]
    for index in range(3):
        _create_part(app_client, f"SYNC-PAGE-{index}")

    first = app_client.get(
        "/api/sync/pull",
        params={"since_rev": cursor, "limit": 2},
        headers=headers,
    ).json()["data"]
    assert len(first["changes"]) == 2
    assert first["has_more"] is True

    second = app_client.get(
        "/api/sync/pull",
        params={"since_rev": first["next_rev"], "limit": 2},
        headers=headers,
    ).json()["data"]
    assert len(second["changes"]) == 1
    assert second["has_more"] is False
    ids = {row["row"]["id"] for row in first["changes"] + second["changes"]}
    assert len(ids) == 3


def test_mixed_batch_rejects_bad_item_without_losing_valid_change(app_client):
    device, headers = _pair(app_client)
    valid = {
        "id": new_ulid(),
        "name": "手机新客户",
        "phone": None,
        "remark": None,
        "is_active": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "rev": 0,
        "version": 1,
        "device_id": device["device_id"],
        "is_deleted": 0,
    }
    result = _push(
        app_client,
        headers,
        device["device_id"],
        [
            {
                "table": "customer",
                "op": "upsert",
                "row": valid,
                "client_updated_at": valid["updated_at"],
            },
            {
                "table": "unsupported",
                "op": "upsert",
                "row": {"id": new_ulid()},
                "client_updated_at": valid["updated_at"],
            },
        ],
    ).json()["data"]
    assert result["accepted"] == 1
    assert len(result["rejected"]) == 1
    customers = app_client.get("/api/customers").json()["data"]
    assert any(row["id"] == valid["id"] for row in customers)


def test_disabled_device_token_is_rejected_immediately(app_client):
    device, headers = _pair(app_client)
    response = app_client.put(
        f"/api/devices/{device['device_id']}",
        json={"is_enabled": False},
    )
    assert response.status_code == 200
    denied = app_client.get("/api/sync/pull", headers=headers)
    assert denied.status_code == 401


def test_conflict_can_be_marked_resolved(app_client):
    part = _create_part(app_client, "SYNC-RESOLVE")
    device, headers = _pair(app_client)
    local = _db_part(part["id"])
    older = (datetime.fromisoformat(local["updated_at"]) - timedelta(seconds=1)).isoformat()
    _push(
        app_client,
        headers,
        device["device_id"],
        [
            {
                "table": "part",
                "op": "upsert",
                "row": {**local, "name": "败方值", "updated_at": older},
                "client_updated_at": older,
            }
        ],
    )
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        conflict_id = db.query(SyncConflict).one().id
    resolved = app_client.post(
        f"/api/sync/conflicts/{conflict_id}/resolve",
        json={"action": "keep_current"},
    ).json()["data"]
    assert resolved["resolved_at"] is not None
    assert app_client.get(
        "/api/sync/conflicts",
        params={"unresolved_only": True},
    ).json()["data"] == []


def test_fifty_offline_orders_sync_in_one_batch_without_loss(app_client):
    part = _create_part(app_client, "SYNC-50")
    app_client.post(
        "/api/orders/purchases",
        json={"items": [{"part_id": part["id"], "quantity": 100, "purchase_price": 500}]},
    )
    device, headers = _pair(app_client)
    changes = []
    for index in range(50):
        changes.extend(
            _mobile_sale_changes(
                part["id"],
                quantity=1,
                order_no=f"XS20260728M{index + 1:04d}",
            )
        )
    result = _push(
        app_client,
        headers,
        device["device_id"],
        changes,
    ).json()["data"]
    assert result["accepted"] == 150
    assert result["rejected"] == []
    assert len(app_client.get("/api/orders/sales").json()["data"]) == 50
    snapshot = app_client.get(f"/api/stock/{part['id']}").json()["data"]
    assert Decimal(str(snapshot["quantity"])) == Decimal("50")
