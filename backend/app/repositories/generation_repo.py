"""生成记录数据访问。"""

from typing import List, Optional

from sqlalchemy import select

from app.models.generation import Generation
from app.repositories.base import BaseRepository


class GenerationRepository(BaseRepository[Generation]):
    model = Generation

    def list_by_task(self, task_id: str) -> List[Generation]:
        stmt = (
            select(Generation)
            .where(Generation.task_id == task_id)
            .order_by(Generation.id.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_listing(self, listing_id: int) -> List[Generation]:
        stmt = (
            select(Generation)
            .where(Generation.listing_id == listing_id)
            .order_by(Generation.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_task_market(self, task_id: str, marketplace_id: str) -> Optional[Generation]:
        stmt = (
            select(Generation)
            .where(
                Generation.task_id == task_id,
                Generation.target_marketplace == marketplace_id,
            )
            .order_by(Generation.id.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def get_latest(self, task_id: str, target_language: str) -> Optional[Generation]:
        stmt = (
            select(Generation)
            .where(Generation.task_id == task_id, Generation.target_language == target_language)
            .order_by(Generation.id.desc())
        )
        return self.db.execute(stmt).scalars().first()
