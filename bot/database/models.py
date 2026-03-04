"""
RefLens — SQLAlchemy Models v2.0
Merged best of Claude + DeepSeek architectures.
"""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    FROZEN = "frozen"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ActivityEventType(str, enum.Enum):
    JOIN = "join"
    LEAVE = "leave"
    MESSAGE = "message"
    REACTION = "reaction"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class MemberStatus(str, enum.Enum):
    MEMBER = "member"
    LEFT = "left"
    KICKED = "kicked"
    RESTRICTED = "restricted"


# ─── Models ───────────────────────────────────────────────────────────────────


class User(Base):
    """Владелец канала — пользователь бота."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    last_name: Mapped[Optional[str]] = mapped_column(String(128))
    language_code: Mapped[Optional[str]] = mapped_column(String(8))
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    channels: Mapped[List["Channel"]] = relationship(back_populates="owner")
    subscription: Mapped[Optional["Subscription"]] = relationship(
        back_populates="user", uselist=False
    )
    payments: Mapped[List["Payment"]] = relationship(back_populates="user")


class Channel(Base):
    """Telegram-канал или чат, подключённый к боту."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(256))
    username: Mapped[Optional[str]] = mapped_column(String(64))
    invite_link: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # JSONB для гибких настроек антифрода (DeepSeek)
    # Пример: {"min_account_age_days": 7, "min_messages_count": 1}
    settings: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="channels")
    members: Mapped[List["ChannelMember"]] = relationship(back_populates="channel")

    __table_args__ = (Index("idx_channels_owner", "owner_id"),)


class ChannelMember(Base):
    """
    Участник канала с реферальной привязкой.

    ВАЖНО: referrer_id — здесь, а не в users, потому что один пользователь
    может быть в нескольких каналах с разными рефереррами.
    Самоссылка для построения дерева через WITH RECURSIVE CTE.
    """

    __tablename__ = "channel_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE")
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    # Реферальная привязка — самоссылка
    referrer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("channel_members.id", ondelete="SET NULL")
    )
    # Антифрод-метаданные
    account_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus), default=MemberStatus.MEMBER
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="members")
    referrer: Mapped[Optional["ChannelMember"]] = relationship(
        "ChannelMember", remote_side="ChannelMember.id", back_populates="referrals"
    )
    referrals: Mapped[List["ChannelMember"]] = relationship(
        "ChannelMember", back_populates="referrer"
    )
    activity_logs: Mapped[List["ActivityLog"]] = relationship(back_populates="member")

    __table_args__ = (
        Index("idx_members_channel", "channel_id"),
        Index("idx_members_referrer", "referrer_id"),
        Index("idx_members_channel_joined", "channel_id", "joined_at"),
        Index("idx_members_telegram", "telegram_id"),
    )


class ActivityLog(Base):
    """Лог активности участника в канале."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("channel_members.id", ondelete="CASCADE")
    )
    event_type: Mapped[ActivityEventType] = mapped_column(
        Enum(ActivityEventType), nullable=False
    )
    # JSONB для доп. данных: тип реакции, длина сообщения и т.д. (DeepSeek)
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    member: Mapped["ChannelMember"] = relationship(back_populates="activity_logs")

    __table_args__ = (
        Index("idx_activity_member", "member_id"),
        Index("idx_activity_date", "created_at"),
        Index("idx_activity_member_date", "member_id", "created_at"),
        Index("idx_activity_event_type", "event_type"),
    )


class Subscription(Base):
    """Подписка пользователя."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier), default=SubscriptionTier.FREE
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE
    )
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    frozen_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscription")

    __table_args__ = (Index("idx_subscriptions_period_end", "current_period_end"),)


class Payment(Base):
    """История платежей."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # в копейках
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    tier: Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier))
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING
    )
    provider: Mapped[str] = mapped_column(String(32))  # yookassa / telegram_stars
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="payments")

    __table_args__ = (Index("idx_payments_user", "user_id"),)
