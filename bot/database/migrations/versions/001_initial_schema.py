"""Initial schema: users, channels, members, activity_log, subscriptions, payments

Revision ID: 001
Revises:
Create Date: 2026-03-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ──────────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── Enums ───────────────────────────────────────────────────────────────
    op.execute(
        "CREATE TYPE subscription_tier AS ENUM ('free', 'pro', 'business')"
    )
    op.execute(
        "CREATE TYPE subscription_status AS ENUM "
        "('active', 'trial', 'frozen', 'expired', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE activity_event_type AS ENUM "
        "('join', 'leave', 'message', 'reaction')"
    )
    op.execute(
        "CREATE TYPE payment_status AS ENUM "
        "('pending', 'success', 'failed', 'refunded')"
    )

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(128)),
        sa.Column("language_code", sa.String(8)),
        sa.Column("consent_given", sa.Boolean(), default=False, nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True)),
        sa.Column("is_blocked", sa.Boolean(), default=False, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── channels ─────────────────────────────────────────────────────────────
    op.create_table(
        "channels",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "owner_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("telegram_chat_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column("title", sa.String(256)),
        sa.Column("username", sa.String(64)),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("min_account_age_days", sa.Integer(), default=7, nullable=False),
        sa.Column("min_messages_count", sa.Integer(), default=1, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_channels_owner", "channels", ["owner_id"])

    # ── channel_members ───────────────────────────────────────────────────────
    op.create_table(
        "channel_members",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column(
            "referrer_id",
            sa.BigInteger(),
            sa.ForeignKey("channel_members.id", ondelete="SET NULL"),
        ),
        sa.Column("account_created_at", sa.DateTime(timezone=True)),
        sa.Column("is_bot", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_premium", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_verified", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_members_channel", "channel_members", ["channel_id"])
    op.create_index("idx_members_referrer", "channel_members", ["referrer_id"])
    op.create_index(
        "idx_members_channel_joined", "channel_members", ["channel_id", "joined_at"]
    )

    # ── activity_log ──────────────────────────────────────────────────────────
    op.create_table(
        "activity_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "member_id",
            sa.BigInteger(),
            sa.ForeignKey("channel_members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.Enum(
                "join", "leave", "message", "reaction",
                name="activity_event_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_activity_member", "activity_log", ["member_id"])
    op.create_index("idx_activity_date", "activity_log", ["created_at"])
    op.create_index(
        "idx_activity_member_date", "activity_log", ["member_id", "created_at"]
    )

    # ── subscriptions ─────────────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "tier",
            sa.Enum("free", "pro", "business", name="subscription_tier", create_type=False),
            default="free",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active", "trial", "frozen", "expired", "cancelled",
                name="subscription_status",
                create_type=False,
            ),
            default="active",
            nullable=False,
        ),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True)),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("frozen_until", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── payments ──────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(8), default="RUB", nullable=False),
        sa.Column(
            "tier",
            sa.Enum("free", "pro", "business", name="subscription_tier", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "success", "failed", "refunded",
                name="payment_status",
                create_type=False,
            ),
            default="pending",
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_payment_id", sa.String(256)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_payments_user", "payments", ["user_id"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("subscriptions")
    op.drop_table("activity_log")
    op.drop_table("channel_members")
    op.drop_table("channels")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS activity_event_type")
    op.execute("DROP TYPE IF EXISTS subscription_status")
    op.execute("DROP TYPE IF EXISTS subscription_tier")
