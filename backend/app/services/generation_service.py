"""生成任务编排服务。

主链路：产品信息输入 → 并行调用 LLM 生成多语言文案 → 合规校验 → 不合规自动重写 → 落库。
"""

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.constants import language_for_marketplace
from app.core.db import SessionLocal
from app.core.exceptions import NotFoundError, UpstreamError
from app.core.logging import get_logger
from app.models.generation import Generation
from app.models.listing import Listing
from app.repositories.generation_repo import GenerationRepository
from app.repositories.listing_repo import ListingRepository
from app.services.compliance_service import ComplianceService
from app.services.llm_service import LLMGateway, PromptRenderer, get_llm_gateway

logger = get_logger("app.generation")

TEMPLATES = [
    "listing_title.j2",
    "listing_bullets.j2",
    "listing_description.j2",
    "listing_search_terms.j2",
    "keyword_suggest.j2",
]


class GenerationService:
    def __init__(
        self,
        db: Session,
        gateway: Optional[LLMGateway] = None,
        compliance: Optional[ComplianceService] = None,
    ) -> None:
        self.db = db
        self.gateway = gateway or get_llm_gateway()
        self.compliance = compliance or ComplianceService()
        self.renderer = PromptRenderer()
        self.listings = ListingRepository(db)
        self.generations = GenerationRepository(db)

    # ------------------------------------------------------------------ #
    # 任务创建 / 查询
    # ------------------------------------------------------------------ #
    def create_task(self, payload: Dict[str, Any]) -> str:
        """落库 Listing 与占位 Generation 行，返回 task_id。"""
        source_content = payload.get("source_content") or {}
        listing_id = payload.get("listing_id")
        if listing_id:
            listing = self.listings.get(int(listing_id))
            if listing is None:
                raise NotFoundError("指定的 Listing 不存在")
        else:
            listing = Listing(
                shop_id=payload.get("shop_id"),
                asin=payload.get("asin"),
                sku=payload.get("sku"),
                marketplace_id=(payload.get("target_marketplaces") or [None])[0],
                source_language=payload.get("source_language", "zh"),
                source_content=source_content,
            )
            self.listings.add(listing)
            self.db.flush()

        task_id = uuid.uuid4().hex
        for marketplace in payload.get("target_marketplaces", []):
            lang = language_for_marketplace(marketplace)
            self.generations.add(
                Generation(
                    task_id=task_id,
                    listing_id=listing.id,
                    target_marketplace=marketplace,
                    target_language=lang,
                    status="pending",
                    result={},
                )
            )
        self.db.commit()
        return task_id

    def get_status(self, task_id: str) -> Dict[str, Any]:
        rows = self.generations.list_by_task(task_id)
        if not rows:
            raise NotFoundError("任务不存在")

        results: List[Dict[str, Any]] = []
        errors: List[str] = []
        statuses = {r.status for r in rows}
        for row in rows:
            if row.status == "failed":
                errors.append(f"{row.target_marketplace}: {row.result.get('error', '生成失败')}")
                continue
            if row.status == "success" and row.result:
                results.append(
                    {
                        "target_marketplace": row.target_marketplace,
                        "target_language": row.target_language,
                        "title": row.result.get("title", ""),
                        "bullets": row.result.get("bullets", []),
                        "description": row.result.get("description", ""),
                        "search_terms": row.result.get("search_terms", ""),
                        "suggested_keywords": row.result.get("suggested_keywords", []),
                        "compliance_report": row.result.get(
                            "compliance_report", {"passed": True, "violations": []}
                        ),
                        "model_used": row.model_used,
                    }
                )

        if statuses <= {"success"}:
            overall = "success"
        elif statuses <= {"failed"}:
            overall = "failed"
        elif statuses & {"running", "pending"}:
            overall = "running" if "running" in statuses else "pending"
        else:
            overall = "partial"

        created = rows[0].created_at if rows else None
        return {
            "task_id": task_id,
            "status": overall,
            "listing_id": next((r.listing_id for r in rows if r.listing_id), None),
            "results": results,
            "errors": errors,
            "created_at": created,
        }

    # ------------------------------------------------------------------ #
    # 核心生成
    # ------------------------------------------------------------------ #
    async def _generate_marketplace(
        self,
        marketplace: str,
        source_content: Dict[str, Any],
        category: str,
        tone: str,
        quality: str,
        extra_note: str = "",
        allow_rewrite: bool = True,
    ) -> Dict[str, Any]:
        """为单个站点生成完整文案。"""
        product_info = dict(source_content)
        if extra_note:
            product_info["_compliance_note"] = extra_note

        variables = self.renderer.build_variables(
            product_info=product_info,
            target_marketplace=marketplace,
            target_language=language_for_marketplace(marketplace),
            category=category,
            keywords=source_content.get("keywords", []),
            tone=tone,
        )

        async def _call(template: str):
            return await self.gateway.generate_json(template, variables, quality=quality)

        responses = await asyncio.gather(
            *(_call(t) for t in TEMPLATES), return_exceptions=True
        )

        merged: Dict[str, Any] = {
            "title": "",
            "bullets": [],
            "description": "",
            "search_terms": "",
            "suggested_keywords": [],
        }
        input_tokens = output_tokens = 0
        cost = 0.0
        model_used = ""
        errors: List[str] = []

        for template, resp in zip(TEMPLATES, responses):
            if isinstance(resp, BaseException):
                errors.append(f"{template}: {resp}")
                continue
            data = resp.as_json()
            input_tokens += resp.input_tokens
            output_tokens += resp.output_tokens
            cost += resp.cost_usd
            model_used = resp.model or model_used
            if template == "listing_title.j2":
                merged["title"] = data.get("title", "")
            elif template == "listing_bullets.j2":
                merged["bullets"] = data.get("bullets", [])
            elif template == "listing_description.j2":
                merged["description"] = data.get("description", "")
            elif template == "listing_search_terms.j2":
                merged["search_terms"] = data.get("search_terms", "")
            elif template == "keyword_suggest.j2":
                merged["suggested_keywords"] = data.get("suggested_keywords", [])

        if errors and not merged["title"]:
            raise UpstreamError("LLM 生成失败: " + "; ".join(errors))

        # 合规校验
        report = self.compliance.validate(
            marketplace_id=marketplace,
            category=category,
            title=merged["title"],
            bullets=merged["bullets"],
            description=merged["description"],
            search_terms=merged["search_terms"],
        )

        # 不合规自动重写（严格最多 1 次：重写轮不允许再次重写）
        if not report["passed"] and allow_rewrite:
            banned = sorted({v["word"] for v in report["violations"] if v.get("word")})
            note = (
                "上一次生成命中违禁词：" + "、".join(banned) + "。请改用客观表述，务必避开这些词。"
                if banned
                else "上一次生成存在超长字段，请压缩长度并保持信息完整。"
            )
            try:
                retry_data = await self._generate_marketplace(
                    marketplace,
                    source_content,
                    category,
                    tone,
                    quality,
                    extra_note=note,
                    allow_rewrite=False,
                )
                if retry_data["compliance_report"]["passed"]:
                    retry_data["input_tokens"] += input_tokens
                    retry_data["output_tokens"] += output_tokens
                    retry_data["cost_usd"] += cost
                    return retry_data
            except UpstreamError as exc:
                logger.warning("重写失败，保留首次结果", extra={"error": str(exc)})

        merged["compliance_report"] = report
        merged.update(
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost,
                "model_used": model_used,
            }
        )
        return merged

    async def generate_all(
        self,
        marketplaces: List[str],
        source_content: Dict[str, Any],
        category: str,
        tone: str,
        quality: str,
    ) -> Dict[str, Dict[str, Any]]:
        """并行生成多个站点的文案。"""
        tasks = [
            self._generate_marketplace(m, source_content, category, tone, quality)
            for m in marketplaces
        ]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        result: Dict[str, Dict[str, Any]] = {}
        for marketplace, outcome in zip(marketplaces, outcomes):
            if isinstance(outcome, BaseException):
                result[marketplace] = {"error": str(outcome)}
            else:
                result[marketplace] = outcome
        return result

    def persist_results(self, task_id: str, outcomes: Dict[str, Dict[str, Any]]) -> None:
        """把生成结果写回 Generation 行。"""
        rows = {r.target_marketplace: r for r in self.generations.list_by_task(task_id)}
        for marketplace, outcome in outcomes.items():
            row = rows.get(marketplace)
            if row is None:
                continue
            if "error" in outcome:
                row.status = "failed"
                row.result = {"error": outcome["error"]}
                continue
            row.status = "success"
            row.model_used = outcome.get("model_used", "")
            row.input_tokens = int(outcome.get("input_tokens", 0))
            row.output_tokens = int(outcome.get("output_tokens", 0))
            row.cost_usd = float(outcome.get("cost_usd", 0.0))
            row.result = {
                "title": outcome.get("title", ""),
                "bullets": outcome.get("bullets", []),
                "description": outcome.get("description", ""),
                "search_terms": outcome.get("search_terms", ""),
                "suggested_keywords": outcome.get("suggested_keywords", []),
                "compliance_report": outcome.get("compliance_report", {"passed": True, "violations": []}),
            }
        self.db.commit()

    def mark_running(self, task_id: str) -> None:
        for row in self.generations.list_by_task(task_id):
            if row.status == "pending":
                row.status = "running"
        self.db.commit()


def execute_generation_task(task_id: str, payload: Dict[str, Any]) -> None:
    """后台任务入口：使用独立会话执行完整生成流程。"""
    db = SessionLocal()
    try:
        service = GenerationService(db)
        service.mark_running(task_id)
        outcomes = asyncio.run(
            service.generate_all(
                marketplaces=payload.get("target_marketplaces", []),
                source_content=payload.get("source_content", {}),
                category=payload.get("category", "*"),
                tone=payload.get("tone", "professional"),
                quality=payload.get("quality", "standard"),
            )
        )
        service.persist_results(task_id, outcomes)
    except Exception as exc:  # noqa: BLE001 - 后台任务需兜底记录
        logger.exception("生成任务执行失败", extra={"task_id": task_id})
        try:
            for row in GenerationRepository(db).list_by_task(task_id):
                if row.status != "success":
                    row.status = "failed"
                    row.result = {"error": str(exc)}
            db.commit()
        except Exception:  # pragma: no cover
            db.rollback()
    finally:
        db.close()
