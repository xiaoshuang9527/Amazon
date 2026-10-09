"""模型层 CRUD 测试：users / shops / listings / generations / subscriptions / compliance_rules。"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import decrypt_secret, encrypt_secret
from app.models.compliance_rule import ComplianceRule
from app.models.generation import Generation
from app.models.listing import Listing
from app.models.shop import Shop
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.generation_repo import GenerationRepository
from app.repositories.listing_repo import ListingRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.user_repo import UserRepository


def _create_user(db, email: str = "crud@example.com") -> User:
    repo = UserRepository(db)
    user = repo.add(User(email=email, hashed_password="hashed-value", is_active=True))
    repo.commit()
    return user


def _create_shop(db, user: User, seller_id: str = "A1SELLER", token: str = "plain-refresh") -> Shop:
    shop = Shop(
        user_id=user.id,
        seller_id=seller_id,
        marketplace_ids=["US", "DE"],
        refresh_token=encrypt_secret(token),
        status="active",
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


# --------------------------------------------------------------------------- #
# users
# --------------------------------------------------------------------------- #
def test_user_crud(db):
    repo = UserRepository(db)
    user = _create_user(db, "owner@example.com")

    assert user.id is not None
    assert user.is_active is True
    assert user.created_at is not None and user.updated_at is not None
    assert repo.get_by_email("owner@example.com").id == user.id

    user.is_active = False
    db.commit()
    assert repo.get(user.id).is_active is False

    repo.delete(user)
    repo.commit()
    assert repo.get(user.id) is None


def test_user_email_is_unique(db):
    _create_user(db, "dup@example.com")
    with pytest.raises(IntegrityError):
        _create_user(db, "dup@example.com")
    db.rollback()


# --------------------------------------------------------------------------- #
# shops
# --------------------------------------------------------------------------- #
def test_shop_stores_encrypted_refresh_token(db):
    user = _create_user(db, "shop-owner@example.com")
    shop = _create_shop(db, user, "A1SHOP", "Atzr|refresh-token-plain")

    assert shop.refresh_token != "Atzr|refresh-token-plain"
    assert decrypt_secret(shop.refresh_token) == "Atzr|refresh-token-plain"
    assert shop.marketplace_ids == ["US", "DE"]


def test_shop_relationship_with_user(db):
    user = _create_user(db, "rel@example.com")
    shop = _create_shop(db, user)
    db.refresh(user)
    assert [s.id for s in user.shops] == [shop.id]
    assert shop.user.email == "rel@example.com"


# --------------------------------------------------------------------------- #
# listings
# --------------------------------------------------------------------------- #
def _create_listing(db, shop: Shop, asin: str = "B0TEST0001", market: str = "US") -> Listing:
    listing = Listing(
        shop_id=shop.id,
        asin=asin,
        sku=f"SKU-{asin}",
        marketplace_id=market,
        source_language="zh",
        source_content={"title": "中文标题", "bullets": ["卖点一"], "description": "描述"},
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def test_listing_crud_and_repo_queries(db):
    user = _create_user(db, "listing-owner@example.com")
    shop = _create_shop(db, user)
    listing = _create_listing(db, shop, "B0TEST0001", "US")
    _create_listing(db, shop, "B0TEST0002", "DE")

    repo = ListingRepository(db)
    assert len(repo.list_by_shop(shop.id)) == 2
    found = repo.get_by_unique(shop.id, "B0TEST0001", "US")
    assert found is not None and found.id == listing.id
    assert listing.source_content["title"] == "中文标题"

    listing.sku = "SKU-UPDATED"
    db.commit()
    assert repo.get(listing.id).sku == "SKU-UPDATED"


def test_listing_unique_constraint(db):
    user = _create_user(db, "uq@example.com")
    shop = _create_shop(db, user)
    _create_listing(db, shop, "B0DUPLICATE", "US")

    with pytest.raises(IntegrityError):
        _create_listing(db, shop, "B0DUPLICATE", "US")
    db.rollback()


# --------------------------------------------------------------------------- #
# generations
# --------------------------------------------------------------------------- #
def test_generation_crud_and_task_queries(db):
    user = _create_user(db, "gen-owner@example.com")
    shop = _create_shop(db, user)
    listing = _create_listing(db, shop)
    repo = GenerationRepository(db)

    for market, lang in (("US", "en"), ("DE", "de")):
        repo.add(
            Generation(
                task_id="task-abc",
                listing_id=listing.id,
                target_marketplace=market,
                target_language=lang,
                model_used="deepseek-chat",
                input_tokens=120,
                output_tokens=80,
                cost_usd=0.0002,
                result={"title": f"{lang} title"},
                status="success",
            )
        )
    db.commit()

    rows = repo.list_by_task("task-abc")
    assert [r.target_language for r in rows] == ["en", "de"]
    assert repo.get_latest("task-abc", "de").target_marketplace == "DE"
    assert len(repo.list_by_listing(listing.id)) == 2

    de_row = repo.get_latest("task-abc", "de")
    de_row.status = "failed"
    de_row.result = {"error": "上游失败"}
    db.commit()
    assert repo.get(de_row.id).status == "failed"


def test_generation_belongs_to_listing(db):
    user = _create_user(db, "gen-rel@example.com")
    shop = _create_shop(db, user)
    listing = _create_listing(db, shop)
    row = GenerationRepository(db).add(
        Generation(
            task_id="task-rel",
            listing_id=listing.id,
            target_marketplace="JP",
            target_language="ja",
            result={},
            status="pending",
        )
    )
    db.commit()
    assert row.listing.id == listing.id


# --------------------------------------------------------------------------- #
# subscriptions
# --------------------------------------------------------------------------- #
def test_subscription_crud_and_active_lookup(db):
    user = _create_user(db, "sub-owner@example.com")
    repo = SubscriptionRepository(db)
    sub = repo.add(
        Subscription(
            user_id=user.id,
            plan="free",
            status="active",
            quota_used=1,
        )
    )
    repo.commit()

    active = repo.get_active_by_user(user.id)
    assert active is not None and active.id == sub.id
    assert active.plan == "free" and active.quota_used == 1

    active.plan = "pro"
    active.quota_used = 0
    db.commit()
    assert repo.get(sub.id).plan == "pro"


def test_subscription_status_filters_active(db):
    user = _create_user(db, "sub-inactive@example.com")
    repo = SubscriptionRepository(db)
    row = repo.add(Subscription(user_id=user.id, plan="basic", status="expired", quota_used=0))
    repo.commit()
    assert repo.get_active_by_user(user.id) is None
    assert repo.get(row.id).status == "expired"


# --------------------------------------------------------------------------- #
# compliance_rules
# --------------------------------------------------------------------------- #
def test_compliance_rule_json_banned_words_roundtrip(db):
    rule = ComplianceRule(
        marketplace_id="US",
        category="Electronics",
        banned_words=["best", "cheapest"],
        rule_type="absolute_term",
        description="绝对化用语",
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    assert rule.id is not None
    assert rule.banned_words == ["best", "cheapest"]
    assert rule.category == "Electronics"
    assert rule.created_at is not None


# --------------------------------------------------------------------------- #
# 聚合导入完整性（Alembic 自动生成 / 建表依赖 `import app.models`）
# --------------------------------------------------------------------------- #
def test_models_package_registers_all_tables():
    """仅执行 `import app.models` 时，Base.metadata 必须包含全部业务表。

    回归背景：listing_copy.py 曾漏在 app/models/__init__.py 中导出，
    导致仅聚合导入的进程（Alembic autogenerate、独立脚本建表）缺少
    listing_copies 表，运行时才在回填接口上报 "no such table"。
    """
    import pathlib
    import subprocess
    import sys

    backend_root = pathlib.Path(__file__).resolve().parent.parent
    code = (
        "import app.models;"
        "from app.models.base import Base;"
        "print(','.join(sorted(Base.metadata.tables)))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(backend_root),
    )
    assert proc.returncode == 0, proc.stderr
    tables = {name.strip() for name in proc.stdout.strip().split(",") if name.strip()}
    expected = {
        "users",
        "shops",
        "listings",
        "listing_copies",
        "generations",
        "subscriptions",
        "compliance_rules",
    }
    assert expected <= tables, f"缺失表: {sorted(expected - tables)}"
