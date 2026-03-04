"""
RefLens — User Middleware
Создаёт/обновляет пользователя в БД и кладёт db_user + user_repo в data.
"""
from typing import Any, Awaitable, Callable, Dict

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TelegramUser

from bot.repositories.user_repository import UserRepository

logger = structlog.get_logger(__name__)


class UserMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: TelegramUser | None = data.get("event_from_user")

        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        session_maker = data.get("session_maker")
        if session_maker is None:
            logger.error("session_maker not found in data")
            return await handler(event, data)

        async with session_maker() as session:
            repo = UserRepository(session)

            try:
                db_user = await repo.get_or_create(
                    telegram_id=tg_user.id,
                    defaults={
                        "username": tg_user.username,
                        "first_name": tg_user.first_name,
                        "last_name": getattr(tg_user, "last_name", None),
                        "language_code": tg_user.language_code,
                    },
                )

                # Обновляем username если изменился
                if db_user.username != tg_user.username:
                    await repo.update(db_user.id, {"username": tg_user.username})

                await session.commit()

                data["db_user"] = db_user
                data["user_repo"] = repo

            except Exception as e:
                logger.error("UserMiddleware failed", telegram_id=tg_user.id, error=str(e))
                data["db_user"] = None
                data["user_repo"] = None

            return await handler(event, data)
