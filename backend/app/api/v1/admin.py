"""管理员接口：用户管理与基础统计。

全部接口依赖 ``get_current_admin``，仅 is_admin=True 的用户可访问。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_session
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.generation import Generation
from app.models.listing import Listing
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.core.security import hash_password
from app.schemas.user import AdminPasswordReset, UserAdminUpdate, UserRead

router = APIRouter()


@router.get("/users", summary="用户列表（分页）")
def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict:
    repo = UserRepository(db)
    users = repo.list_paged(limit=limit, offset=offset)
    return {
        "total": repo.count(),
        "limit": limit,
        "offset": offset,
        "items": [UserRead.model_validate(u) for u in users],
    }


@router.get("/stats", summary="平台基础统计")
def stats(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict:
    def _count(model) -> int:
        return int(db.execute(select(func.count()).select_from(model)).scalar_one())

    return {
        "users": _count(User),
        "admins": int(
            db.execute(
                select(func.count()).select_from(User).where(User.is_admin.is_(True))
            ).scalar_one()
        ),
        "listings": _count(Listing),
        "generations": _count(Generation),
    }


@router.get("/users/{user_id}", response_model=UserRead, summary="用户详情")
def get_user(
    user_id: int,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> User:
    user = UserRepository(db).get(user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    return user


@router.patch("/users/{user_id}", response_model=UserRead, summary="启用/禁用、授予/撤销管理员")
def update_user(
    user_id: int,
    payload: UserAdminUpdate,
    current: User = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> User:
    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is None:
        raise NotFoundError("用户不存在")

    # 安全护栏：管理员不能把自己降权或停用，避免把自己锁在门外
    if user.id == current.id:
        if payload.is_admin is False:
            raise PermissionDeniedError("不能撤销自己的管理员权限")
        if payload.is_active is False:
            raise PermissionDeniedError("不能停用自己的账号")

    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin
    repo.commit()
    return user


@router.post("/users/{user_id}/reset-password", summary="重置用户密码")
def reset_password(
    user_id: int,
    payload: AdminPasswordReset,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_session),
) -> dict:
    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    user.hashed_password = hash_password(payload.new_password)
    repo.commit()
    return {"user_id": user.id, "email": user.email, "message": "密码已重置"}
