import logging

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from redis.asyncio import Redis

from bot.config import settings

logger = structlog.get_logger(__name__)


async def on_startup(bot: Bot) -> None:
    logger.info("Bot starting...", env=settings.APP_ENV)
    # Здесь: прогрев кэша, проверка внешних сервисов, и т.д.


async def on_shutdown(bot: Bot, redis: Redis) -> None:
    logger.info("Bot shutting down...")
    await bot.session.close()
    await redis.aclose()
    logger.info("Bot stopped.")


async def main() -> None:
    # ── Логирование ──────────────────────────
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # Sentry (если настроен)
    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.APP_ENV)
        logger.info("Sentry initialized")

    # ── Redis + Storage ───────────────────────
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    storage = RedisStorage(
        redis=redis,
        key_builder=DefaultKeyBuilder(with_destiny=True),
    )

    # ── Bot + Dispatcher ──────────────────────
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    # ── Регистрация роутеров ──────────────────
    # TODO: раскомментировать по мере создания
    # from bot.handlers import start, help_handler, payment
    # dp.include_router(start.router)
    # dp.include_router(help_handler.router)
    # dp.include_router(payment.router)

    # ── Хуки жизненного цикла ─────────────────
    dp.startup.register(lambda: on_startup(bot))

    # ── Запуск ────────────────────────────────
    try:
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown(bot, redis)
