# RefLens — Справочник архитектуры для DeepSeek

Этот документ описывает **финальные решения** по архитектуре.
Используй его как источник истины при написании кода.

---

## 1. Схема БД — критические отличия от "стандартного" подхода

### ❌ НЕТ полей подписки в таблице `users`
```python
# НЕПРАВИЛЬНО (не делай так):
User.subscription_tier     # не существует
User.subscription_end      # не существует
User.auto_renew            # не существует
User.referrer_id           # не существует в users
User.message_count         # не существует
```

### ✅ Подписка — в отдельной таблице `subscriptions`
```python
# ПРАВИЛЬНО:
Subscription.tier          # SubscriptionTier enum: free/pro/business
Subscription.status        # SubscriptionStatus: active/trial/frozen/expired/cancelled
Subscription.current_period_end
Subscription.auto_renew
Subscription.frozen_until

# Доступ через relationship:
user.subscription.tier
user.subscription.current_period_end
```

### ✅ `referrer_id` — в `channel_members`, НЕ в `users`
```python
# НЕПРАВИЛЬНО:
User.referrer_id

# ПРАВИЛЬНО — один участник может быть в нескольких каналах с разными рефереррами:
ChannelMember.referrer_id  # FK на channel_members.id (самоссылка)
```

### ✅ Активность участника — через `activity_log`, НЕ поля в `channel_members`
```python
# НЕПРАВИЛЬНО:
ChannelMember.message_count   # не существует
ChannelMember.reaction_count  # не существует

# ПРАВИЛЬНО — считать через SQL:
SELECT COUNT(*) FROM activity_log
WHERE member_id = :member_id AND event_type = 'message'
```

### ✅ Возраст Telegram-аккаунта — `ChannelMember.account_created_at`
```python
# НЕПРАВИЛЬНО (это дата регистрации в боте, не возраст аккаунта):
User.created_at

# ПРАВИЛЬНО:
ChannelMember.account_created_at  # заполняется при вступлении если доступно
```

---

## 2. Полные схемы таблиц

### `users`
```
id, telegram_id, username, first_name, last_name,
language_code, consent_given, consent_at,
is_blocked, created_at, updated_at
```

### `channels`
```
id, owner_id (FK users), telegram_chat_id, title, username,
invite_link, is_active,
settings (JSONB: {"min_account_age_days": 7, "min_messages_count": 1}),
created_at
```

### `channel_members`
```
id, channel_id (FK channels), telegram_id, username,
referrer_id (FK channel_members.id — самоссылка),
account_created_at, is_bot, is_premium, is_verified,
status (member/left/kicked/restricted),
joined_at, left_at, last_seen
```

### `activity_log`
```
id, member_id (FK channel_members), event_type (join/leave/message/reaction),
metadata (JSONB), created_at
```

### `subscriptions`
```
id, user_id (FK users, UNIQUE), tier (free/pro/business),
status (active/trial/frozen/expired/cancelled),
trial_ends_at, current_period_start, current_period_end,
frozen_until, auto_renew, cancel_reason,
created_at, updated_at
```

### `payments`
```
id, user_id (FK users), amount (в копейках), currency,
tier, status (pending/success/failed/refunded),
provider (yookassa/telegram_stars), provider_payment_id,
created_at
```

---

## 3. Архитектура — как передаются зависимости

### ❌ НЕТ `data.get("session")` и `data.get("user")`
```python
# НЕПРАВИЛЬНО — таких ключей нет в data:
session = data.get("session")
user = data.get("user")
```

### ✅ Правильные ключи в `data`
```python
# Из UserMiddleware:
db_user = data["db_user"]           # объект User из БД (или None)
user_repo = data["user_repo"]       # UserRepository

# Из dp[...]:
session_maker = data["session_maker"]   # AsyncSessionLocal
redis = data["redis"]                   # Redis instance
settings = data["settings"]             # Settings object
```

### ✅ Как открывать сессию в handler/service
```python
# ПРАВИЛЬНО:
async with session_maker() as session:
    repo = SomeRepository(session)
    result = await repo.get(...)
    await session.commit()

# НЕПРАВИЛЬНО — не создавать engine внутри задачи каждый раз:
engine = create_async_engine(...)  # не делай так в задачах
```

---

## 4. Запросы подписки — правильный паттерн

```python
# Найти пользователей с истекающей подпиской:
from bot.database.models import User, Subscription, SubscriptionStatus, SubscriptionTier

stmt = (
    select(User)
    .join(User.subscription)
    .where(
        Subscription.tier.in_([SubscriptionTier.PRO, SubscriptionTier.BUSINESS]),
        Subscription.current_period_end <= deadline,
        Subscription.current_period_end > now,
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.auto_renew == True,
    )
    .options(selectinload(User.subscription))
)
```

---

## 5. Импорты — правильные пути

```python
# Модели:
from bot.database.models import (
    User, Channel, ChannelMember, ActivityLog,
    Subscription, Payment,
    SubscriptionTier, SubscriptionStatus,
    ActivityEventType, MemberStatus, PaymentStatus
)

# Сессия:
from bot.database.session import AsyncSessionLocal

# Репозитории:
from bot.repositories.user_repository import UserRepository
from bot.repositories.channel_repository import ChannelRepository

# Конфиг:
from bot.config import settings
```

---

## 6. Celery — правильная инициализация

```python
# Используй AsyncSessionLocal из bot.database.session, не создавай новый engine:
from bot.database.session import AsyncSessionLocal

async def my_task_async():
    async with AsyncSessionLocal() as session:
        ...

@shared_task
def my_task():
    asyncio.run(my_task_async())
```
