"""
RefLens — Entry point
"""

import logging

import sentry_sdk
import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from redis.asyncio import Redis

from bot.config import settings
from bot.database.session import AsyncSessionLocal
from bot.handlers import analytics, channel, start, subscription, tree
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.middlewares.user import UserMiddleware

dp.include_router(subscription.router)

logger = structlog.get_logger(__name__)


async def on_shutdown(bot: Bot, redis: Redis) -> None:
    logger.info("Shutting down...")
    await bot.session.close()
    await redis.aclose()
    logger.info("Bot stopped.")


async def main() -> None:
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    if settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.APP_ENV)
        logger.info("Sentry initialized")

    redis = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    storage = RedisStorage(
        redis=redis,
        key_builder=DefaultKeyBuilder(with_destiny=True),
    )

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    # Зависимости доступны во всех middleware и handlers
    dp["redis"] = redis
    dp["session_maker"] = AsyncSessionLocal
    dp["settings"] = settings

    # Middleware (порядок: throttling → user)
    dp.message.middleware(ThrottlingMiddleware(redis))
    dp.callback_query.middleware(ThrottlingMiddleware(redis))
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    # Роутеры
    dp.include_router(start.router)
    dp.include_router(channel.router)
    dp.include_router(analytics.router)
    dp.include_router(tree.router)

    try:
        logger.info("Starting polling...", env=settings.APP_ENV)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown(bot, redis)
