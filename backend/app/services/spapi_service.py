"""Amazon SP-API 授权服务（MVP 仅实现 LWA 授权链路）。

约束：
- 仅使用官方 LWA OAuth 2.0，禁止模拟登录 / 爬虫；
- 所有请求带令牌桶限流 + 指数退避重试；
- MVP 阶段产品信息由用户手动粘贴，本模块保留但不作为主链路依赖。
"""

import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import UpstreamError
from app.core.logging import get_logger
from app.core.rate_limit import TokenBucket, retry_sync

logger = get_logger("app.spapi")

_SPAPI_BUCKET = TokenBucket(
    capacity=settings.RATE_LIMIT_CAPACITY,
    refill_per_sec=settings.RATE_LIMIT_REFILL_PER_SEC,
)


class SPAPIService:
    def __init__(self) -> None:
        self._token_cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # 授权链接
    # ------------------------------------------------------------------ #
    def get_authorization_url(self, state: str) -> str:
        """生成卖家授权链接（Login with Amazon）。"""
        params = {
            "application_id": settings.SPAPI_CLIENT_ID,
            "state": state,
            "redirect_uri": settings.SPAPI_REDIRECT_URI,
        }
        return f"{settings.SPAPI_AUTH_BASE}?{urlencode(params)}"

    # ------------------------------------------------------------------ #
    # 用授权码换 refresh_token
    # ------------------------------------------------------------------ #
    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.SPAPI_CLIENT_ID,
            "client_secret": settings.SPAPI_CLIENT_SECRET,
            "redirect_uri": settings.SPAPI_REDIRECT_URI,
        }

        def _call() -> Dict[str, Any]:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(settings.SPAPI_LWA_ENDPOINT, data=payload)
                resp.raise_for_status()
                return resp.json()

        try:
            data = retry_sync(_call, max_retries=3, bucket=_SPAPI_BUCKET)
        except UpstreamError as exc:
            logger.error("换取 refresh_token 失败", extra={"error": str(exc)})
            raise
        return {
            "refresh_token": data.get("refresh_token", ""),
            "access_token": data.get("access_token", ""),
            "expires_in": data.get("expires_in", 3600),
            "seller_id": data.get("selling_partner_id", ""),
        }

    # ------------------------------------------------------------------ #
    # 刷新 access_token（带内存缓存）
    # ------------------------------------------------------------------ #
    def get_access_token(self, refresh_token: str) -> str:
        cached = self._token_cache.get(refresh_token)
        now = time.time()
        if cached and cached["expires_at"] > now + 60:
            return cached["token"]

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.SPAPI_CLIENT_ID,
            "client_secret": settings.SPAPI_CLIENT_SECRET,
        }

        def _call() -> Dict[str, Any]:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(settings.SPAPI_LWA_ENDPOINT, data=payload)
                resp.raise_for_status()
                return resp.json()

        data = retry_sync(_call, max_retries=3, bucket=_SPAPI_BUCKET)
        token = data.get("access_token", "")
        expires_in = int(data.get("expires_in", 3600))
        self._token_cache[refresh_token] = {"token": token, "expires_at": now + expires_in}
        logger.info("刷新 SP-API access_token 成功", extra={"expires_in": expires_in})
        return token

    def clear_cache(self, refresh_token: Optional[str] = None) -> None:
        if refresh_token:
            self._token_cache.pop(refresh_token, None)
        else:
            self._token_cache.clear()


spapi_service = SPAPIService()
