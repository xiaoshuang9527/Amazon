"""订阅数据访问。"""

from typing import Optional

from sqlalchemy import select

from app.models.subscription import Subscription
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    def get_active_by_user(self, user_id: int) -> Optional[Subscription]:
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.status == "active")
            .order_by(Subscription.id.desc())
        )
        return self.db.execute(stmt).scalars().first()
