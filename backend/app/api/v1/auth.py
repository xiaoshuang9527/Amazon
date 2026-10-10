"""认证与店铺授权路由。"""

import secrets

from fastapi import APIRouter, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.config import settings
from app.core.exceptions import AuthError, NotFoundError
from app.core.security import (
    create_access_token,
    encrypt_secret,
    hash_password,
    verify_password,
)
from app.models.shop import Shop
from app.models.user import User
from app.repositories.shop_repo import ShopRepository
from app.repositories.user_repo import UserRepository
from app.schemas.user import PasswordChange, Token, UserCreate, UserRead
from app.services.spapi_service import spapi_service

router = APIRouter()


@router.post("/register", response_model=UserRead, summary="注册")
def register(payload: UserCreate, db: Session = Depends(get_session)) -> User:
    repo = UserRepository(db)
    if repo.get_by_email(payload.email):
        raise AuthError("该邮箱已注册")
    bootstrap = (settings.BOOTSTRAP_ADMIN_EMAIL or "").strip().lower()
    is_bootstrap_admin = bool(bootstrap) and payload.email.strip().lower() == bootstrap
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_admin=is_bootstrap_admin,
    )
    repo.add(user)
    repo.commit()
    return user


@router.post("/token", response_model=Token, summary="登录获取令牌")
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_session)
) -> Token:
    repo = UserRepository(db)
    user = repo.get_by_email(form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        raise AuthError("邮箱或密码错误")
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead, summary="当前用户")
def me(current: User = Depends(get_current_user)) -> User:
    return current


@router.post("/password", summary="修改当前用户密码")
def change_password(
    payload: PasswordChange,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    if not verify_password(payload.old_password, current.hashed_password):
        raise AuthError("当前密码不正确")
    current.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "密码已更新"}


# --------------------------------------------------------------------------- #
# SP-API 授权（MVP 可选）
# --------------------------------------------------------------------------- #
@router.get("/spapi/authorize", summary="获取 SP-API 授权链接")
def spapi_authorize(current: User = Depends(get_current_user)) -> dict:
    state = secrets.token_urlsafe(16)
    return {
        "authorize_url": spapi_service.get_authorization_url(state),
        "state": state,
        # 未配置 SP-API 凭据时，授权链接无法真正走通，前端据此给出提示
        "configured": bool(settings.SPAPI_CLIENT_ID and settings.SPAPI_CLIENT_SECRET),
    }


@router.get("/spapi/callback", summary="SP-API 授权回调")
def spapi_callback(
    code: str = Query(...),
    selling_partner_id: str = Query(default=""),
    db: Session = Depends(get_session),
) -> dict:
    token_info = spapi_service.exchange_code_for_token(code)
    seller_id = selling_partner_id or token_info.get("seller_id", "")
    if not seller_id:
        raise NotFoundError("未能获取 seller_id，请检查回调参数")

    repo = ShopRepository(db)
    shop = repo.get_by_seller(user_id=1, seller_id=seller_id)
    if shop is None:
        shop = Shop(
            user_id=1,  # MVP：回调未带登录态，先落默认用户，二期改为 state 绑定用户
            seller_id=seller_id,
            marketplace_ids=[],
            refresh_token=encrypt_secret(token_info.get("refresh_token", "")),
            status="active",
        )
        repo.add(shop)
    else:
        shop.refresh_token = encrypt_secret(token_info.get("refresh_token", ""))
    repo.commit()
    return {"shop_id": shop.id, "seller_id": seller_id, "status": "authorized"}


@router.get("/shops", summary="我的店铺列表")
def list_shops(
    current: User = Depends(get_current_user), db: Session = Depends(get_session)
) -> list[dict]:
    shops = ShopRepository(db).list_by_user(current.id)
    return [
        {
            "id": s.id,
            "seller_id": s.seller_id,
            "marketplace_ids": s.marketplace_ids,
            "status": s.status,
            "created_at": s.created_at,
        }
        for s in shops
    ]


@router.delete("/shops/{shop_id}", summary="解除店铺授权")
def revoke_shop(
    shop_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> dict:
    repo = ShopRepository(db)
    shop = repo.get(shop_id)
    if shop is None or shop.user_id != current.id:
        raise NotFoundError("店铺不存在")
    repo.delete(shop)
    repo.commit()
    return {"shop_id": shop_id, "message": "已解除授权"}
