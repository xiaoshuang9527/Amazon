"""生成 / 查询 / 导出接口测试（LLM 用假网关，全链路不发起外部请求）。"""

import os

import pytest
from conftest import SAMPLE_SOURCE_CONTENT

from app.api.v1.generate import EXPORT_DIR
from app.services.billing_service import BillingService

GENERATE_URL = "/api/v1/generate/listing"

PAYLOAD = {
    "shop_id": None,
    "source_content": SAMPLE_SOURCE_CONTENT,
    "target_marketplaces": ["US", "DE"],
    "category": "Electronics",
    "tone": "professional",
    "quality": "standard",
}


def _submit(client, headers, **overrides):
    payload = {**PAYLOAD, **overrides}
    return client.post(GENERATE_URL, json=payload, headers=headers)


def test_generate_requires_auth(client):
    assert client.post(GENERATE_URL, json=PAYLOAD).status_code == 401


def test_generate_rejects_unsupported_marketplace(client, auth_headers):
    resp = _submit(client, auth_headers, target_marketplaces=["XX"])
    assert resp.status_code >= 400


def test_generate_rejects_empty_marketplace_list(client, auth_headers):
    resp = _submit(client, auth_headers, target_marketplaces=[])
    assert resp.status_code >= 400


def test_generate_full_flow_returns_multilingual_results(client, auth_headers, patched_gateway):
    resp = _submit(client, auth_headers)
    assert resp.status_code == 200, resp.text
    task_id = resp.json()["task_id"]
    assert task_id

    status = client.get(f"/api/v1/generate/{task_id}", headers=auth_headers)
    assert status.status_code == 200
    body = status.json()
    assert body["task_id"] == task_id
    assert body["status"] == "success"
    assert body["errors"] == []

    results = {r["target_marketplace"]: r for r in body["results"]}
    assert set(results) == {"US", "DE"}
    for marketplace, language in (("US", "en"), ("DE", "de")):
        item = results[marketplace]
        assert item["title"] and item["description"] and item["search_terms"]
        assert len(item["bullets"]) == 5
        assert item["suggested_keywords"]
        assert item["compliance_report"]["passed"] is True


def test_task_status_unknown_returns_404(client, auth_headers):
    resp = client.get("/api/v1/generate/task-not-exist", headers=auth_headers)
    assert resp.status_code == 404


def test_history_returns_generated_rows(client, auth_headers, patched_gateway):
    task_id = _submit(client, auth_headers, target_marketplaces=["US"]).json()["task_id"]
    resp = client.get("/api/v1/generate/history", headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert rows and rows[0]["task_id"] == task_id
    assert rows[0]["target_marketplace"] == "US"


def test_high_quality_mode_accepted(client, auth_headers, patched_gateway):
    resp = _submit(client, auth_headers, quality="high", target_marketplaces=["JP"])
    assert resp.status_code == 200
    status = client.get(f"/api/v1/generate/{resp.json()['task_id']}", headers=auth_headers)
    assert status.json()["results"][0]["target_marketplace"] == "JP"


@pytest.mark.parametrize("fmt", ["xlsx", "json", "csv"])
def test_export_downloads_file(client, auth_headers, patched_gateway, fmt):
    task_id = _submit(client, auth_headers).json()["task_id"]
    resp = client.get(
        f"/api/v1/generate/{task_id}/export", params={"format": fmt}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.content) > 0
    assert f"listing_{task_id}.{fmt}" in resp.headers.get("content-disposition", "")

    produced = os.path.join(EXPORT_DIR, f"listing_{task_id}.{fmt}")
    if os.path.exists(produced):
        os.remove(produced)


def test_export_rejects_bad_format(client, auth_headers, patched_gateway):
    task_id = _submit(client, auth_headers).json()["task_id"]
    resp = client.get(
        f"/api/v1/generate/{task_id}/export", params={"format": "pdf"}, headers=auth_headers
    )
    assert resp.status_code == 422


def test_quota_exceeded_returns_402(client, auth_headers, db, patched_gateway):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    sub = BillingService(db).ensure_subscription(me["id"])
    sub.quota_used = 9999
    db.commit()

    resp = _submit(client, auth_headers)
    assert resp.status_code == 402


def test_quota_is_consumed_per_task(client, auth_headers, patched_gateway):
    before = client.get("/api/v1/billing/usage", headers=auth_headers).json()["quota_used"]

    _submit(client, auth_headers, target_marketplaces=["US"])
    after = client.get("/api/v1/billing/usage", headers=auth_headers).json()
    assert after["quota_used"] == before + 1
    assert after["plan"] == "free"
