# RefLens — Architecture Document v1.0

## Стек

- **Bot:** Python 3.12, aiogram 3.13
- **DB:** PostgreSQL 16, SQLAlchemy 2, Alembic
- **Cache/FSM:** Redis 7
- **Queue:** Celery 5 (брокер — Redis)
- **Storage:** S3 (Yandex Object Storage) — для CSV экспортов
- **Monitoring:** Sentry, structlog

---

## Структура проекта

```
bot/
├── handlers/          # Роутеры aiogram — входная точка
├── middlewares/       # Throttling, подписка, логирование
├── services/          # Бизнес-логика
├── repositories/      # Доступ к данным (Repository pattern)
├── database/
│   ├── models.py      # SQLAlchemy ORM модели
│   ├── session.py     # Фабрика сессий
│   └── migrations/    # Alembic миграции
├── tasks/             # Celery-задачи
├── keyboards/         # Reply + Inline клавиатуры
├── states/            # FSM состояния
├── utils/             # Хелперы
├── locales/           # i18n (ru/en)
├── config.py
└── main.py
```

---

## Слои архитектуры

### Handlers (входная точка)
Принимают updates от Telegram, вызывают сервисы, возвращают ответ.
Не содержат бизнес-логики.

```
handlers/
├── start.py        # /start, онбординг, согласие
├── channel.py      # /connect, подключение канала
├── analytics.py    # /stats, /top
├── tree.py         # /tree
├── subscription.py # /tariffs, /cancel, /freeze
├── support.py      # /support, FAQ
└── admin.py        # Команды администратора
```

### Middlewares
| Middleware | Назначение |
|-----------|-----------|
| `ThrottlingMiddleware` | Rate limiting через Redis |
| `SubscriptionMiddleware` | Проверка доступа к платным фичам |
| `LoggingMiddleware` | Структурированное логирование |
| `UserMiddleware` | Автосоздание/обновление пользователя в БД |

### Services (бизнес-логика)
| Сервис | Ответственность |
|--------|----------------|
| `UserService` | Регистрация, согласие, профиль |
| `ChannelService` | Подключение, проверка прав, настройки |
| `ReferralService` | Дерево (CTE), топ-рефереры, статистика |
| `AnalyticsService` | Агрегация активности за период |
| `AntifraudService` | Проверка участника по правилам |
| `PaymentService` | Счета ЮKassa/Stars, вебхуки |
| `SubscriptionService` | Статус, заморозка, отмена |
| `ExportService` | Генерация CSV, загрузка в S3 |

### Repositories (доступ к данным)
| Репозиторий | Таблица |
|------------|---------|
| `UserRepository` | users |
| `ChannelRepository` | channels |
| `ChannelMemberRepository` | channel_members |
| `ActivityLogRepository` | activity_log |
| `SubscriptionRepository` | subscriptions |
| `PaymentRepository` | payments |

---

## Celery — фоновые задачи

| Задача | Триггер | Периодичность | Зачем |
|--------|---------|--------------|-------|
| `generate_referral_tree` | Запрос пользователя | По событию | CTE может быть долгим при 10к+ участников |
| `export_analytics_csv` | Запрос пользователя | По событию | Генерация файла + загрузка в S3 |
| `recalculate_leaderboard` | Планировщик | Каждый час | Кэш топ-рефереров |
| `process_payment_webhook` | Вебхук ЮKassa | По событию | Не блокировать бота |
| `send_subscription_reminders` | Планировщик | Каждый день | За 3 дня и за 1 день до конца |
| `cleanup_old_logs` | Планировщик | Каждую неделю | Удалить activity_log старше 90 дней |
| `update_member_activity` | Планировщик | Каждые 15 минут | Актуализация last_seen |

---

## Redis — кэш и ключи

| Ключ | Данные | TTL | Инвалидация |
|------|--------|-----|-------------|
| `user:{telegram_id}:subscription` | tier, status, end_date | 5 мин | При изменении подписки |
| `channel:{chat_id}:stats:{period}` | Агрегированная статистика | 1 час | При новом событии в канале |
| `channel:{chat_id}:tree` | Текстовое дерево рефералов | 10 мин | При изменении состава |
| `leaderboard:{channel_id}:week` | Топ-10 рефереров | 1 час | Задача recalculate_leaderboard |
| `antifraud:{telegram_id}:check` | Результат проверки | 30 мин | При изменении активности |
| `rate_limit:{user_id}:{command}` | Счётчик запросов | По лимиту | Автоматически по TTL |
| `fsm:{bot_id}:{user_id}:{chat_id}` | FSM состояние (aiogram) | 24 часа | Автоматически |

### Стратегия инвалидации
- Новое событие активности → сброс `channel:{chat_id}:stats:*`
- Новый реферал → сброс `channel:{chat_id}:tree`
- Изменение подписки → сброс `user:{telegram_id}:subscription`

---

## Схема БД (кратко)

```
users
  └── channels (owner_id → users.id)
        └── channel_members (channel_id → channels.id)
              ├── referrer_id → channel_members.id  ← дерево рефералов
              └── activity_log (member_id → channel_members.id)

users
  ├── subscriptions (user_id → users.id, 1:1)
  └── payments (user_id → users.id, 1:N)
```

**Ключевое решение:** `referrer_id` в `channel_members`, а не в `users` —
один пользователь может быть в нескольких каналах с разными рефереррами.

---

## Запрос дерева рефералов (WITH RECURSIVE)

```sql
WITH RECURSIVE referral_tree AS (
    -- корень
    SELECT id, telegram_id, username, referrer_id, 1 AS level
    FROM channel_members
    WHERE id = :root_member_id

    UNION ALL

    -- рекурсия
    SELECT m.id, m.telegram_id, m.username, m.referrer_id, rt.level + 1
    FROM channel_members m
    INNER JOIN referral_tree rt ON m.referrer_id = rt.id
    WHERE rt.level < :max_depth  -- защита от бесконечной рекурсии
)
SELECT * FROM referral_tree ORDER BY level, id;
```

---

## S3 — хранение файлов

CSV-экспорты не хранятся на сервере. Поток:
1. Celery генерирует CSV в памяти
2. Загружает в S3 с TTL 24 часа
3. Бот отправляет пользователю presigned URL
4. Файл автоматически удаляется через 24 часа
