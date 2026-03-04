-- Инициализация БД при первом запуске контейнера
-- Здесь можно добавить расширения PostgreSQL

-- UUID генерация
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Статистика запросов (для мониторинга медленных запросов)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Полнотекстовый поиск (если понадобится)
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
