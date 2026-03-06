"""RefLens — Support Handler."""

import logging
import re
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.states.states import SupportStates

router = Router()
logger = logging.getLogger(__name__)

FAQ = [
    {
        "q": "Как подключить канал?",
        "a": (
            "1️⃣ Добавь меня в канал как администратора\n"
            "2️⃣ Дай права: читать сообщения, видеть участников\n"
            "3️⃣ Вернись в бот и отправь @username канала"
        ),
    },
    {
        "q": "Что такое реферальная аналитика?",
        "a": (
            "RefLens отслеживает кто из подписчиков привёл новых людей. "
            "Показываем дерево связей, активность и отсеиваем ботов."
        ),
    },
    {
        "q": "Сколько стоит подписка?",
        "a": "⚡ Pro — 790 ₽/мес\n💎 Business — 1990 ₽/мес\n\nПодробнее: /tariffs",
    },
    {
        "q": "Как отменить подписку?",
        "a": (
            "Команда /cancel — автопродление отключится, "
            "доступ сохранится до конца оплаченного периода."
        ),
    },
    {
        "q": "Как удалить свои данные?",
        "a": (
            "Команда /delete_account — удалим все данные в течение 24 часов.\n"
            "Отозвать согласие: /revoke_consent"
        ),
    },
    {
        "q": "Почему бот не видит участников?",
        "a": (
            "Проверь права бота в канале: нужны «Читать сообщения» и «Видеть участников». "
            "Если права есть — напиши оператору."
        ),
    },
]


def support_menu_kb() -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="📖 FAQ", callback_data="support:faq")
    builder.button(text="👨‍💻 Написать оператору", callback_data="support:operator")
    builder.adjust(1)
    return builder.as_markup()


def faq_kb() -> Any:
    builder = InlineKeyboardBuilder()
    for i, item in enumerate(FAQ):
        builder.button(text=item["q"], callback_data=f"support:faq:{i}")
    builder.button(text="◀️ Назад", callback_data="support:back")
    builder.adjust(1)
    return builder.as_markup()


def back_kb() -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ В меню поддержки", callback_data="support:back")
    return builder.as_markup()


SUPPORT_TEXT = "🆘 <b>Поддержка RefLens</b>\n\nВыбери что тебе нужно:"


@router.message(Command("support"))
@router.message(F.text == "🆘 Поддержка")
async def cmd_support(message: Message) -> None:
    await message.answer(SUPPORT_TEXT, reply_markup=support_menu_kb())


@router.callback_query(F.data == "support:back")
async def support_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(SUPPORT_TEXT, reply_markup=support_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "support:faq")
async def support_faq(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📖 <b>Частые вопросы</b>\n\nВыбери вопрос:",
        reply_markup=faq_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("support:faq:"))
async def faq_answer(callback: CallbackQuery) -> None:
    idx = int(callback.data.split(":")[2])
    if 0 <= idx < len(FAQ):
        item = FAQ[idx]
        await callback.message.edit_text(
            f"<b>{item['q']}</b>\n\n{item['a']}",
            reply_markup=back_kb(),
        )
    else:
        await callback.answer("Вопрос не найден", show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "support:operator")
async def support_operator(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportStates.waiting_message)
    await callback.message.edit_text(
        "👨‍💻 Напиши сообщение — ответим в ближайшее время.\n"
        "Можно прикрепить текст, фото или файл.",
        reply_markup=back_kb(),
    )
    await callback.answer()


@router.message(SupportStates.waiting_message)
async def handle_user_message(
    message: Message,
    bot: Bot,
    state: FSMContext,
    db_user: Any = None,
) -> None:
    if not db_user or not settings.SUPPORT_CHAT_ID:
        await message.answer("❌ Ошибка отправки. Напиши напрямую @reflens_support")
        await state.clear()
        return

    username = db_user.username or "нет username"
    header = f"📩 @{username} (ID: {db_user.telegram_id})\n\n"

    try:
        await bot.send_message(
            chat_id=settings.SUPPORT_CHAT_ID,
            text=header + (message.text or message.caption or "[Медиафайл]"),
        )
        if message.photo:
            await bot.send_photo(
                settings.SUPPORT_CHAT_ID,
                message.photo[-1].file_id,
                caption=f"Фото от {db_user.telegram_id}",
            )
        elif message.document:
            await bot.send_document(
                settings.SUPPORT_CHAT_ID,
                message.document.file_id,
                caption=f"Документ от {db_user.telegram_id}",
            )

        await message.answer("✅ Сообщение отправлено. Ответим в этом чате.")
    except Exception as e:
        logger.error("Failed to forward to support", error=str(e))
        await message.answer("❌ Ошибка при отправке. Попробуй позже или напиши @reflens_support")

    await state.clear()


@router.message(F.reply_to_message)
async def operator_reply(message: Message, bot: Bot) -> None:
    """Оператор отвечает на сообщение пользователя из чата поддержки."""
    if not settings.SUPPORT_CHAT_ID:
        return
    if message.chat.id != settings.SUPPORT_CHAT_ID:
        return

    reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"ID: (\d+)", reply_text)
    if not match:
        await message.reply("Не найден ID пользователя в сообщении.")
        return

    user_id = int(match.group(1))
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"👨‍💻 <b>Ответ поддержки:</b>\n\n{message.text or message.caption}",
        )
        await message.reply("✅ Ответ отправлен.")
    except Exception as e:
        logger.error("Failed to send reply to user", user_id=user_id, error=str(e))
        await message.reply("❌ Не удалось отправить — пользователь мог заблокировать бота.")
