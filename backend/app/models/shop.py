"""店铺模型：保存卖家授权信息（refresh_token 加密存储）。"""

from typing import List

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Shop(Base, TimestampMixin):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    seller_id: Mapped[str] = mapped_column(String(64), nullable=False)
    marketplace_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # 存储 Fernet 加密后的 refresh_token，禁止明文落库
    refresh_token: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    user: Mapped["User"] = relationship(back_populates="shops")  # noqa: F821
    listings: Mapped[List["Listing"]] = relationship(  # noqa: F821
        back_populates="shop", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Shop id={self.id} seller_id={self.seller_id} status={self.status}>"
