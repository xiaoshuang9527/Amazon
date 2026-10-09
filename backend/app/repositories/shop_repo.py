"""店铺数据访问。"""

from typing import List, Optional

from sqlalchemy import select

from app.models.shop import Shop
from app.repositories.base import BaseRepository


class ShopRepository(BaseRepository[Shop]):
    model = Shop

    def list_by_user(self, user_id: int) -> List[Shop]:
        stmt = select(Shop).where(Shop.user_id == user_id).order_by(Shop.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_by_seller(self, user_id: int, seller_id: str) -> Optional[Shop]:
        stmt = select(Shop).where(Shop.user_id == user_id, Shop.seller_id == seller_id)
        return self.db.execute(stmt).scalar_one_or_none()
