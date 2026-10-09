"""应用配置。

统一通过 pydantic-settings 从 .env 读取，禁止在业务代码中硬编码密钥。
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---------- 基础 ----------
    APP_NAME: str = "亚马逊 Listing 多语言文案生成工具"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = [
        "http://localhost:5180",
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    # ---------- 数据库 ----------
    # 开发 / 生产使用 PostgreSQL 15；测试可覆盖为 sqlite。
    DATABASE_URL: str = "postgresql+psycopg2://listing:listing@postgres:5432/listing"
    SQL_ECHO: bool = False

    # ---------- 安全 ----------
    JWT_SECRET: str = "change-me-in-production-please"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
    # Fernet 对称加密密钥，用于加密存储 SP-API refresh_token。
    # 默认值为 32 字节零值的合法 Fernet key，生产环境必须通过 .env 覆盖。
    FERNET_KEY: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

    # ---------- Amazon SP-API (MVP 仅保留授权，可留空) ----------
    SPAPI_CLIENT_ID: str = ""
    SPAPI_CLIENT_SECRET: str = ""
    SPAPI_REFRESH_TOKEN: str = ""
    SPAPI_LWA_ENDPOINT: str = "https://api.amazon.com/auth/o2/token"
    SPAPI_AUTH_BASE: str = "https://sellercentral.amazon.com/apps/authorize/consent"
    SPAPI_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/spapi/callback"

    # ---------- LLM 网关 ----------
    LLM_PROVIDER: str = "deepseek"  # deepseek | openai
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL_STANDARD: str = "deepseek-chat"
    LLM_MODEL_HIGH: str = "deepseek-reasoner"
    LLM_TIMEOUT: float = 60.0
    LLM_MAX_RETRIES: int = 2
    LLM_ENABLE_CACHE: bool = True

    # ---------- 外部调用速率控制（令牌桶 + 指数退避）----------
    RATE_LIMIT_CAPACITY: int = 10
    RATE_LIMIT_REFILL_PER_SEC: float = 5.0
    RETRY_BASE_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 8.0

    # ---------- 计费 / 配额 ----------
    FREE_MONTHLY_QUOTA: int = 3
    BASIC_MONTHLY_QUOTA: int = 50
    PRO_MONTHLY_QUOTA: int = 200

    # ---------- 任务调度 ----------
    ENABLE_SCHEDULER: bool = True
    LOG_DIR: str = "D:\\yms\\amazon-listing-mvp\\logs"
    LOG_LEVEL: str = "INFO"

    # ---------- 管理后台 ----------
    # 若设置，则使用该邮箱注册的用户自动成为管理员（用于引导第一个管理员）
    BOOTSTRAP_ADMIN_EMAIL: str = ""

    @field_validator("LLM_PROVIDER")
    @classmethod
    def _normalize_provider(cls, v: str) -> str:
        provider = (v or "").strip().lower()
        if provider not in {"deepseek", "openai"}:
            raise ValueError("LLM_PROVIDER 仅支持 deepseek / openai")
        return provider


    @property
    def cors_origin_list(self) -> List[str]:
        """CORS 白名单（便于在测试中覆盖）。"""
        return self.CORS_ORIGINS


@lru_cache
def get_settings() -> Settings:
    """返回单例配置对象（带缓存）。"""
    return Settings()


settings = get_settings()
