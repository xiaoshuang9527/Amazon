"""用户相关 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    is_admin: bool
    created_at: datetime


class UserAdminUpdate(BaseModel):
    """管理员对用户的更新请求（仅允许改这两个开关）。"""

    is_active: bool | None = None
    is_admin: bool | None = None


class AdminPasswordReset(BaseModel):
    """管理员重置指定用户密码的请求。"""

    new_password: str = Field(min_length=6, max_length=128)


class PasswordChange(BaseModel):
    """用户自助修改密码的请求。"""

    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
