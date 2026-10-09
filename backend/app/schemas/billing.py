"""计费与订阅相关 Pydantic 模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PlanRead(BaseModel):
    code: str
    name: str
    price_monthly: float
    price_yearly: float
    price_per_month_yearly: float = 0.0
    monthly_quota: int
    features: list[str] = Field(default_factory=list)


class SubscribeRequest(BaseModel):
    plan: str  # basic | pro
    period: str = "monthly"  # monthly | yearly


class SubscribeResponse(BaseModel):
    order_created: bool
    plan: str
    period: str
    amount: float


class UsageRead(BaseModel):
    plan: str
    status: str
    quota_total: int
    quota_used: int
    quota_remaining: int
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
