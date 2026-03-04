"""
RefLens — /start handler + онбординг
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.states.states import OnboardingStates

router = Router()

# ─── Тексты (ToV RefLens) ────────────────────────────────────────────────────

WELCOME_TEXT = (
    "Привет! 👋 Я RefLens — твой личный аналитик рефералов.\n\n"
    "Помогу разобраться, кто из подписчиков реально активен "
    "и приводит качественную аудиторию.\n\n"
    "Прежде чем начать — мне нужно твоё согласие на обработку данных."
)

CONSENT_INFO_TEXT = (
    "🔍 Что именно я собираю:\n"
    "• Telegram ID и никнейм — для идентификации\n"
    "• Факты активности в подключённых каналах: "
    "вступления/выходы, количество сообщений и реакций\n\n"
    "Я не читаю содержимое сообщений и не передаю данные третьим лицам.\n\n"
    "Подробнее: /privacy\n\n"
    "Отозвать согласие можно в любой момент через /revoke_consent."
)

CHANNEL_INSTRUCTION_TEXT = (
    "Готово. Теперь подключим твой канал 🎉\n\n"
    "1️⃣ Добавь меня в канал как администратора\n"
    "   Нужны права: читать сообщения, видеть участников\n\n"
    "2️⃣ Нажми кнопку ниже когда добавишь"
)

ALREADY_ONBOARDED_TEXT = (
    "С возвращением! 👌\n"
    "Всё готово — переходи к аналитике."
)

CHANNEL_HELP_TEXT = (
    "Как добавить бота администратором:\n\n"
    "1. Открой настройки своего канала\n"
    "2. Администраторы → Добавить администратора\n"
    "3. Найди @RefLensBot и добавь\n"
    "4. Включи права: читать сообщения\n\n"
    "Если не получается — @reflens_support"
)


# ─── Клавиатуры ──────────────────────────────────────────────────────────────

def consent_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять", callback_data="consent:accept")
    builder.button(text="ℹ️ Подробнее о данных", callback_data="consent:info")
    builder.adjust(1)
    return builder.as_markup()


def channel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я добавил, проверить", callback_data="channel:check")
    builder.button(text="❓ Как добавить?", callback_data="channel:help")
    builder.adjust(1)
    return builder.as_markup()


def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📈 Аналитика"), KeyboardButton(text="🌳 Дерево связей")],
            [KeyboardButton(text="⭐ Топ рефереров"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="💎 Подписка"), KeyboardButton(text="🆘 Поддержка")],
        ],
        resize_keyboard=True,
    )


# ─── Handlers ────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db_user=None):
    """
    Точка входа. db_user приходит из UserMiddleware.
    Если пользователь уже прошёл онбординг — главное меню.
    Если нет — начинаем с согласия.
    """
    if db_user and db_user.consent_given:
        await message.answer(ALREADY_ONBOARDED_TEXT, reply_markup=main_menu_kb())
        return

    await state.set_state(OnboardingStates.waiting_consent)
    await message.answer(WELCOME_TEXT, reply_markup=consent_kb())


@router.callback_query(F.data == "consent:info", OnboardingStates.waiting_consent)
async def consent_info(callback: CallbackQuery):
    """Показать подробности об обработке данных."""
    await callback.message.edit_text(CONSENT_INFO_TEXT, reply_markup=consent_kb())
    await callback.answer()


@router.callback_query(F.data == "consent:accept", OnboardingStates.waiting_consent)
async def consent_accept(callback: CallbackQuery, state: FSMContext, user_repo=None):
    """Пользователь принял согласие — фиксируем и переходим к подключению канала."""
    if user_repo:
        await user_repo.set_consent(callback.from_user.id)

    await state.set_state(OnboardingStates.waiting_channel_add)
    await callback.message.edit_text(
        CHANNEL_INSTRUCTION_TEXT,
        reply_markup=channel_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "channel:help", OnboardingStates.waiting_channel_add)
async def channel_help(callback: CallbackQuery):
    """Инструкция по добавлению бота."""
    await callback.message.edit_text(CHANNEL_HELP_TEXT, reply_markup=channel_kb())
    await callback.answer()


@router.callback_query(F.data == "channel:check", OnboardingStates.waiting_channel_add)
async def channel_check(callback: CallbackQuery, state: FSMContext):
    """
    Проверяем что бот добавлен в канал.
    TODO: реальная проверка через ChannelService.verify_bot_in_channel()
    Пока — заглушка, завершаем онбординг.
    """
    await state.clear()
    await callback.message.edit_text(
        "Готово 🎉 Можем начинать.\n\nВот главное меню:"
    )
    await callback.message.answer(
        "Выбери раздел:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Показать главное меню."""
    await message.answer("Главное меню:", reply_markup=main_menu_kb())
