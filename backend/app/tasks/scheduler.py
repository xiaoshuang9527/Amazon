"""基于 APScheduler 的轻量定时任务（冷启动方案，规模化后切 Celery）。"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.repositories.subscription_repo import SubscriptionRepository

logger = get_logger("app.scheduler")

_scheduler: BackgroundScheduler | None = None


def reset_monthly_quota() -> None:
    """每月 1 号重置配额（示例任务）。"""
    db = SessionLocal()
    try:
        repo = SubscriptionRepository(db)
        for sub in repo.list(limit=10000):
            sub.quota_used = 0
        db.commit()
        logger.info("已重置全部订阅的月度配额")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.ENABLE_SCHEDULER:
        logger.info("调度器已禁用（ENABLE_SCHEDULER=false）")
        return None
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(reset_monthly_quota, CronTrigger(day=1, hour=0, minute=5), id="reset_quota")
    _scheduler.start()
    logger.info("APScheduler 已启动")
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler 已停止")
