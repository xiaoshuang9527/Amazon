"""计费与订阅路由。"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.billing import (
    PlanRead,
    SubscribeRequest,
    SubscribeResponse,
    UsageRead,
)
from app.services.billing_service import BillingService

router = APIRouter()
logger = get_logger("app.billing")


@router.get("/plans", response_model=list[PlanRead], summary="套餐列表")
def plans() -> list[dict]:
    return BillingService.list_plans()


@router.post("/subscribe", response_model=SubscribeResponse, summary="创建订单/开通套餐")
def subscribe(
    payload: SubscribeRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> SubscribeResponse:
    result = BillingService(db).subscribe(current.id, payload.plan, payload.period)
    return SubscribeResponse(**result)


@router.get("/usage", response_model=UsageRead, summary="当前用量")
def usage(
    current: User = Depends(get_current_user), db: Session = Depends(get_session)
) -> UsageRead:
    return UsageRead(**BillingService(db).get_usage(current.id))


@router.post("/webhook", summary="支付回调（预留）")
async def webhook(request: Request) -> dict:
    body = await request.json()
    logger.info("收到支付回调（MVP 未启用验签）", extra={"body": body})
    return {"received": True}
