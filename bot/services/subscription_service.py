"""RefLens — Subscription Service."""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Subscription, SubscriptionStatus, SubscriptionTier
from bot.repositories.subscription_repository import SubscriptionRepository


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sub_repo = SubscriptionRepository(session)

    async def get_or_create(self, user_id: int) -> Subscription:
        sub = await self.sub_repo.get_by_user_id(user_id)
        if not sub:
            sub = await self.sub_repo.create(
                user_id=user_id,
                tier=SubscriptionTier.FREE,
                status=SubscriptionStatus.ACTIVE,
                auto_renew=False,
            )
            await self.session.flush()
        return sub

    async def activate(
        self,
        user_id: int,
        tier: SubscriptionTier,
        period_days: int = 30,
    ) -> Subscription:
        now = datetime.utcnow()
        sub = await self.sub_repo.create_or_update(
            user_id=user_id,
            tier=tier,
            status=SubscriptionStatus.ACTIVE,
            current_period_end=now + timedelta(days=period_days),
            current_period_start=now,
            auto_renew=True,
        )
        await self.session.commit()
        return sub

    async def cancel(self, user_id: int) -> Subscription:
        sub = await self.get_or_create(user_id)
        sub.status = SubscriptionStatus.CANCELLED
        sub.auto_renew = False
        await self.session.commit()
        return sub

    async def freeze(self, user_id: int, days: int = 30) -> Subscription:
        sub = await self.get_or_create(user_id)
        if sub.tier == SubscriptionTier.FREE:
            raise ValueError("Нельзя заморозить бесплатную подписку")
        sub.status = SubscriptionStatus.FROZEN
        sub.frozen_until = datetime.utcnow() + timedelta(days=days)
        await self.session.commit()
        return sub

    async def check_access(
        self, user_id: int, required_tier: SubscriptionTier
    ) -> Tuple[bool, Optional[str]]:
        if required_tier == SubscriptionTier.FREE:
            return True, None

        sub = await self.get_or_create(user_id)
        now = datetime.utcnow()

        if sub.tier == SubscriptionTier.FREE:
            return False, "Функция доступна только на платных тарифах"

        if sub.status == SubscriptionStatus.CANCELLED:
            return False, "Подписка отменена"

        if sub.status == SubscriptionStatus.EXPIRED:
            return False, "Срок подписки истёк"

        if sub.status == SubscriptionStatus.FROZEN:
            if sub.frozen_until and now < sub.frozen_until:
                until = sub.frozen_until.strftime("%d.%m.%Y")
                return False, f"Подписка заморожена до {until}"
            return False, "Подписка заморожена и требует продления"

        if sub.current_period_end and now > sub.current_period_end:
            sub.status = SubscriptionStatus.EXPIRED
            await self.session.commit()
            return False, "Срок подписки истёк"

        tiers_ok = {
            SubscriptionTier.PRO: {SubscriptionTier.PRO, SubscriptionTier.BUSINESS},
            SubscriptionTier.BUSINESS: {SubscriptionTier.BUSINESS},
        }
        if sub.tier in tiers_ok.get(required_tier, set()):
            return True, None

        return False, "Недостаточный уровень подписки"
