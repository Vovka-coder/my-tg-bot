"""
RefLens — Subscription Middleware
Проверяет доступ к платным функциям.
"""

from typing import Any, Awaitable, Callable, Dict, Set

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.database.models import SubscriptionTier

logger = structlog.get_logger(__name__)

# Команды требующие Pro или выше
PRO_COMMANDS: Set[str] = {"/tree", "/export", "/top"}

# Команды требующие Business
BUSINESS_COMMANDS: Set[str] = set()


class SubscriptionMiddleware(BaseMiddleware):
    """
    Проверяет подписку пользователя перед доступом к платным функциям.
    Использует db_user из UserMiddleware (должен быть раньше в цепочке).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        db_user = data.get("db_user")

        # Нет пользователя — пропускаем проверку
        if db_user is None:
            return await handler(event, data)

        # Определяем команду
        command = None
        if isinstance(event, Message) and event.text:
            command = event.text.split()[0].lower()
        elif isinstance(event, CallbackQuery) and event.data:
            command = event.data.split(":")[0].lower()

        if command is None:
            return await handler(event, data)

        # Проверяем доступ
        tier = await self._get_user_tier(db_user, data)

        if command in BUSINESS_COMMANDS and tier != SubscriptionTier.BUSINESS:
            await self._send_upgrade_message(event, required_tier="business")
            return None

        if command in PRO_COMMANDS and tier == SubscriptionTier.FREE:
            await self._send_upgrade_message(event, required_tier="pro")
            return None

        # Кладём тир в data для использования в handlers
        data["subscription_tier"] = tier

        return await handler(event, data)

    async def _get_user_tier(self, db_user: Any, data: Dict) -> SubscriptionTier:
        """Получает тир из кэша Redis или БД."""
        redis = data.get("redis")
        if redis:
            try:
                cached = await redis.get(f"user:{db_user.telegram_id}:subscription")
                if cached:
                    return SubscriptionTier(cached.decode())
            except Exception:
                pass

        # Fallback: из объекта подписки
        if db_user.subscription:
            return db_user.subscription.tier

        return SubscriptionTier.FREE

    async def _send_upgrade_message(self, event: TelegramObject, required_tier: str) -> None:
        tier_names = {"pro": "Pro (790 ₽/мес)", "business": "Business (1990 ₽/мес)"}
        text = (
            f"🔒 Эта функция доступна на тарифе {tier_names.get(required_tier, required_tier)}.\n\n"
            f"Попробуй бесплатно 7 дней — /tariffs"
        )
        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
