"""
RefLens — Throttling Middleware
Ограничение частоты запросов через Redis.
"""

from typing import Any, Awaitable, Callable, Dict

import structlog
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

# Лимиты по умолчанию (запросов / секунд)
DEFAULT_RATE_LIMIT = 1  # 1 запрос
DEFAULT_RATE_PERIOD = 1  # в 1 секунду


class ThrottlingMiddleware(BaseMiddleware):
    """
    Rate limiting через Redis.
    Блокирует пользователей превышающих лимит запросов.
    """

    def __init__(
        self,
        redis: Redis,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        rate_period: int = DEFAULT_RATE_PERIOD,
    ) -> None:
        self.redis = redis
        self.rate_limit = rate_limit
        self.rate_period = rate_period

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        from aiogram.types import User as TelegramUser

        tg_user: TelegramUser | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        key = f"rate_limit:{tg_user.id}"

        try:
            current = await self.redis.incr(key)
            if current == 1:
                await self.redis.expire(key, self.rate_period)

            if current > self.rate_limit:
                logger.warning("Rate limit exceeded", telegram_id=tg_user.id)
                if isinstance(event, Message):
                    await event.answer("⚠️ Слишком много запросов. Подожди секунду.")
                return None

        except Exception as e:
            logger.error("Throttling check failed", error=str(e))
            # При ошибке Redis — пропускаем, не блокируем бота

        return await handler(event, data)
