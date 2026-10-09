"""Listing 回填副本数据访问。"""

from typing import List, Optional

from sqlalchemy import select

from app.models.listing_copy import ListingCopy
from app.repositories.base import BaseRepository


class ListingCopyRepository(BaseRepository[ListingCopy]):
    model = ListingCopy

    def get_by_listing_market(
        self, listing_id: int, marketplace_id: str
    ) -> Optional[ListingCopy]:
        stmt = select(ListingCopy).where(
            ListingCopy.listing_id == listing_id,
            ListingCopy.marketplace_id == marketplace_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_listing(self, listing_id: int) -> List[ListingCopy]:
        stmt = (
            select(ListingCopy)
            .where(ListingCopy.listing_id == listing_id)
            .order_by(ListingCopy.id.asc())
        )
        return list(self.db.execute(stmt).scalars().all())
