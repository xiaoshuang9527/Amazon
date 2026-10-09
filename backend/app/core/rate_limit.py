"""外部调用的速率控制与重试工具（令牌桶 + 指数退避 + 超时）。"""

import asyncio
import threading
import time
from typing import Awaitable, Callable, Optional, Tuple, Type, TypeVar

from app.core.exceptions import UpstreamError
from app.core.logging import get_logger

logger = get_logger("app.rate_limit")

T = TypeVar("T")


class TokenBucket:
    """线程安全的令牌桶限流器。

    支持同步与异步两种消费方式，供 SP-API / LLM 等外部调用复用。
    """

    def __init__(self, capacity: int = 10, refill_per_sec: float = 5.0) -> None:
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
            self._last = now

    def _wait_time(self) -> float:
        if self._tokens >= 1:
            return 0.0
        return (1 - self._tokens) / self.refill_per_sec

    def try_acquire(self) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

    def acquire(self) -> None:
        """同步阻塞获取一个令牌。"""
        while True:
            with self._lock:
                self._refill()
                wait = self._wait_time()
                if wait <= 0:
                    self._tokens -= 1
                    return
            time.sleep(min(wait, 0.5))

    async def acquire_async(self) -> None:
        """异步获取一个令牌。"""
        while True:
            with self._lock:
                self._refill()
                wait = self._wait_time()
                if wait <= 0:
                    self._tokens -= 1
                    return
            await asyncio.sleep(min(wait, 0.5))


def compute_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    """指数退避：base * 2^(attempt-1)，上限 max_delay。"""
    return min(max_delay, base_delay * (2 ** (attempt - 1)))


def retry_sync(
    func: Callable[[], T],
    *,
    max_retries: int = 2,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
    retry_statuses: Tuple[int, ...] = (429, 500, 502, 503, 504),
    bucket: Optional[TokenBucket] = None,
) -> T:
    """同步重试包装器。

    对 ``retry_statuses`` 或 ``retry_on`` 命中的异常做指数退避重试。
    若传入 ``bucket``，每次尝试前先获取令牌。
    """
    last_exc: Optional[BaseException] = None
    for attempt in range(1, max_retries + 2):  # 首次 + max_retries 次重试
        if bucket is not None:
            bucket.acquire()
        try:
            return func()
        except retry_on as exc:  # type: ignore[misc]
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and status not in retry_statuses:
                raise
            last_exc = exc
            if attempt > max_retries:
                break
            delay = compute_backoff(attempt, base_delay, max_delay)
            logger.warning(
                "调用失败，准备重试",
                extra={"attempt": attempt, "delay": delay, "error": str(exc)},
            )
            time.sleep(delay)
    raise UpstreamError(f"外部调用在 {max_retries} 次重试后仍失败: {last_exc}")


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 2,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
    bucket: Optional[TokenBucket] = None,
) -> T:
    """异步重试包装器，语义与 :func:`retry_sync` 一致。"""
    last_exc: Optional[BaseException] = None
    for attempt in range(1, max_retries + 2):
        if bucket is not None:
            await bucket.acquire_async()
        try:
            return await func()
        except retry_on as exc:  # type: ignore[misc]
            last_exc = exc
            if attempt > max_retries:
                break
            delay = compute_backoff(attempt, base_delay, max_delay)
            logger.warning(
                "异步调用失败，准备重试",
                extra={"attempt": attempt, "delay": delay, "error": str(exc)},
            )
            await asyncio.sleep(delay)
    raise UpstreamError(f"外部调用在 {max_retries} 次重试后仍失败: {last_exc}")
