def test_health_no_auth_required(app_client):
    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_setup_and_login_flow(app_client):
    status = app_client.get("/api/auth/status").json()
    assert status["data"]["has_password"] is False

    setup_resp = app_client.post("/api/auth/setup", json={"password": "abcd1234"})
    assert setup_resp.status_code == 200

    again = app_client.post("/api/auth/setup", json={"password": "other"})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "BUSINESS_PASSWORD_ALREADY_SET"

    bad_login = app_client.post("/api/auth/login", json={"password": "wrong"})
    assert bad_login.status_code == 400
    assert bad_login.json()["error"]["code"] == "BUSINESS_LOGIN_FAILED"

    good_login = app_client.post("/api/auth/login", json={"password": "abcd1234"})
    assert good_login.status_code == 200
    assert "autostock_session" in good_login.cookies


def test_setup_rejects_short_password(app_client):
    resp = app_client.post("/api/auth/setup", json={"password": "12"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_PASSWORD_TOO_SHORT"
