"""
RefLens — Channel Repository
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Channel
from bot.repositories.base import BaseRepository


class ChannelRepository(BaseRepository[Channel]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Channel)

    async def get_by_chat_id(self, telegram_chat_id: int) -> Optional[Channel]:
        return await self.get(telegram_chat_id=telegram_chat_id)

    async def get_user_channels(self, owner_id: int) -> List[Channel]:
        result = await self.session.execute(
            select(Channel).where(Channel.owner_id == owner_id, Channel.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_or_create_channel(
        self,
        telegram_chat_id: int,
        owner_id: int,
        title: str,
        username: Optional[str] = None,
        invite_link: Optional[str] = None,
    ) -> tuple[Channel, bool]:
        """Вернуть (channel, created)."""
        existing = await self.get_by_chat_id(telegram_chat_id)
        if existing:
            return existing, False

        channel = await self.create(
            telegram_chat_id=telegram_chat_id,
            owner_id=owner_id,
            title=title,
            username=username,
            invite_link=invite_link,
            settings={
                "min_account_age_days": 7,
                "min_messages_count": 1,
            },
        )
        return channel, True
