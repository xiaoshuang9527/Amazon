"""计费与订阅服务（MVP 支持手动开通 + 配额扣减）。"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import QuotaExceededError
from app.models.subscription import Subscription
from app.repositories.subscription_repo import SubscriptionRepository

PLANS: List[Dict[str, Any]] = [
    {
        "code": "free",
        "name": "免费版",
        "price_monthly": 0.0,
        "price_yearly": 0.0,
        "monthly_quota": settings.FREE_MONTHLY_QUOTA,
        "features": ["每月 3 条 Listing 生成", "基础导出"],
    },
    {
        "code": "basic",
        "name": "基础版",
        "price_monthly": 199.0,
        "price_yearly": 1999.0,
        "monthly_quota": settings.BASIC_MONTHLY_QUOTA,
        "features": ["50 条/月", "单店铺", "xlsx / json / csv 导出"],
    },
    {
        "code": "pro",
        "name": "专业版",
        "price_monthly": 399.0,
        "price_yearly": 3999.0,
        "monthly_quota": settings.PRO_MONTHLY_QUOTA,
        "features": ["200 条/月", "多店铺", "高质量模型", "优先支持"],
    },
]

PLAN_BY_CODE = {p["code"]: p for p in PLANS}


class BillingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SubscriptionRepository(db)

    def ensure_subscription(self, user_id: int) -> Subscription:
        """确保用户存在一条订阅记录，默认免费版。"""
        sub = self.repo.get_active_by_user(user_id)
        if sub is None:
            now = datetime.now(timezone.utc)
            sub = Subscription(
                user_id=user_id,
                plan="free",
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=365),
                quota_used=0,
            )
            self.repo.add(sub)
            self.db.commit()
        return sub

    @staticmethod
    def list_plans() -> List[Dict[str, Any]]:
        plans = []
        for plan in PLANS:
            item = dict(plan)
            item["price_per_month_yearly"] = round(plan["price_yearly"] / 12, 2)
            plans.append(item)
        return plans

    def check_and_consume(self, user_id: int, amount: int = 1) -> Subscription:
        """生成任务前检查配额并扣减；不足抛 402。"""
        sub = self.ensure_subscription(user_id)
        quota = PLAN_BY_CODE.get(sub.plan, PLAN_BY_CODE["free"])["monthly_quota"]
        if sub.quota_used + amount > quota:
            raise QuotaExceededError(
                f"本月额度不足（已用 {sub.quota_used}/{quota}），请升级套餐"
            )
        sub.quota_used += amount
        self.db.commit()
        return sub

    def get_usage(self, user_id: int) -> Dict[str, Any]:
        sub = self.ensure_subscription(user_id)
        quota = PLAN_BY_CODE.get(sub.plan, PLAN_BY_CODE["free"])["monthly_quota"]
        return {
            "plan": sub.plan,
            "status": sub.status,
            "quota_total": quota,
            "quota_used": sub.quota_used,
            "quota_remaining": max(quota - sub.quota_used, 0),
            "current_period_start": sub.current_period_start,
            "current_period_end": sub.current_period_end,
        }

    def subscribe(self, user_id: int, plan: str, period: str = "monthly") -> Dict[str, Any]:
        """创建订单（MVP：直接开通，支付二期接入）。"""
        if plan not in PLAN_BY_CODE or plan == "free":
            raise QuotaExceededError("无效的套餐，仅支持 basic / pro")
        sub = self.ensure_subscription(user_id)
        now = datetime.now(timezone.utc)
        sub.plan = plan
        sub.status = "active"
        sub.quota_used = 0
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=365 if period == "yearly" else 30)
        self.db.commit()
        price = (
            PLAN_BY_CODE[plan]["price_yearly"]
            if period == "yearly"
            else PLAN_BY_CODE[plan]["price_monthly"]
        )
        return {"order_created": True, "plan": plan, "period": period, "amount": price}
