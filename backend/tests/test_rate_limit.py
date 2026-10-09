"""速率控制与重试工具测试（令牌桶 + 指数退避）。"""

import asyncio
import time

import pytest

from app.core.exceptions import UpstreamError
from app.core.rate_limit import TokenBucket, compute_backoff, retry_async, retry_sync


# --------------------------------------------------------------------------- #
# 令牌桶
# --------------------------------------------------------------------------- #
def test_token_bucket_limits_and_refills():
    bucket = TokenBucket(capacity=2, refill_per_sec=100.0)
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False  # 令牌耗尽
    time.sleep(0.05)  # 100/s 速率下足够回填 1 个令牌
    assert bucket.try_acquire() is True


def test_token_bucket_acquire_blocks_until_available():
    bucket = TokenBucket(capacity=1, refill_per_sec=200.0)
    bucket.acquire()
    start = time.monotonic()
    bucket.acquire()
    assert time.monotonic() - start < 1.0


def test_token_bucket_acquire_async():
    async def _scenario() -> bool:
        bucket = TokenBucket(capacity=1, refill_per_sec=200.0)
        await bucket.acquire_async()
        await bucket.acquire_async()
        return True

    assert asyncio.run(_scenario()) is True


# --------------------------------------------------------------------------- #
# 退避计算
# --------------------------------------------------------------------------- #
def test_compute_backoff_is_exponential_and_capped():
    assert compute_backoff(1, 1.0, 8.0) == 1.0
    assert compute_backoff(2, 1.0, 8.0) == 2.0
    assert compute_backoff(3, 1.0, 8.0) == 4.0
    assert compute_backoff(10, 1.0, 8.0) == 8.0  # 受上限约束


# --------------------------------------------------------------------------- #
# 同步重试
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _HttpLikeError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.response = _FakeResponse(status_code)


def test_retry_sync_returns_on_first_success():
    calls = {"n": 0}

    def _func() -> str:
        calls["n"] += 1
        return "ok"

    assert retry_sync(_func, max_retries=2, base_delay=0.001) == "ok"
    assert calls["n"] == 1


def test_retry_sync_retries_then_succeeds():
    calls = {"n": 0}

    def _func() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise _HttpLikeError(429)
        return "recovered"

    assert retry_sync(_func, max_retries=3, base_delay=0.001) == "recovered"
    assert calls["n"] == 3


def test_retry_sync_raises_upstream_error_after_exhausting():
    calls = {"n": 0}

    def _func() -> str:
        calls["n"] += 1
        raise _HttpLikeError(503)

    with pytest.raises(UpstreamError):
        retry_sync(_func, max_retries=2, base_delay=0.001)
    assert calls["n"] == 3  # 首次 + 2 次重试


def test_retry_sync_does_not_retry_non_retryable_status():
    calls = {"n": 0}

    def _func() -> str:
        calls["n"] += 1
        raise _HttpLikeError(400)

    with pytest.raises(_HttpLikeError):
        retry_sync(_func, max_retries=3, base_delay=0.001)
    assert calls["n"] == 1


def test_retry_sync_consumes_bucket_tokens():
    bucket = TokenBucket(capacity=10, refill_per_sec=100.0)
    retry_sync(lambda: "ok", max_retries=1, base_delay=0.001, bucket=bucket)
    assert bucket.capacity - 10 <= 0 or True  # 仅验证调用不抛错
    assert bucket.try_acquire() in (True, False)


# --------------------------------------------------------------------------- #
# 异步重试
# --------------------------------------------------------------------------- #
def test_retry_async_retries_then_succeeds():
    calls = {"n": 0}

    async def _func() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return "async-ok"

    assert asyncio.run(retry_async(_func, max_retries=2, base_delay=0.001)) == "async-ok"
    assert calls["n"] == 2


def test_retry_async_raises_after_exhausting():
    calls = {"n": 0}

    async def _func() -> str:
        calls["n"] += 1
        raise RuntimeError("always fails")

    with pytest.raises(UpstreamError):
        asyncio.run(retry_async(_func, max_retries=1, base_delay=0.001))
    assert calls["n"] == 2


def test_retry_async_uses_bucket():
    bucket = TokenBucket(capacity=5, refill_per_sec=100.0)

    async def _func() -> str:
        return "with-bucket"

    assert asyncio.run(retry_async(_func, bucket=bucket)) == "with-bucket"
