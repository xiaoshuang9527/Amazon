"""计费与 Listing 接口测试。"""


def test_plans_are_public_and_complete(client):
    resp = client.get("/api/v1/billing/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert [p["code"] for p in plans] == ["free", "basic", "pro"]

    basic = next(p for p in plans if p["code"] == "basic")
    assert basic["price_monthly"] == 199.0
    assert basic["price_yearly"] == 1999.0
    assert basic["price_per_month_yearly"] == round(1999.0 / 12, 2)
    assert basic["features"]


def test_usage_defaults_to_free_plan(client, auth_headers):
    resp = client.get("/api/v1/billing/usage", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "free"
    assert body["quota_used"] == 0
    assert body["quota_remaining"] == body["quota_total"]


def test_usage_requires_auth(client):
    assert client.get("/api/v1/billing/usage").status_code == 401


def test_subscribe_upgrades_plan_and_resets_quota(client, auth_headers):
    resp = client.post(
        "/api/v1/billing/subscribe", json={"plan": "pro", "period": "yearly"}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_created"] is True
    assert body["plan"] == "pro"
    assert body["amount"] == 3999.0

    usage = client.get("/api/v1/billing/usage", headers=auth_headers).json()
    assert usage["plan"] == "pro"
    assert usage["quota_used"] == 0
    assert usage["quota_total"] > 100


def test_subscribe_monthly_pricing(client, auth_headers):
    resp = client.post(
        "/api/v1/billing/subscribe", json={"plan": "basic", "period": "monthly"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["amount"] == 199.0


def test_subscribe_free_plan_is_rejected(client, auth_headers):
    resp = client.post(
        "/api/v1/billing/subscribe", json={"plan": "free", "period": "monthly"}, headers=auth_headers
    )
    assert resp.status_code >= 400


def test_subscribe_unknown_plan_is_rejected(client, auth_headers):
    resp = client.post(
        "/api/v1/billing/subscribe", json={"plan": "enterprise", "period": "monthly"},
        headers=auth_headers,
    )
    assert resp.status_code >= 400


def test_payment_webhook_accepts_payload(client):
    resp = client.post("/api/v1/billing/webhook", json={"order_id": "o-1", "status": "paid"})
    assert resp.status_code == 200
    assert resp.json() == {"received": True}


# --------------------------------------------------------------------------- #
# listings
# --------------------------------------------------------------------------- #
SAMPLE_LISTING = {
    "shop_id": None,
    "asin": "B0APITEST01",
    "sku": "SKU-API-1",
    "marketplace_id": "US",
    "source_language": "zh",
    "source_content": {
        "title": "无线蓝牙耳机 头戴式",
        "bullets": ["40 小时续航"],
        "description": "适合通勤与旅行",
        "keywords": ["蓝牙耳机"],
        "attributes": {"battery": "40H"},
    },
}


def test_create_and_fetch_listing(client, auth_headers):
    resp = client.post("/api/v1/listings", json=SAMPLE_LISTING, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    created = resp.json()
    assert created["asin"] == "B0APITEST01"
    assert created["source_content"]["title"] == "无线蓝牙耳机 头戴式"

    detail = client.get(f"/api/v1/listings/{created['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["sku"] == "SKU-API-1"

    listing = client.get("/api/v1/listings", headers=auth_headers)
    assert listing.status_code == 200
    assert any(item["id"] == created["id"] for item in listing.json())


def test_listing_detail_unknown_returns_404(client, auth_headers):
    assert client.get("/api/v1/listings/987654", headers=auth_headers).status_code == 404


def test_listings_require_auth(client):
    assert client.get("/api/v1/listings").status_code == 401


def test_validate_endpoint_passes_clean_copy(client, auth_headers):
    resp = client.post(
        "/api/v1/listings/validate",
        json={
            "marketplace_id": "US",
            "category": "Electronics",
            "title": "Wireless Bluetooth Headphones, Over-Ear Design, 40H Playtime",
            "bullets": ["40 hours of playtime keeps your music going"],
            "search_terms": "wireless headphones bluetooth",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"passed": True, "violations": []}


def test_validate_endpoint_reports_violations(client, auth_headers):
    resp = client.post(
        "/api/v1/listings/validate",
        json={
            "marketplace_id": "US",
            "title": "Best Wireless Headphones with Free Shipping",
            "brand_words": ["Nike"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is False
    types = {v["type"] for v in body["violations"]}
    assert "absolute_term" in types and "promo_term" in types
    assert all("suggestion" in v for v in body["violations"])


def test_validate_endpoint_rejects_short_marketplace(client, auth_headers):
    resp = client.post(
        "/api/v1/listings/validate", json={"marketplace_id": "U"}, headers=auth_headers
    )
    assert resp.status_code == 422
