"""
RefLens — FSM States
Все состояния конечного автомата бота.
"""
from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """Онбординг нового пользователя."""
    waiting_consent = State()        # Ждём согласие на обработку данных
    waiting_channel_add = State()    # Ждём добавления бота в канал
    setup_min_age = State()          # Настройка мин. возраста аккаунта
    setup_min_messages = State()     # Настройка мин. активности


class ChannelStates(StatesGroup):
    """Подключение канала."""
    waiting_channel_add = State()    # Ждём добавления бота в канал
    waiting_verify = State()         # Проверяем права бота


class AnalyticsStates(StatesGroup):
    """Просмотр аналитики."""
    selecting_channel = State()      # Выбор канала (если несколько)
    selecting_period = State()       # Выбор периода


class TreeStates(StatesGroup):
    """Просмотр дерева связей."""
    selecting_channel = State()      # Выбор канала
    selecting_depth = State()        # Выбор глубины дерева


class SubscriptionStates(StatesGroup):
    """Покупка и управление подпиской."""
    selecting_tier = State()         # Выбор тарифа
    selecting_payment_method = State()  # Выбор способа оплаты
    waiting_payment = State()        # Ждём оплаты
    cancellation_reason = State()    # Причина отмены


class SupportStates(StatesGroup):
    """Обращение в поддержку."""
    waiting_message = State()        # Ждём сообщение пользователя
