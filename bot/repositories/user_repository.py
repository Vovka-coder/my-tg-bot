"""
RefLens — User Repository
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import Subscription, SubscriptionStatus, SubscriptionTier, User
from bot.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID (с подпиской)."""
        result = await self.session.execute(
            select(User)
            .where(User.telegram_id == telegram_id)
            .options(selectinload(User.subscription))
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> User:
        """
        Получить пользователя или создать нового.
        При создании автоматически создаёт запись Subscription(FREE).
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user

        create_data: Dict[str, Any] = {"telegram_id": telegram_id}
        if defaults:
            create_data.update(defaults)

        user = await self.create(**create_data)

        # Создаём подписку FREE автоматически
        subscription = Subscription(
            user_id=user.id,
            tier=SubscriptionTier.FREE,
            status=SubscriptionStatus.ACTIVE,
        )
        self.session.add(subscription)
        await self.session.flush()

        return user

    async def set_consent(self, telegram_id: int) -> Optional[User]:
        """Зафиксировать согласие пользователя."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return None
        return await self.update(
            user.id,
            {"consent_given": True, "consent_at": datetime.utcnow()},
        )

    async def get_expiring_subscriptions(self, days: int = 3) -> List[User]:
        """Пользователи чья подписка истекает через N дней (для напоминаний)."""
        from datetime import timedelta

        from sqlalchemy import and_, func

        now = datetime.utcnow()
        deadline = now + timedelta(days=days)

        result = await self.session.execute(
            select(User)
            .join(User.subscription)
            .where(
                and_(
                    Subscription.current_period_end >= now,
                    Subscription.current_period_end <= deadline,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                )
            )
            .options(selectinload(User.subscription))
        )
        return list(result.scalars().all())
