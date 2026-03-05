"""
RefLens — Tree Handler
/tree и кнопка «🌳 Дерево связей»
"""

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.repositories.channel_repository import ChannelRepository
from bot.services.tree_service import TreeService

router = Router()
logger = logging.getLogger(__name__)


# ─── Клавиатуры ──────────────────────────────────────────────────────────────


def depth_kb(channel_id: int) -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="2 уровня", callback_data=f"tree:depth:{channel_id}:2")
    builder.button(text="3 уровня", callback_data=f"tree:depth:{channel_id}:3")
    builder.button(text="Все уровни", callback_data=f"tree:depth:{channel_id}:all")
    builder.adjust(3)
    return builder.as_markup()


def tree_actions_kb(channel_id: int) -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Экспорт CSV", callback_data=f"export:tree:{channel_id}")
    builder.button(text="◀️ Назад", callback_data="tree:back")
    builder.adjust(1)
    return builder.as_markup()


# ─── /tree и кнопка меню ─────────────────────────────────────────────────────


@router.message(Command("tree"))
@router.message(F.text == "🌳 Дерево связей")
async def cmd_tree(
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
        await message.answer(
            f"Канал: <b>{channels[0].title}</b>\nВыбери глубину дерева:",
            reply_markup=depth_kb(channels[0].id),
        )
    else:
        builder = InlineKeyboardBuilder()
        for ch in channels:
            builder.button(text=ch.title, callback_data=f"tree:channel:{ch.id}")
        builder.adjust(1)
        await message.answer(
            "Выбери канал:",
            reply_markup=builder.as_markup(),
        )


# ─── Выбор канала ─────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("tree:channel:"))
async def select_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        "Выбери глубину дерева:",
        reply_markup=depth_kb(channel_id),
    )
    await callback.answer()


# ─── Выбор глубины → построение дерева ───────────────────────────────────────


@router.callback_query(F.data.startswith("tree:depth:"))
async def show_tree(
    callback: CallbackQuery,
    session_maker: Any = None,
) -> None:
    parts = callback.data.split(":")
    channel_id = int(parts[2])
    depth_raw = parts[3]
    max_depth = None if depth_raw == "all" else int(depth_raw)

    if not session_maker:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    await callback.message.edit_text("🔍 Строю дерево...")

    try:
        async with session_maker() as session:
            svc = TreeService(session)
            nodes = await svc.get_tree(channel_id, max_depth)

        text = TreeService.format_tree(nodes)
        await callback.message.edit_text(
            text,
            reply_markup=tree_actions_kb(channel_id),
        )
    except Exception as e:
        logger.error("Tree build failed", channel_id=channel_id, error=str(e))
        await callback.message.edit_text(
            "❌ Не удалось построить дерево. Попробуй позже.",
            reply_markup=depth_kb(channel_id),
        )

    await callback.answer()


# ─── Назад ────────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "tree:back")
async def tree_back(
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
            "Выбери глубину дерева:",
            reply_markup=depth_kb(channels[0].id),
        )
    else:
        builder = InlineKeyboardBuilder()
        for ch in channels:
            builder.button(text=ch.title, callback_data=f"tree:channel:{ch.id}")
        builder.adjust(1)
        await callback.message.edit_text(
            "Выбери канал:",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()
