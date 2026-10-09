"""生成记录模型：一次多语言生成任务的结果。"""

from sqlalchemy import ForeignKey, Index, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Generation(Base, TimestampMixin):
    __tablename__ = "generations"
    __table_args__ = (
        Index("ix_generation_listing_lang_created", "listing_id", "target_language", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 任务 ID：同一批次多语言结果共享，用于前端轮询状态
    task_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("listings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_marketplace: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    target_language: Mapped[str] = mapped_column(String(16), nullable=False)
    model_used: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    input_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    # {title, bullets, description, search_terms, suggested_keywords, compliance_report}
    result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)

    listing: Mapped["Listing"] = relationship(back_populates="generations")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Generation id={self.id} task={self.task_id} lang={self.target_language}>"
