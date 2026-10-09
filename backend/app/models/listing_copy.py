"""Listing 回填副本模型：记录 (Listing, 站点) 最近一次确认回填的文案。

MVP 阶段不调用 SP-API，用户确认回填后先把文案落库为"当前 Listing 文案"，
后续 diff 以此为基准；二期接入 SP-API 后本表同时作为回填审计快照。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ListingCopy(Base, TimestampMixin):
    __tablename__ = "listing_copies"
    __table_args__ = (
        UniqueConstraint(
            "listing_id", "marketplace_id", name="uq_listing_copy_listing_market"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    marketplace_id: Mapped[str] = mapped_column(String(16), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 当前文案：{title, bullets, description, search_terms}
    content: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # 最近一次确认回填时勾选的字段名
    applied_fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    listing: Mapped["Listing"] = relationship(back_populates="copies")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ListingCopy listing={self.listing_id} market={self.marketplace_id}>"
