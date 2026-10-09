"""Listing 模型：产品原始信息。"""

from typing import List

from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Listing(Base, TimestampMixin):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("shop_id", "asin", "marketplace_id", name="uq_listing_shop_asin_market"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shop_id: Mapped[int | None] = mapped_column(
        ForeignKey("shops.id", ondelete="SET NULL"), nullable=True, index=True
    )
    asin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    marketplace_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_language: Mapped[str] = mapped_column(String(16), default="zh", nullable=False)
    # 原始产品信息：{title, bullets, description, keywords, attributes}
    source_content: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    shop: Mapped["Shop"] = relationship(back_populates="listings")  # noqa: F821
    generations: Mapped[List["Generation"]] = relationship(  # noqa: F821
        back_populates="listing", cascade="all, delete-orphan"
    )
    copies: Mapped[List["ListingCopy"]] = relationship(  # noqa: F821
        back_populates="listing", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Listing id={self.id} asin={self.asin} market={self.marketplace_id}>"
