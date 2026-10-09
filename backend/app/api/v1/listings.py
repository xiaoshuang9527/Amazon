"""Listing 路由：创建、查询、合规校验、回填（diff / apply）。"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.exceptions import NotFoundError
from app.models.listing import Listing
from app.models.user import User
from app.repositories.listing_repo import ListingRepository
from app.schemas.backfill import ApplyRequest, ApplyResponse, ListingDiffResponse
from app.schemas.listing import ListingCreate, ListingRead, ValidateRequest, ValidateResponse
from app.services.backfill_service import BackfillService
from app.services.compliance_service import ComplianceService

router = APIRouter()


def _get_listing_or_404(db: Session, listing_id: int) -> Listing:
    listing = ListingRepository(db).get(listing_id)
    if listing is None:
        raise NotFoundError("Listing 不存在")
    return listing


@router.post("", response_model=ListingRead, summary="创建 Listing（手动输入产品信息）")
def create_listing(
    payload: ListingCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Listing:
    repo = ListingRepository(db)
    listing = Listing(
        shop_id=payload.shop_id,
        asin=payload.asin,
        sku=payload.sku,
        marketplace_id=payload.marketplace_id,
        source_language=payload.source_language,
        source_content=payload.source_content.model_dump(),
    )
    repo.add(listing)
    repo.commit()
    return listing


@router.get("", response_model=List[ListingRead], summary="Listing 列表")
def list_listings(
    shop_id: int | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> List[Listing]:
    repo = ListingRepository(db)
    if shop_id is not None:
        return repo.list_by_shop(shop_id)
    return repo.list(limit=200)


@router.get("/{listing_id}", response_model=ListingRead, summary="Listing 详情")
def get_listing(
    listing_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Listing:
    return _get_listing_or_404(db, listing_id)


@router.get(
    "/{listing_id}/diff",
    response_model=ListingDiffResponse,
    summary="当前 Listing 文案与生成结果的字段级差异",
)
def listing_diff(
    listing_id: int,
    task_id: str = Query(..., description="生成任务 ID"),
    marketplace_id: str = Query(..., description="目标站点，如 US"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ListingDiffResponse:
    listing = _get_listing_or_404(db, listing_id)
    data = BackfillService(db).build_diff(
        listing, task_id=task_id, marketplace_id=marketplace_id.upper()
    )
    return ListingDiffResponse(**data)


@router.post(
    "/{listing_id}/apply",
    response_model=ApplyResponse,
    summary="确认回填：提交用户勾选的字段",
)
def apply_listing(
    listing_id: int,
    payload: ApplyRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ApplyResponse:
    listing = _get_listing_or_404(db, listing_id)
    data = BackfillService(db).apply(listing, payload)
    return ApplyResponse(**data)


@router.post("/validate", response_model=ValidateResponse, summary="合规校验")
def validate(
    payload: ValidateRequest, current: User = Depends(get_current_user)
) -> ValidateResponse:
    service = ComplianceService()
    report = service.validate(
        marketplace_id=payload.marketplace_id,
        category=payload.category,
        title=payload.title,
        bullets=payload.bullets,
        description=payload.description,
        search_terms=payload.search_terms,
        brand_words=payload.brand_words,
    )
    return ValidateResponse(**report)
