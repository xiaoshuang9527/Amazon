"""初始表结构：users / shops / listings / generations / subscriptions / compliance_rules

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-08

说明：
- refresh_token 以 Fernet 密文存储（列长度 1024）；
- listings 对 (shop_id, asin, marketplace_id) 建唯一约束；
- generations 对 (listing_id, target_language, created_at) 建索引。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list:
    return [
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
    ]


def upgrade() -> None:
    # ---------------- users ----------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ---------------- shops ----------------
    op.create_table(
        "shops",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.String(length=64), nullable=False),
        sa.Column("marketplace_ids", sa.JSON(), nullable=False),
        sa.Column("refresh_token", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shops_user_id", "shops", ["user_id"])

    # ---------------- listings ----------------
    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=True),
        sa.Column("asin", sa.String(length=32), nullable=True),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("marketplace_id", sa.String(length=16), nullable=True),
        sa.Column("source_language", sa.String(length=16), nullable=False, server_default="zh"),
        sa.Column("source_content", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "shop_id", "asin", "marketplace_id", name="uq_listing_shop_asin_market"
        ),
    )
    op.create_index("ix_listings_shop_id", "listings", ["shop_id"])

    # ---------------- generations ----------------
    op.create_table(
        "generations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("target_marketplace", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("target_language", sa.String(length=16), nullable=False),
        sa.Column("model_used", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False, server_default="0"),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generations_task_id", "generations", ["task_id"])
    op.create_index("ix_generations_listing_id", "generations", ["listing_id"])
    op.create_index(
        "ix_generation_listing_lang_created",
        "generations",
        ["listing_id", "target_language", "created_at"],
    )

    # ---------------- subscriptions ----------------
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quota_used", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    # ---------------- compliance_rules ----------------
    op.create_table(
        "compliance_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("marketplace_id", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="*"),
        sa.Column("banned_words", sa.JSON(), nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False, server_default=""),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_rules_marketplace_id", "compliance_rules", ["marketplace_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_compliance_rules_marketplace_id", table_name="compliance_rules")
    op.drop_table("compliance_rules")

    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_generation_listing_lang_created", table_name="generations")
    op.drop_index("ix_generations_listing_id", table_name="generations")
    op.drop_index("ix_generations_task_id", table_name="generations")
    op.drop_table("generations")

    op.drop_index("ix_listings_shop_id", table_name="listings")
    op.drop_table("listings")

    op.drop_index("ix_shops_user_id", table_name="shops")
    op.drop_table("shops")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
