"""
RefLens — Channel Handler
Подключение канала: получаем @username или пересланное сообщение,
проверяем права бота через Telegram API, сохраняем в БД.
"""
import logging
from typing import Any, Dict

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.repositories.channel_repository import ChannelRepository
from bot.states.states import OnboardingStates

router = Router()
logger = logging.getLogger(__name__)

# ─── Клавиатуры ──────────────────────────────────────────────────────────────

def retry_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Попробовать снова", callback_data="channel:check")
    builder.button(text="❓ Помощь", callback_data="channel:help")
    builder.adjust(1)
    return builder.as_markup()

def connected_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📈 Открыть аналитику", callback_data="analytics:open")
    builder.button(text="➕ Подключить ещё канал", callback_data="channel:add_another")
    builder.adjust(1)
    return builder.as_markup()

def main_menu_kb():
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📈 Аналитика"), KeyboardButton(text="🌳 Дерево связей")],
            [KeyboardButton(text="⭐ Топ рефереров"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="💎 Подписка"), KeyboardButton(text="🆘 Поддержка")],
        ],
        resize_keyboard=True,
    )


# ─── Шаг 1: пользователь нажал «Я добавил, проверить» ────────────────────────

@router.callback_query(F.data == "channel:check")
async def ask_for_channel(callback: CallbackQuery, state: FSMContext) -> None:
    """Просим ввести @username канала или переслать сообщение из него."""
    await state.set_state(OnboardingStates.waiting_channel_add)
    await callback.message.edit_text(
        "Отправь @username канала или перешли любое сообщение из него.\n\n"
        "Пример: @mychannel"
    )
    await callback.answer()


# ─── Шаг 2: пользователь прислал @username ────────────────────────────────────

@router.message(OnboardingStates.waiting_channel_add, F.text.startswith("@"))
async def verify_channel_by_username(
    message: Message,
    bot: Bot,
    state: FSMContext,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    username = message.text.strip().lstrip("@")
    await _verify_and_save(message, bot, state, f"@{username}", db_user, session_maker)


# ─── Шаг 2б: пользователь переслал сообщение из канала ───────────────────────

@router.message(OnboardingStates.waiting_channel_add, F.forward_from_chat)
async def verify_channel_by_forward(
    message: Message,
    bot: Bot,
    state: FSMContext,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    chat_id = message.forward_from_chat.id
    await _verify_and_save(message, bot, state, chat_id, db_user, session_maker)


# ─── Шаг 2в: прислал что-то непонятное ───────────────────────────────────────

@router.message(OnboardingStates.waiting_channel_add)
async def wrong_input(message: Message) -> None:
    await message.answer(
        "Не понял 🤔 Отправь @username канала (например, @mychannel) "
        "или перешли любое сообщение из канала."
    )


# ─── Основная логика проверки ─────────────────────────────────────────────────

async def _verify_and_save(
    message: Message,
    bot: Bot,
    state: FSMContext,
    chat_identifier: Any,
    db_user: Any,
    session_maker: Any,
) -> None:
    """Проверяем права бота и сохраняем канал в БД."""

    # 1. Получаем инфо о чате
    try:
        chat = await bot.get_chat(chat_identifier)
    except TelegramBadRequest:
        await message.answer(
            "❌ Канал не найден. Проверь @username и попробуй снова.",
            reply_markup=retry_kb(),
        )
        return
    except TelegramForbiddenError:
        await message.answer(
            "❌ Бот не имеет доступа к этому каналу.\n"
            "Убедись что бот добавлен как администратор.",
            reply_markup=retry_kb(),
        )
        return
    except Exception as e:
        logger.error("get_chat failed", chat=chat_identifier, error=str(e))
        await message.answer(
            "❌ Не удалось получить информацию о канале. Попробуй позже.",
            reply_markup=retry_kb(),
        )
        return

    # 2. Проверяем что бот — администратор
    try:
        me = await bot.get_me()
        bot_member = await bot.get_chat_member(chat.id, me.id)
        if bot_member.status not in ("administrator", "creator"):
            await message.answer(
                f"❌ Я не администратор канала «{chat.title}».\n\n"
                "Добавь меня как администратора с правами:\n"
                "• Читать сообщения\n"
                "• Видеть участников\n\n"
                "Затем попробуй снова.",
                reply_markup=retry_kb(),
            )
            return
    except Exception as e:
        logger.error("get_chat_member failed", chat_id=chat.id, error=str(e))
        await message.answer(
            "❌ Не удалось проверить права бота. Попробуй позже.",
            reply_markup=retry_kb(),
        )
        return

    # 3. Сохраняем в БД
    if session_maker is None or db_user is None:
        logger.error("session_maker or db_user is None in channel handler")
        await message.answer("❌ Внутренняя ошибка. Попробуй позже.")
        return

    try:
        async with session_maker() as session:
            repo = ChannelRepository(session)
            channel, created = await repo.get_or_create_channel(
                telegram_chat_id=chat.id,
                owner_id=db_user.id,
                title=chat.title or str(chat.id),
                username=chat.username,
                invite_link=getattr(chat, "invite_link", None),
            )
            await session.commit()
    except Exception as e:
        logger.error("Failed to save channel", chat_id=chat.id, error=str(e))
        await message.answer(
            "❌ Ошибка при сохранении канала. Попробуй позже.",
            reply_markup=retry_kb(),
        )
        return

    await state.clear()

    if created:
        await message.answer(
            f"✅ Канал «{chat.title}» подключён.\n\n"
            "Начинаю собирать статистику — первые данные появятся "
            "как только произойдут события в канале.",
            reply_markup=connected_kb(),
        )
    else:
        await message.answer(
            f"ℹ️ Канал «{chat.title}» уже был подключён.",
            reply_markup=connected_kb(),
        )

    await message.answer("Главное меню:", reply_markup=main_menu_kb())


# ─── Help ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "channel:help")
async def channel_help(callback: CallbackQuery) -> None:
    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data="channel:check")
    await callback.message.edit_text(
        "Как добавить бота администратором:\n\n"
        "1. Открой настройки канала\n"
        "2. Администраторы → Добавить администратора\n"
        "3. Найди @RefLensBot и добавь\n"
        "4. Включи права: читать сообщения\n"
        "5. Вернись и отправь @username канала\n\n"
        "Не получается? @reflens_support",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()
