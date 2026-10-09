"""FastAPI 公共依赖：数据库会话、当前用户。"""

from typing import Generator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.exceptions import AuthError, PermissionDeniedError
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user_repo import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/token", auto_error=False
)


def get_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_session),
) -> User:
    if not token:
        raise AuthError("缺少访问令牌")
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthError("访问令牌缺少主体信息")
    user = UserRepository(db).get(int(user_id))
    if user is None or not user.is_active:
        raise AuthError("用户不存在或已被禁用")
    return user


def get_current_admin(current: User = Depends(get_current_user)) -> User:
    """要求当前用户具备管理员权限，否则 403。"""
    if not current.is_admin:
        raise PermissionDeniedError("需要管理员权限")
    return current
