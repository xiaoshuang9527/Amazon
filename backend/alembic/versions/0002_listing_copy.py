"""listing_copies 回填文案表

Revision ID: 0002_listing_copy
Revises: 0001_initial
Create Date: 2026-10-09

说明：
- 记录 (listing_id, marketplace_id) 维度最近一次确认回填的文案；
- content 为 JSON：{title, bullets, description, search_terms}；
- (listing_id, marketplace_id) 建唯一约束，配合 upsert 语义。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_listing_copy"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listing_copies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.String(length=16), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("applied_fields", sa.JSON(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "listing_id", "marketplace_id", name="uq_listing_copy_listing_market"
        ),
    )
    op.create_index("ix_listing_copies_listing_id", "listing_copies", ["listing_id"])


def downgrade() -> None:
    op.drop_index("ix_listing_copies_listing_id", table_name="listing_copies")
    op.drop_table("listing_copies")
