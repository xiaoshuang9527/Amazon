"""合规规则模型（可入库的规则，与 data/ 下 JSON 规则互补）。"""

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ComplianceRule(Base, TimestampMixin):
    __tablename__ = "compliance_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    marketplace_id: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="*", nullable=False)
    banned_words: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)  # banned_word|char_limit|...
    description: Mapped[str] = mapped_column(String(512), default="", nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ComplianceRule market={self.marketplace_id} type={self.rule_type}>"
