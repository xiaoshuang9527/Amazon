"""回填链路测试：GET /listings/{id}/diff 与 POST /listings/{id}/apply。

覆盖：
- 鉴权与 404/400 分支；
- diff 基准来源（原始信息 vs 上次回填结果）；
- 逐字段勾选回填、字段值覆盖、未勾选字段保持不变；
- 合规校验拦截与 force 强制提交。
"""

import pytest
from conftest import SAMPLE_SOURCE_CONTENT

from app.models.generation import Generation

LISTINGS_URL = "/api/v1/listings"
GENERATE_URL = "/api/v1/generate/listing"

GENERATE_PAYLOAD = {
    "shop_id": None,
    "source_content": SAMPLE_SOURCE_CONTENT,
    "target_marketplaces": ["US"],
    "category": "Electronics",
    "tone": "professional",
    "quality": "standard",
}


def _create_listing(client, headers, **overrides) -> int:
    payload = {
        "shop_id": None,
        "asin": "B0BACKFILL1",
        "sku": "SKU-BF-1",
        "marketplace_id": "US",
        "source_language": "zh",
        "source_content": SAMPLE_SOURCE_CONTENT,
    }
    payload.update(overrides)
    resp = client.post(LISTINGS_URL, json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _generate(client, headers, listing_id=None, marketplaces=("US",)) -> str:
    payload = {**GENERATE_PAYLOAD, "listing_id": listing_id, "target_marketplaces": list(marketplaces)}
    resp = client.post(GENERATE_URL, json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["task_id"]


def _diff(client, headers, listing_id, task_id, marketplace="US"):
    return client.get(
        f"{LISTINGS_URL}/{listing_id}/diff",
        params={"task_id": task_id, "marketplace_id": marketplace},
        headers=headers,
    )


def _apply(client, headers, listing_id, body):
    return client.post(f"{LISTINGS_URL}/{listing_id}/apply", json=body, headers=headers)


def _all_fields(selected=True, **values):
    return [
        {"field": "title", "selected": selected, "value": values.get("title")},
        {"field": "bullets", "selected": selected, "value": values.get("bullets")},
        {"field": "description", "selected": selected, "value": values.get("description")},
        {"field": "search_terms", "selected": selected, "value": values.get("search_terms")},
    ]


# --------------------------------------------------------------------------- #
# diff
# --------------------------------------------------------------------------- #
def test_diff_requires_auth(client):
    assert client.get(f"{LISTINGS_URL}/1/diff?task_id=t&marketplace_id=US").status_code == 401


def test_diff_unknown_task_returns_404(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    resp = _diff(client, auth_headers, listing_id, "task-not-exist")
    assert resp.status_code == 404


def test_diff_unknown_listing_returns_404(client, auth_headers, patched_gateway):
    task_id = _generate(client, auth_headers)
    resp = _diff(client, auth_headers, 999999, task_id)
    assert resp.status_code == 404


def test_diff_uses_source_content_as_baseline(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    task_id = _generate(client, auth_headers, listing_id=listing_id)

    body = _diff(client, auth_headers, listing_id, task_id).json()
    assert body["current_source"] == "source_content"
    assert body["marketplace_id"] == "US"
    assert body["target_language"] == "en"
    assert body["generated_compliance_report"]["passed"] is True

    fields = {f["field"]: f for f in body["fields"]}
    assert set(fields) == {"title", "bullets", "description", "search_terms"}
    assert fields["title"]["current"] == SAMPLE_SOURCE_CONTENT["title"]
    assert fields["title"]["changed"] is True
    assert fields["bullets"]["current"] == SAMPLE_SOURCE_CONTENT["bullets"]
    assert fields["bullets"]["changed"] is True


def test_diff_rejects_unfinished_generation(client, auth_headers, db):
    listing_id = _create_listing(client, auth_headers)
    db.add(
        Generation(
            task_id="running-task",
            listing_id=listing_id,
            target_marketplace="US",
            target_language="en",
            status="running",
            result={},
        )
    )
    db.commit()

    resp = _diff(client, auth_headers, listing_id, "running-task")
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# apply
# --------------------------------------------------------------------------- #
def test_apply_all_fields_marks_copy_as_current(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    task_id = _generate(client, auth_headers, listing_id=listing_id)

    resp = _apply(
        client,
        auth_headers,
        listing_id,
        {"task_id": task_id, "marketplace_id": "US", "selections": _all_fields(True)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert sorted(body["applied_fields"]) == ["bullets", "description", "search_terms", "title"]
    assert body["skipped_fields"] == []
    assert body["spapi_synced"] is False
    assert body["content"]["title"].startswith("Wireless Bluetooth Headphones")

    after = _diff(client, auth_headers, listing_id, task_id).json()
    assert after["current_source"] == "listing_copy"
    assert all(f["changed"] is False for f in after["fields"])
    assert after["current_updated_at"] is not None


def test_apply_only_selected_fields_keeps_others(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    task_id = _generate(client, auth_headers, listing_id=listing_id)

    selections = _all_fields(False)
    selections[0]["selected"] = True  # 只回填 title
    resp = _apply(
        client,
        auth_headers,
        listing_id,
        {"task_id": task_id, "marketplace_id": "US", "selections": selections},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["applied_fields"] == ["title"]
    assert sorted(body["skipped_fields"]) == ["bullets", "description", "search_terms"]

    fields = {f["field"]: f for f in _diff(client, auth_headers, listing_id, task_id).json()["fields"]}
    assert fields["title"]["changed"] is False
    assert fields["bullets"]["changed"] is True
    assert fields["bullets"]["current"] == SAMPLE_SOURCE_CONTENT["bullets"]


def test_apply_supports_value_override(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    task_id = _generate(client, auth_headers, listing_id=listing_id)

    selections = _all_fields(False)
    selections[0]["selected"] = True
    selections[0]["value"] = "Manual Edited Title for Backfill"
    resp = _apply(
        client,
        auth_headers,
        listing_id,
        {"task_id": task_id, "marketplace_id": "US", "selections": selections},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"]["title"] == "Manual Edited Title for Backfill"


def test_apply_is_idempotent(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    task_id = _generate(client, auth_headers, listing_id=listing_id)
    payload = {"task_id": task_id, "marketplace_id": "US", "selections": _all_fields(True)}

    first = _apply(client, auth_headers, listing_id, payload)
    second = _apply(client, auth_headers, listing_id, payload)
    assert first.status_code == second.status_code == 200

    fields = {f["field"]: f for f in _diff(client, auth_headers, listing_id, task_id).json()["fields"]}
    assert all(f["changed"] is False for f in fields.values())


def test_apply_requires_at_least_one_field(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    task_id = _generate(client, auth_headers, listing_id=listing_id)
    resp = _apply(
        client,
        auth_headers,
        listing_id,
        {"task_id": task_id, "marketplace_id": "US", "selections": _all_fields(False)},
    )
    assert resp.status_code == 400


def test_apply_rejects_unsupported_field(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    task_id = _generate(client, auth_headers, listing_id=listing_id)
    resp = _apply(
        client,
        auth_headers,
        listing_id,
        {
            "task_id": task_id,
            "marketplace_id": "US",
            "selections": [{"field": "price", "selected": True}],
        },
    )
    assert resp.status_code == 400


def test_apply_unknown_task_returns_404(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    resp = _apply(
        client,
        auth_headers,
        listing_id,
        {"task_id": "task-not-exist", "marketplace_id": "US", "selections": _all_fields(True)},
    )
    assert resp.status_code == 404


def test_apply_blocks_compliance_violation_and_allows_force(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    task_id = _generate(client, auth_headers, listing_id=listing_id)

    selections = _all_fields(False)
    selections[0]["selected"] = True
    selections[0]["value"] = "Best Wireless Headphones with Free Shipping"
    # 但 description 为空会触发必填类规则，这里补上 description
    selections[2]["selected"] = True

    blocked = _apply(
        client,
        auth_headers,
        listing_id,
        {"task_id": task_id, "marketplace_id": "US", "selections": selections},
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == "compliance_failed"
    assert blocked.json()["details"]["passed"] is False

    forced = _apply(
        client,
        auth_headers,
        listing_id,
        {
            "task_id": task_id,
            "marketplace_id": "US",
            "selections": selections,
            "force": True,
        },
    )
    assert forced.status_code == 200, forced.text
    body = forced.json()
    assert body["forced"] is True
    assert body["compliance_report"]["passed"] is False
    assert body["content"]["title"] == "Best Wireless Headphones with Free Shipping"


def test_task_status_exposes_listing_id(client, auth_headers, patched_gateway):
    listing_id = _create_listing(client, auth_headers)
    task_id = _generate(client, auth_headers, listing_id=listing_id)
    body = client.get(f"/api/v1/generate/{task_id}", headers=auth_headers).json()
    assert body["listing_id"] == listing_id
