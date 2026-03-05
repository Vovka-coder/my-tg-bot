"""RefLens — Subscription Handler."""

import logging
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.database.models import SubscriptionTier
from bot.services.subscription_service import SubscriptionService

router = Router()
logger = logging.getLogger(__name__)

PRICES = {
    SubscriptionTier.PRO: {"rub": 79000, "stars": 79},
    SubscriptionTier.BUSINESS: {"rub": 199000, "stars": 199},
}
PERIOD_DAYS = 30

TARIFF_TEXT = (
    "💎 <b>Тарифы RefLens</b>\n\n"
    "🆓 <b>Free</b> — до 100 рефералов, базовый антифрод\n\n"
    "⚡ <b>Pro — 790 ₽/мес</b>\n"
    "• Безлимит рефералов\n"
    "• Аналитика активности\n"
    "• Дерево связей (/tree)\n"
    "• Экспорт CSV\n\n"
    "💎 <b>Business — 1990 ₽/мес</b>\n"
    "• Всё из Pro\n"
    "• AI-антифрод\n"
    "• Google Sheets экспорт\n"
)


def tariff_kb() -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Pro — 790 ₽", callback_data="sub:tier:pro")
    builder.button(text="💎 Business — 1990 ₽", callback_data="sub:tier:business")
    builder.adjust(1)
    return builder.as_markup()


def payment_kb(tier_value: str) -> Any:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Картой (ЮKassa)", callback_data=f"sub:pay:rub:{tier_value}")
    builder.button(text="⭐ Telegram Stars", callback_data=f"sub:pay:stars:{tier_value}")
    builder.button(text="◀️ Назад", callback_data="sub:back")
    builder.adjust(1)
    return builder.as_markup()


@router.message(Command("tariffs"))
@router.message(F.text == "💎 Подписка")
async def show_tariffs(
    message: Message,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    tier_label = "free"
    if db_user and session_maker:
        async with session_maker() as session:
            svc = SubscriptionService(session)
            sub = await svc.get_or_create(db_user.id)
            tier_label = sub.tier.value

    await message.answer(
        TARIFF_TEXT + f"\nТвой тариф сейчас: <b>{tier_label}</b>",
        reply_markup=tariff_kb(),
    )


@router.callback_query(F.data == "sub:back")
async def tariffs_back(
    callback: CallbackQuery,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    tier_label = "free"
    if db_user and session_maker:
        async with session_maker() as session:
            svc = SubscriptionService(session)
            sub = await svc.get_or_create(db_user.id)
            tier_label = sub.tier.value

    await callback.message.edit_text(
        TARIFF_TEXT + f"\nТвой тариф сейчас: <b>{tier_label}</b>",
        reply_markup=tariff_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:tier:"))
async def select_tier(callback: CallbackQuery) -> None:
    tier_str = callback.data.split(":")[2]
    names = {"pro": "Pro — 790 ₽/мес", "business": "Business — 1990 ₽/мес"}
    await callback.message.edit_text(
        f"Тариф: <b>{names.get(tier_str, tier_str)}</b>\n\nВыбери способ оплаты:",
        reply_markup=payment_kb(tier_str),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:pay:"))
async def process_payment(callback: CallbackQuery, bot: Bot) -> None:
    parts = callback.data.split(":")
    currency = parts[2]
    tier_str = parts[3]

    try:
        tier = SubscriptionTier(tier_str)
    except ValueError:
        await callback.answer("Неверный тариф", show_alert=True)
        return

    title = f"RefLens {tier.value.capitalize()}"
    description = "Подписка на 30 дней"
    payload = f"subscription:{tier.value}:{currency}"

    if currency == "stars":
        prices = [LabeledPrice(label=title, amount=PRICES[tier]["stars"])]
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
        )
    else:
        prices = [LabeledPrice(label=title, amount=PRICES[tier]["rub"])]
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=title,
            description=description,
            payload=payload,
            provider_token=settings.YOOKASSA_TOKEN or "",
            currency="RUB",
            prices=prices,
        )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(
    message: Message,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "subscription":
        await message.answer("Ошибка платежа. Обратись в поддержку: /support")
        return

    tier_str = parts[1]
    try:
        tier = SubscriptionTier(tier_str)
    except ValueError:
        await message.answer("Ошибка платежа. Обратись в поддержку: /support")
        return

    if db_user and session_maker:
        async with session_maker() as session:
            svc = SubscriptionService(session)
            await svc.activate(db_user.id, tier, PERIOD_DAYS)

    await message.answer(
        f"✅ Оплата прошла успешно!\n\n"
        f"Тариф <b>{tier.value.capitalize()}</b> активирован на 30 дней.\n"
        "Спасибо за доверие! 🎉"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    builder = InlineKeyboardBuilder()
    builder.button(text="Всё равно отменить", callback_data="sub:confirm_cancel")
    builder.button(text="❄️ Заморозить на месяц", callback_data="sub:confirm_freeze")
    builder.button(text="◀️ Оставить подписку", callback_data="sub:keep")
    builder.adjust(1)
    await message.answer(
        "Жаль расставаться 😔\n\n"
        "Если дело в цене — можем заморозить на месяц: данные сохранятся, платить не нужно.\n\n"
        "Если всё же решил уйти — подтверди ниже.",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "sub:confirm_cancel")
async def confirm_cancel(
    callback: CallbackQuery,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    builder = InlineKeyboardBuilder()
    builder.button(text="Дорого", callback_data="sub:reason:price")
    builder.button(text="Мало функций", callback_data="sub:reason:features")
    builder.button(text="Не использую", callback_data="sub:reason:unused")
    builder.button(text="Другое", callback_data="sub:reason:other")
    builder.adjust(2)
    await callback.message.edit_text(
        "Расскажи почему уходишь — это поможет нам стать лучше:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:reason:"))
async def cancel_reason(
    callback: CallbackQuery,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    if db_user and session_maker:
        async with session_maker() as session:
            svc = SubscriptionService(session)
            await svc.cancel(db_user.id)
    await callback.message.edit_text(
        "Подписка отменена. Доступ сохранится до конца оплаченного периода.\n\n"
        "Будем рады видеть тебя снова 👋"
    )
    await callback.answer()


@router.callback_query(F.data == "sub:keep")
async def keep_subscription(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Отлично, продолжаем! 💪")
    await callback.answer()


@router.message(Command("freeze"))
async def cmd_freeze(message: Message) -> None:
    builder = InlineKeyboardBuilder()
    builder.button(text="❄️ Заморозить на 30 дней", callback_data="sub:confirm_freeze")
    builder.button(text="◀️ Назад", callback_data="sub:keep")
    builder.adjust(1)
    await message.answer(
        "Заморозка приостанавливает подписку на 30 дней.\n"
        "Данные сохранятся, платить не нужно.\n\n"
        "После окончания заморозки доступ восстановится автоматически.",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "sub:confirm_freeze")
async def confirm_freeze(
    callback: CallbackQuery,
    db_user: Any = None,
    session_maker: Any = None,
) -> None:
    if not db_user or not session_maker:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    try:
        async with session_maker() as session:
            svc = SubscriptionService(session)
            sub = await svc.freeze(db_user.id, days=30)
        until = sub.frozen_until.strftime("%d.%m.%Y")
        await callback.message.edit_text(
            f"❄️ Подписка заморожена до {until}.\n"
            "После этой даты доступ восстановится автоматически."
        )
    except ValueError as e:
        await callback.message.edit_text(f"❌ {e}")
    await callback.answer()
