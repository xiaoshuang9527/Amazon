"""ORM 模型汇总导出。

导入全部模型，确保 ``Base.metadata`` 完整，Alembic 自动生成迁移时可发现所有表。
"""

from app.models.base import Base, TimestampMixin
from app.models.compliance_rule import ComplianceRule
from app.models.generation import Generation
from app.models.listing import Listing
from app.models.listing_copy import ListingCopy
from app.models.shop import Shop
from app.models.subscription import Subscription
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Shop",
    "Listing",
    "ListingCopy",
    "Generation",
    "Subscription",
    "ComplianceRule",
]
