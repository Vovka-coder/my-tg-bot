"""
RefLens — Analytics Handler
/stats и кнопка «📈 Аналитика» из главного меню.
"""

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.repositories.channel_repository import ChannelRepository
from bot.services.analytics_service import AnalyticsService

router = Router()
logger = logging.getLogger(__name__)


# ─── Клавиатуры ──────────────────────────────────────────────────────────────


def period_kb(channel_id: int) -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="7 дней", callback_data=f"stats:period:{channel_id}:7")
    builder.button(text="30 дней", callback_data=f"stats:period:{channel_id}:30")
    builder.button(text="Всё время", callback_data=f"stats:period:{channel_id}:all")
    builder.adjust(3)
    return builder.as_markup()


def stats_actions_kb(channel_id: int) -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌳 Дерево связей", callback_data=f"tree:show:{channel_id}")
    builder.button(text="📤 Экспорт CSV", callback_data=f"export:csv:{channel_id}")
    builder.button(text="◀️ Назад", callback_data="stats:back")
    builder.adjust(2, 1)
    return builder.as_markup()


# ─── /stats и кнопка меню ────────────────────────────────────────────────────


@router.message(Command("stats"))
@router.message(F.text == "📈 Аналитика")
async def cmd_stats(
    message: Message,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    if not db_user or not session_maker:
        await message.answer("❌ Ошибка. Попробуй позже.")
        return

    async with session_maker() as session:
        repo = ChannelRepository(session)
        channels = await repo.get_user_channels(db_user.id)

    if not channels:
        await message.answer(
            "У тебя пока нет подключённых каналов.\n" "Подключи первый через /connect."
        )
        return

    if len(channels) == 1:
        # Сразу к выбору периода
        await message.answer(
            f"Канал: <b>{channels[0].title}</b>\nВыбери период:",
            reply_markup=period_kb(channels[0].id),
        )
    else:
        # Показываем список каналов
        builder = InlineKeyboardBuilder()
        for ch in channels:
            builder.button(text=ch.title, callback_data=f"stats:channel:{ch.id}")
        builder.adjust(1)
        await message.answer(
            "Выбери канал для аналитики:",
            reply_markup=builder.as_markup(),
        )


# ─── Выбор канала (если несколько) ───────────────────────────────────────────


@router.callback_query(F.data.startswith("stats:channel:"))
async def select_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        "Выбери период:",
        reply_markup=period_kb(channel_id),
    )
    await callback.answer()


# ─── Выбор периода → показ статистики ────────────────────────────────────────


@router.callback_query(F.data.startswith("stats:period:"))
async def show_stats(
    callback: CallbackQuery,
    session_maker: Any = None,
) -> None:
    parts = callback.data.split(":")
    channel_id = int(parts[2])
    period_raw = parts[3]
    period_days = None if period_raw == "all" else int(period_raw)

    if not session_maker:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    await callback.message.edit_text("🔍 Считаю...")

    try:
        async with session_maker() as session:
            # Получаем название канала
            repo = ChannelRepository(session)
            channel = await repo.get(id=channel_id)
            if not channel:
                await callback.message.edit_text("❌ Канал не найден.")
                await callback.answer()
                return

            svc = AnalyticsService(session)
            stats = await svc.get_channel_stats(channel_id, period_days)

        text = AnalyticsService.format_stats(stats, channel.title or str(channel_id))
        await callback.message.edit_text(
            text,
            reply_markup=stats_actions_kb(channel_id),
        )
    except Exception as e:
        logger.error("Analytics failed", channel_id=channel_id, error=str(e))
        await callback.message.edit_text(
            "❌ Не удалось получить статистику. Попробуй позже.",
            reply_markup=period_kb(channel_id),
        )

    await callback.answer()


# ─── Кнопка «Назад» ──────────────────────────────────────────────────────────


@router.callback_query(F.data == "stats:back")
async def stats_back(
    callback: CallbackQuery,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    if not db_user or not session_maker:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    async with session_maker() as session:
        repo = ChannelRepository(session)
        channels = await repo.get_user_channels(db_user.id)

    if len(channels) == 1:
        await callback.message.edit_text(
            "Выбери период:",
            reply_markup=period_kb(channels[0].id),
        )
    else:
        builder = InlineKeyboardBuilder()
        for ch in channels:
            builder.button(text=ch.title, callback_data=f"stats:channel:{ch.id}")
        builder.adjust(1)
        await callback.message.edit_text(
            "Выбери канал:",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()
