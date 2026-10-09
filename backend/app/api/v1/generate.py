"""文案生成与导出路由。"""

import os
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.config import settings
from app.core.constants import SUPPORTED_MARKETPLACES, language_for_marketplace
from app.core.exceptions import AppError, NotFoundError
from app.models.user import User
from app.repositories.generation_repo import GenerationRepository
from app.schemas.generation import (
    GenerateRequest,
    GenerationRead,
    GenerateTaskResponse,
    TaskStatusResponse,
)
from app.services.billing_service import BillingService
from app.services.export_service import export
from app.services.generation_service import (
    GenerationService,
    execute_generation_task,
)

router = APIRouter()

EXPORT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "exports")
)


@router.post("/listing", response_model=GenerateTaskResponse, summary="提交多语言生成任务")
def generate_listing(
    payload: GenerateRequest,
    background: BackgroundTasks,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> GenerateTaskResponse:
    marketplaces = [m.upper() for m in payload.target_marketplaces]
    if not marketplaces:
        raise AppError("请至少选择一个目标站点")
    invalid = [m for m in marketplaces if m not in SUPPORTED_MARKETPLACES]
    if invalid:
        raise AppError(f"暂不支持的站点: {', '.join(invalid)}")

    # 配额检查与扣减
    BillingService(db).check_and_consume(current.id, amount=1)

    service = GenerationService(db)
    task_id = service.create_task(
        {
            "listing_id": payload.listing_id,
            "shop_id": payload.shop_id,
            "source_content": payload.source_content.model_dump(),
            "target_marketplaces": marketplaces,
            "source_language": "zh",
        }
    )

    background.add_task(
        execute_generation_task,
        task_id,
        {
            "target_marketplaces": marketplaces,
            "source_content": payload.source_content.model_dump(),
            "category": payload.category,
            "tone": payload.tone,
            "quality": payload.quality,
        },
    )
    return GenerateTaskResponse(task_id=task_id)


@router.get("/history", response_model=List[GenerationRead], summary="生成历史")
def history(
    limit: int = Query(default=50, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> List[GenerationRead]:
    rows = GenerationRepository(db).list(limit=limit)
    return [GenerationRead.model_validate(r) for r in rows]


@router.get("/{task_id}", response_model=TaskStatusResponse, summary="查询任务状态")
def task_status(
    task_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> TaskStatusResponse:
    service = GenerationService(db)
    data = service.get_status(task_id)
    return TaskStatusResponse(**data)


@router.get("/{task_id}/export", summary="导出结果（xlsx / json / csv）")
def export_task(
    task_id: str,
    format: str = Query(default="xlsx", pattern="^(xlsx|json|csv)$"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    service = GenerationService(db)
    data = service.get_status(task_id)
    if not data["results"]:
        raise NotFoundError("该任务暂无可导出的结果")
    rows = [
        {"target_marketplace": r.target_marketplace, "sku": r.result.get("sku")}
        for r in GenerationRepository(db).list_by_task(task_id)
    ]
    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = export(format, task_id, data["results"], rows, EXPORT_DIR)
    media = {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
        "json": "application/json",
    }[format]
    return FileResponse(path, media_type=media, filename=os.path.basename(path))
