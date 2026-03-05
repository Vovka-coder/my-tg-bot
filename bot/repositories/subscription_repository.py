"""RefLens — Subscription Repository."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Subscription, SubscriptionStatus, SubscriptionTier
from bot.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Subscription)

    async def get_by_user_id(self, user_id: int) -> Optional[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        user_id: int,
        tier: SubscriptionTier,
        status: SubscriptionStatus,
        current_period_end,
        auto_renew: bool = True,
        **kwargs,
    ) -> Subscription:
        sub = await self.get_by_user_id(user_id)
        if sub:
            values = {
                "tier": tier,
                "status": status,
                "current_period_end": current_period_end,
                "auto_renew": auto_renew,
                **kwargs,
            }
            for key, value in values.items():
                setattr(sub, key, value)
            await self.session.flush()
            return sub
        return await self.create(
            user_id=user_id,
            tier=tier,
            status=status,
            current_period_end=current_period_end,
            auto_renew=auto_renew,
            **kwargs,
        )
