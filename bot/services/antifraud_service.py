"""
RefLens — AntifraudService
Проверяет участника канала по настраиваемым правилам.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ActivityLog, ActivityEventType, Channel, ChannelMember


@dataclass
class AntiFraudResult:
    is_valid: bool
    reason: Optional[str] = None


class AntiFraudService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def check_member(
        self,
        member: ChannelMember,
        channel: Channel,
    ) -> AntiFraudResult:
        """
        Проверяет участника по трём правилам:
        1. is_bot флаг
        2. Возраст Telegram-аккаунта (member.account_created_at)
        3. Количество сообщений в activity_log
        """
        settings: dict = channel.settings or {}

        # ── 1. Бот-флаг ──────────────────────────────────────────────────────
        if member.is_bot:
            return AntiFraudResult(False, "Аккаунт является ботом")

        # ── 2. Возраст Telegram-аккаунта ─────────────────────────────────────
        # account_created_at заполняется при вступлении в канал если доступно
        min_age_days: Optional[int] = settings.get("min_account_age_days")
        if min_age_days is not None:
            if member.account_created_at is None:
                # Нет данных о возрасте — считаем подозрительным
                return AntiFraudResult(
                    False,
                    "Не удалось определить возраст аккаунта",
                )
            age_days = (
                datetime.utcnow() - member.account_created_at.replace(tzinfo=None)
            ).days
            if age_days < min_age_days:
                return AntiFraudResult(
                    False,
                    f"Аккаунт слишком новый ({age_days} дн., требуется {min_age_days})",
                )

        # ── 3. Количество сообщений в канале ─────────────────────────────────
        min_messages: Optional[int] = settings.get("min_messages_count")
        if min_messages is not None and min_messages > 0:
            result = await self.session.execute(
                select(func.count(ActivityLog.id)).where(
                    ActivityLog.member_id == member.id,
                    ActivityLog.event_type == ActivityEventType.MESSAGE,
                )
            )
            message_count = result.scalar() or 0
            if message_count < min_messages:
                return AntiFraudResult(
                    False,
                    f"Мало сообщений ({message_count}, требуется {min_messages})",
                )

        return AntiFraudResult(True)

    async def bulk_check(
        self,
        members: list[ChannelMember],
        channel: Channel,
    ) -> dict[int, AntiFraudResult]:
        """
        Проверяет список участников.
        Возвращает {member_id: AntiFraudResult}.
        Оптимизировано: один запрос к activity_log для всех участников.
        """
        settings: dict = channel.settings or {}
        min_messages: int = settings.get("min_messages_count", 0)
        min_age_days: Optional[int] = settings.get("min_account_age_days")

        # Получаем счётчики сообщений для всех участников разом
        member_ids = [m.id for m in members]
        counts_result = await self.session.execute(
            select(ActivityLog.member_id, func.count(ActivityLog.id).label("cnt"))
            .where(
                ActivityLog.member_id.in_(member_ids),
                ActivityLog.event_type == ActivityEventType.MESSAGE,
            )
            .group_by(ActivityLog.member_id)
        )
        message_counts = {row.member_id: row.cnt for row in counts_result}

        results: dict[int, AntiFraudResult] = {}
        now = datetime.utcnow()

        for member in members:
            if member.is_bot:
                results[member.id] = AntiFraudResult(False, "Аккаунт является ботом")
                continue

            if min_age_days is not None:
                if member.account_created_at is None:
                    results[member.id] = AntiFraudResult(
                        False, "Не удалось определить возраст аккаунта"
                    )
                    continue
                age_days = (now - member.account_created_at.replace(tzinfo=None)).days
                if age_days < min_age_days:
                    results[member.id] = AntiFraudResult(
                        False,
                        f"Аккаунт слишком новый ({age_days} дн., требуется {min_age_days})",
                    )
                    continue

            if min_messages > 0:
                count = message_counts.get(member.id, 0)
                if count < min_messages:
                    results[member.id] = AntiFraudResult(
                        False, f"Мало сообщений ({count}, требуется {min_messages})"
                    )
                    continue

            results[member.id] = AntiFraudResult(True)

        return results
