"""回填服务：读取当前 Listing 文案 → 与生成结果做字段级 diff → 用户确认后提交。

MVP 约束：
- 不调用 SP-API 完成真实刊登，确认后把文案落库为"当前 Listing 文案"（ListingCopy）；
- 提交前对合并后的文案再做一次合规校验，未通过时默认拒绝，需显式 force 才能强制提交；
- diff 基准优先取上次回填结果，其次取 Listing 原始信息（source_content）。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ComplianceError, NotFoundError
from app.models.generation import Generation
from app.models.listing import Listing
from app.models.listing_copy import ListingCopy
from app.repositories.generation_repo import GenerationRepository
from app.repositories.listing_copy_repo import ListingCopyRepository
from app.schemas.backfill import ApplyRequest
from app.services.compliance_service import ComplianceService

FIELD_LABELS: Dict[str, str] = {
    "title": "标题",
    "bullets": "五点描述",
    "description": "长描述",
    "search_terms": "搜索词",
}
SUPPORTED_FIELDS: Tuple[str, ...] = tuple(FIELD_LABELS)
LIST_FIELDS = ("bullets",)


def _empty(field: str) -> Any:
    return [] if field in LIST_FIELDS else ""


def _normalize(field: str, value: Any) -> Any:
    """归一化后再比较，避免空白/换行差异导致误报。"""
    if field in LIST_FIELDS:
        if not isinstance(value, list):
            value = [value] if value else []
        return [str(item).strip() for item in value if str(item).strip()]
    return str(value or "").strip()


def _coerce(field: str, value: Any) -> Any:
    if field in LIST_FIELDS:
        if value is None:
            return []
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        return [str(item).strip() for item in value if str(item).strip()]
    return "" if value is None else str(value)


class BackfillService:
    def __init__(self, db: Session, compliance: ComplianceService | None = None) -> None:
        self.db = db
        self.copies = ListingCopyRepository(db)
        self.generations = GenerationRepository(db)
        self.compliance = compliance or ComplianceService()

    # ------------------------------------------------------------------ #
    # 内部工具
    # ------------------------------------------------------------------ #
    def _get_generation(self, task_id: str, marketplace_id: str) -> Generation:
        row = self.generations.get_by_task_market(task_id, marketplace_id)
        if row is None:
            raise NotFoundError("未找到该任务对应站点的生成结果")
        if row.status != "success" or not row.result:
            raise AppError("该站点文案尚未生成完成，暂不可回填")
        return row

    def _current_content(
        self, listing: Listing, marketplace_id: str
    ) -> Tuple[Dict[str, Any], str, Any]:
        copy = self.copies.get_by_listing_market(listing.id, marketplace_id)
        if copy is not None:
            return dict(copy.content or {}), "listing_copy", copy.updated_at
        source = listing.source_content or {}
        search_terms = source.get("search_terms") or ", ".join(source.get("keywords", []) or [])
        return (
            {
                "title": source.get("title", ""),
                "bullets": list(source.get("bullets", []) or []),
                "description": source.get("description", ""),
                "search_terms": search_terms,
            },
            "source_content",
            None,
        )

    @staticmethod
    def _proposed(row: Generation) -> Dict[str, Any]:
        result = row.result or {}
        return {field: result.get(field, _empty(field)) for field in SUPPORTED_FIELDS}

    # ------------------------------------------------------------------ #
    # diff
    # ------------------------------------------------------------------ #
    def build_diff(self, listing: Listing, task_id: str, marketplace_id: str) -> Dict[str, Any]:
        row = self._get_generation(task_id, marketplace_id)
        current, source, updated_at = self._current_content(listing, marketplace_id)
        proposed = self._proposed(row)

        fields: List[Dict[str, Any]] = []
        for field in SUPPORTED_FIELDS:
            old_value = current.get(field, _empty(field))
            new_value = proposed.get(field, _empty(field))
            fields.append(
                {
                    "field": field,
                    "label": FIELD_LABELS[field],
                    "current": old_value,
                    "proposed": new_value,
                    "changed": _normalize(field, old_value) != _normalize(field, new_value),
                    "editable": True,
                }
            )

        return {
            "listing_id": listing.id,
            "marketplace_id": marketplace_id,
            "task_id": task_id,
            "current_source": source,
            "current_updated_at": updated_at,
            "model_used": row.model_used,
            "target_language": row.target_language,
            "generated_compliance_report": row.result.get(
                "compliance_report", {"passed": True, "violations": []}
            ),
            "fields": fields,
        }

    # ------------------------------------------------------------------ #
    # apply
    # ------------------------------------------------------------------ #
    def apply(self, listing: Listing, payload: ApplyRequest) -> Dict[str, Any]:
        marketplace_id = payload.marketplace_id.upper()
        row = self._get_generation(payload.task_id, marketplace_id)
        current, _, _ = self._current_content(listing, marketplace_id)
        proposed = self._proposed(row)

        merged = {field: current.get(field, _empty(field)) for field in SUPPORTED_FIELDS}
        applied: List[str] = []
        skipped: List[str] = []
        seen: set[str] = set()

        for selection in payload.selections:
            field = selection.field
            if field not in SUPPORTED_FIELDS:
                raise AppError(f"不支持的字段: {field}")
            if field in seen:
                continue
            seen.add(field)
            if not selection.selected:
                skipped.append(field)
                continue
            source_value = proposed.get(field) if selection.value is None else selection.value
            merged[field] = _coerce(field, source_value)
            applied.append(field)

        if not applied:
            raise AppError("请至少勾选一个需要回填的字段")

        report = self.compliance.validate(
            marketplace_id=marketplace_id,
            category="*",
            title=merged["title"],
            bullets=merged["bullets"],
            description=merged["description"],
            search_terms=merged["search_terms"],
        )
        if not report["passed"] and not payload.force:
            raise ComplianceError("回填内容未通过合规校验，请修正后重试", details=report)

        now = datetime.now(timezone.utc)
        copy = self.copies.get_by_listing_market(listing.id, marketplace_id)
        if copy is None:
            copy = ListingCopy(
                listing_id=listing.id,
                marketplace_id=marketplace_id,
                task_id=payload.task_id,
                content=merged,
                applied_fields=applied,
                applied_at=now,
            )
            self.copies.add(copy)
        else:
            copy.task_id = payload.task_id
            copy.content = merged
            copy.applied_fields = applied
            copy.applied_at = now
        self.db.commit()
        self.db.refresh(copy)

        return {
            "listing_id": listing.id,
            "marketplace_id": marketplace_id,
            "task_id": payload.task_id,
            "applied_fields": applied,
            "skipped_fields": skipped,
            "compliance_report": report,
            "forced": bool(payload.force and not report["passed"]),
            "spapi_synced": False,
            "message": "MVP 阶段未接入 SP-API，文案已落库为当前 Listing 文案",
            "applied_at": copy.applied_at,
            "content": dict(copy.content or {}),
        }
