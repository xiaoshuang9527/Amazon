"""认证与店铺授权接口测试。"""

from app.core.security import decrypt_secret
from app.models.shop import Shop


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_then_login(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "flow@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "flow@example.com"
    assert "hashed_password" not in resp.json()

    resp = client.post(
        "/api/v1/auth/token",
        data={"username": "flow@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


def test_register_duplicate_email_is_rejected(client):
    payload = {"email": "dup@example.com", "password": "secret123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 200
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code >= 400


def test_login_with_wrong_password_is_rejected(client):
    client.post("/api/v1/auth/register", json={"email": "wrong@example.com", "password": "secret123"})
    resp = client.post(
        "/api/v1/auth/token", data={"username": "wrong@example.com", "password": "bad-password"}
    )
    assert resp.status_code >= 400


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_user(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "tester@example.com"
    assert resp.json()["is_active"] is True


def test_shops_list_is_empty_for_new_user(client, auth_headers):
    resp = client.get("/api/v1/auth/shops", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_spapi_authorize_returns_lwa_url(client, auth_headers):
    resp = client.get("/api/v1/auth/spapi/authorize", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "authorize_url" in body and body["state"]
    assert "state=" in body["authorize_url"]


def test_spapi_authorize_requires_auth(client):
    assert client.get("/api/v1/auth/spapi/authorize").status_code == 401


def test_spapi_callback_stores_encrypted_refresh_token(client, db, monkeypatch):
    from app.api.v1 import auth as auth_module

    monkeypatch.setattr(
        auth_module.spapi_service,
        "exchange_code_for_token",
        lambda code: {
            "refresh_token": "Atzr|callback-token-plain",
            "access_token": "access-1",
            "expires_in": 3600,
            "seller_id": "A1CALLBACK",
        },
    )

    resp = client.get(
        "/api/v1/auth/spapi/callback",
        params={"code": "auth-code", "selling_partner_id": "A1CALLBACK"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "authorized"

    db.rollback()
    shop = db.query(Shop).filter(Shop.seller_id == "A1CALLBACK").one()
    assert shop.refresh_token != "Atzr|callback-token-plain"
    assert decrypt_secret(shop.refresh_token) == "Atzr|callback-token-plain"


def test_spapi_service_caches_access_token(monkeypatch):
    from app.services.spapi_service import SPAPIService

    service = SPAPIService()
    calls = {"n": 0}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"access_token": "token-1", "expires_in": 3600}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            calls["n"] += 1
            return _Resp()

    monkeypatch.setattr("app.services.spapi_service.httpx.Client", _Client)

    assert service.get_access_token("refresh-x") == "token-1"
    assert service.get_access_token("refresh-x") == "token-1"  # 命中内存缓存
    assert calls["n"] == 1

    service.clear_cache()
    service.get_access_token("refresh-x")
    assert calls["n"] == 2
