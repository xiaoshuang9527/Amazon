"""users 增加 is_admin 管理员标记

Revision ID: 0003_user_is_admin
Revises: 0002_listing_copy
Create Date: 2026-10-09

说明：
- 新增 is_admin 布尔列，默认 false；
- 已有用户全部保持普通用户，首个管理员通过 CLI 或 BOOTSTRAP_ADMIN_EMAIL 引导。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_user_is_admin"
down_revision: Union[str, None] = "0002_listing_copy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
