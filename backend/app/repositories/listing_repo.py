"""Listing 数据访问。"""

from typing import List, Optional

from sqlalchemy import select

from app.models.listing import Listing
from app.repositories.base import BaseRepository


class ListingRepository(BaseRepository[Listing]):
    model = Listing

    def list_by_shop(self, shop_id: int) -> List[Listing]:
        stmt = select(Listing).where(Listing.shop_id == shop_id).order_by(Listing.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_by_unique(self, shop_id: int, asin: str, marketplace_id: str) -> Optional[Listing]:
        stmt = select(Listing).where(
            Listing.shop_id == shop_id,
            Listing.asin == asin,
            Listing.marketplace_id == marketplace_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()
