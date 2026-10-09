"""生成任务编排测试：建任务 → 并行生成 → 合规校验 → 自动重写 → 落库。"""

import asyncio

import pytest
from conftest import SAMPLE_SOURCE_CONTENT, SequencedLLMGateway

from app.core.exceptions import NotFoundError
from app.repositories.generation_repo import GenerationRepository
from app.repositories.listing_repo import ListingRepository
from app.services.generation_service import GenerationService, execute_generation_task

BASE_PAYLOAD = {
    "shop_id": None,
    "source_content": SAMPLE_SOURCE_CONTENT,
    "target_marketplaces": ["US", "DE"],
    "source_language": "zh",
}


class _BrokenGateway:
    """所有模板都抛错的假网关。"""

    async def generate_json(self, template_name, variables, *, quality="standard"):
        raise RuntimeError("provider down")


def _service(db, gateway) -> GenerationService:
    return GenerationService(db, gateway=gateway)


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# 任务创建与查询
# --------------------------------------------------------------------------- #
def test_create_task_persists_listing_and_placeholder_rows(db, fake_gateway):
    service = _service(db, fake_gateway)
    task_id = service.create_task(dict(BASE_PAYLOAD))

    rows = GenerationRepository(db).list_by_task(task_id)
    assert len(rows) == 2
    assert [r.status for r in rows] == ["pending", "pending"]
    assert [r.target_marketplace for r in rows] == ["US", "DE"]
    assert [r.target_language for r in rows] == ["en", "de"]

    listing = ListingRepository(db).get(rows[0].listing_id)
    assert listing is not None
    assert listing.source_content["title"] == SAMPLE_SOURCE_CONTENT["title"]


def test_create_task_uses_existing_listing(db, fake_gateway):
    from app.models.listing import Listing

    repo = ListingRepository(db)
    listing = repo.add(
        Listing(
            shop_id=None,
            asin="B0EXIST001",
            sku="SKU-EXIST",
            marketplace_id="US",
            source_language="zh",
            source_content=SAMPLE_SOURCE_CONTENT,
        )
    )
    repo.commit()

    service = _service(db, fake_gateway)
    task_id = service.create_task({**BASE_PAYLOAD, "listing_id": listing.id, "target_marketplaces": ["US"]})
    rows = GenerationRepository(db).list_by_task(task_id)
    assert len(rows) == 1
    assert rows[0].listing_id == listing.id


def test_create_task_with_missing_listing_raises(db, fake_gateway):
    service = _service(db, fake_gateway)
    with pytest.raises(NotFoundError):
        service.create_task({**BASE_PAYLOAD, "listing_id": 999999})


def test_get_status_raises_for_unknown_task(db, fake_gateway):
    with pytest.raises(NotFoundError):
        _service(db, fake_gateway).get_status("task-not-exist")


def test_mark_running_moves_pending_rows(db, fake_gateway):
    service = _service(db, fake_gateway)
    task_id = service.create_task(dict(BASE_PAYLOAD))
    service.mark_running(task_id)
    assert {r.status for r in GenerationRepository(db).list_by_task(task_id)} == {"running"}


# --------------------------------------------------------------------------- #
# 生成链路
# --------------------------------------------------------------------------- #
def test_generate_all_returns_full_listing_per_marketplace(db, fake_gateway):
    service = _service(db, fake_gateway)
    outcomes = _run(
        service.generate_all(
            ["US", "DE"], SAMPLE_SOURCE_CONTENT, "Electronics", "professional", "standard"
        )
    )

    assert set(outcomes) == {"US", "DE"}
    for marketplace in ("US", "DE"):
        item = outcomes[marketplace]
        assert item["title"]
        assert len(item["bullets"]) == 5
        assert item["description"]
        assert item["search_terms"]
        assert item["suggested_keywords"]
        assert item["compliance_report"]["passed"] is True
        assert item["compliance_report"]["violations"] == []
        assert item["input_tokens"] > 0 and item["output_tokens"] > 0
        # 五个模板都被调用了一次
    assert len(fake_gateway.calls) == 10


def test_generate_uses_target_language_in_prompt_variables(db, fake_gateway):
    service = _service(db, fake_gateway)
    _run(service.generate_all(["JP"], SAMPLE_SOURCE_CONTENT, "Electronics", "friendly", "high"))

    variables = fake_gateway.calls[0]["variables"]
    assert variables["target_marketplace"] == "JP"
    assert variables["target_language"] == "ja"
    assert variables["tone"] == "friendly"
    assert fake_gateway.calls[0]["quality"] == "high"


def test_high_quality_mode_is_passed_to_gateway(db, fake_gateway):
    service = _service(db, fake_gateway)
    _run(service.generate_all(["US"], SAMPLE_SOURCE_CONTENT, "*", "professional", "high"))
    assert {c["quality"] for c in fake_gateway.calls} == {"high"}


def test_end_to_end_persist_and_read_status(db, fake_gateway):
    service = _service(db, fake_gateway)
    task_id = service.create_task(dict(BASE_PAYLOAD))
    service.mark_running(task_id)

    outcomes = _run(
        service.generate_all(
            ["US", "DE"], SAMPLE_SOURCE_CONTENT, "Electronics", "professional", "standard"
        )
    )
    service.persist_results(task_id, outcomes)

    status = service.get_status(task_id)
    assert status["status"] == "success"
    assert status["errors"] == []
    assert {r["target_marketplace"] for r in status["results"]} == {"US", "DE"}
    row = GenerationRepository(db).get_latest(task_id, "en")
    assert row.status == "success"
    assert row.cost_usd > 0
    assert row.result["title"]


# --------------------------------------------------------------------------- #
# 自动重写
# --------------------------------------------------------------------------- #
def test_violation_triggers_single_rewrite(db):
    gateway = SequencedLLMGateway(violating_rounds=1)
    service = _service(db, gateway)

    outcomes = _run(
        service.generate_all(["US"], SAMPLE_SOURCE_CONTENT, "Electronics", "professional", "standard")
    )
    item = outcomes["US"]

    assert gateway.title_calls == 2  # 首轮违规 + 1 次重写
    assert item["compliance_report"]["passed"] is True
    assert "best" not in item["title"].lower()
    # 重写时把违规词提示传给了下一轮 Prompt
    retry_call = [c for c in gateway.calls if "_compliance_note" in c["variables"]["product_info"]]
    assert retry_call, gateway.calls


def test_rewrite_limited_to_one_attempt(db):
    gateway = SequencedLLMGateway(violating_rounds=99)
    service = _service(db, gateway)

    outcomes = _run(
        service.generate_all(["US"], SAMPLE_SOURCE_CONTENT, "Electronics", "professional", "standard")
    )
    item = outcomes["US"]

    assert gateway.title_calls == 2  # 严格只重写一次，不再递归
    assert item["compliance_report"]["passed"] is False
    assert item["compliance_report"]["violations"]


# --------------------------------------------------------------------------- #
# 异常路径
# --------------------------------------------------------------------------- #
def test_provider_failure_is_recorded_as_error(db):
    service = _service(db, _BrokenGateway())
    outcomes = _run(
        service.generate_all(["US"], SAMPLE_SOURCE_CONTENT, "Electronics", "professional", "standard")
    )
    assert "provider down" in outcomes["US"]["error"]


def test_persist_results_marks_failed_rows(db):
    service = _service(db, _BrokenGateway())
    task_id = service.create_task({**BASE_PAYLOAD, "target_marketplaces": ["US"]})
    outcomes = _run(
        service.generate_all(["US"], SAMPLE_SOURCE_CONTENT, "Electronics", "professional", "standard")
    )
    service.persist_results(task_id, outcomes)

    row = GenerationRepository(db).list_by_task(task_id)[0]
    assert row.status == "failed"
    assert "provider down" in row.result["error"]
    assert service.get_status(task_id)["status"] == "failed"


def test_execute_generation_task_runs_full_pipeline(db, patched_gateway):
    """后台任务入口：独立会话执行完整流程。"""
    service = _service(db, patched_gateway)
    task_id = service.create_task({**BASE_PAYLOAD, "target_marketplaces": ["US", "DE"]})
    db.rollback()

    execute_generation_task(
        task_id,
        {
            "target_marketplaces": ["US", "DE"],
            "source_content": SAMPLE_SOURCE_CONTENT,
            "category": "Electronics",
            "tone": "professional",
            "quality": "standard",
        },
    )

    db.rollback()
    status = _service(db, patched_gateway).get_status(task_id)
    assert status["status"] == "success"
    assert len(status["results"]) == 2
