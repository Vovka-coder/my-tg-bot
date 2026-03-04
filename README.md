# 🤖 [Название бота]

> [Краткое описание: что делает бот и для кого]

---

## 🚀 Быстрый старт (локальная разработка)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/your-org/your-bot.git
cd your-bot

# 2. Создать .env из шаблона
cp .env.example .env
# Заполнить .env актуальными значениями (получить у владельца через защищённый канал)

# 3. Установить pre-commit хуки
pip install pre-commit
pre-commit install

# 4. Запустить все сервисы
docker-compose up -d

# 5. Применить миграции
docker-compose exec bot alembic upgrade head

# 6. Проверить логи
docker-compose logs -f bot
```

---

## 🏗️ Архитектура

```
bot/
├── handlers/       # Обработчики команд и сообщений (aiogram Router)
├── keyboards/      # Reply и Inline клавиатуры
├── middlewares/    # Rate limiting, логирование, i18n
├── database/       # SQLAlchemy модели, Alembic миграции, репозитории
├── services/       # Внешние сервисы: AI, платежи, email, S3
├── utils/          # Вспомогательные функции
├── locales/        # Файлы переводов (ru.json, en.json)
├── config.py       # Pydantic Settings — конфигурация из .env
└── main.py         # Точка входа
```

**Стек:** Python 3.12, aiogram 3, PostgreSQL 16, Redis 7, Celery 5

---

## 🧪 Тесты

```bash
# Запустить все тесты с покрытием
pytest

# Только линтеры
black --check . && isort --check-only . && flake8 .

# Аудит безопасности зависимостей
pip-audit -r requirements.txt
```

---

## 📦 Деплой

```bash
# Production деплой (на сервере)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Применить новые миграции (без простоя)
docker-compose exec bot alembic upgrade head
```

---

## 📚 Документация

- [Definition of Done](docs/DEFINITION_OF_DONE.md)
- [Политика работы с секретами](docs/SECRETS_POLICY.md)
- [Архитектурные решения (ADR)](docs/adr/)

---

## 👥 Разработка

- Все изменения — через Pull Request, прямые пуши в `main` запрещены
- CI проверяет: линтеры → безопасность → тесты
- Фича считается готовой только при выполнении [DoD](docs/DEFINITION_OF_DONE.md)
