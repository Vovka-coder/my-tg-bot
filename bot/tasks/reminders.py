"""
RefLens — Celery Tasks: reminders + cleanup
"""
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from celery import shared_task
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database.models import ActivityLog, Subscription, SubscriptionStatus, SubscriptionTier, User
from bot.database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _send_reminders_async() -> None:
    bot = Bot(token=settings.BOT_TOKEN)
    now = datetime.utcnow()

    reminder_windows = [
        (
            now + timedelta(days=1),
            now,
            "⚠️ Подписка истекает <b>завтра</b>!\n\nПродли сейчас чтобы не потерять доступ к аналитике → /tariffs",
        ),
        (
            now + timedelta(days=3),
            now + timedelta(days=2),
            "📅 Подписка истекает через 3 дня.\n\nЧтобы не прерывать аналитику — продли заранее → /tariffs",
        ),
    ]

    async with AsyncSessionLocal() as session:
        for deadline, after, text in reminder_windows:
            stmt = (
                select(User)
                .join(User.subscription)
                .where(
                    Subscription.tier.in_([SubscriptionTier.PRO, SubscriptionTier.BUSINESS]),
                    Subscription.current_period_end <= deadline,
                    Subscription.current_period_end > after,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.auto_renew == True,
                )
                .options(selectinload(User.subscription))
            )
            users = (await session.execute(stmt)).scalars().all()

            for user in users:
                try:
                    await bot.send_message(user.telegram_id, text)
                    logger.info("Reminder sent", extra={"telegram_id": user.telegram_id})
                except Exception as e:
                    logger.warning("Failed to send reminder", extra={"telegram_id": user.telegram_id, "error": str(e)})

    await bot.session.close()


async def _cleanup_logs_async() -> None:
    cutoff = datetime.utcnow() - timedelta(days=90)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            delete(ActivityLog).where(ActivityLog.created_at < cutoff)
        )
        await session.commit()
        logger.info("Cleaned up old logs", extra={"deleted": result.rowcount})


@shared_task(name="bot.tasks.reminders.send_subscription_reminders")
def send_subscription_reminders() -> None:
    asyncio.run(_send_reminders_async())


@shared_task(name="bot.tasks.reminders.cleanup_old_logs")
def cleanup_old_logs() -> None:
    asyncio.run(_cleanup_logs_async())
