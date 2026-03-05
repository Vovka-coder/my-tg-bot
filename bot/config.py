from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

YOOKASSA_TOKEN: Optional[str] = None


class Settings(BaseSettings):
    # ──────────────────────────────────────────
    # TELEGRAM
    # ──────────────────────────────────────────
    BOT_TOKEN: str
    ADMIN_IDS: List[int] = Field(default=[])

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        return v

    # ──────────────────────────────────────────
    # POSTGRESQL
    # ──────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ──────────────────────────────────────────
    # REDIS
    # ──────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return (
                f"redis://:{self.REDIS_PASSWORD}"
                f"@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ──────────────────────────────────────────
    # AI ПРОВАЙДЕРЫ
    # ──────────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 10
    OPENAI_MONTHLY_BUDGET_USD: float = 50.0

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"

    AI_PROVIDER: str = "openai"  # openai | anthropic

    # ──────────────────────────────────────────
    # ПЛАТЕЖИ
    # ──────────────────────────────────────────
    YOOKASSA_SHOP_ID: Optional[str] = None
    YOOKASSA_SECRET_KEY: Optional[str] = None
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    TELEGRAM_PAYMENTS_TOKEN: Optional[str] = None

    # ──────────────────────────────────────────
    # ПРИЛОЖЕНИЕ
    # ──────────────────────────────────────────
    APP_ENV: str = "development"  # development | staging | production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "change_me"

    DEFAULT_LOCALE: str = "ru"
    SUPPORTED_LOCALES: str = "ru,en"

    WEBHOOK_HOST: Optional[str] = None
    WEBHOOK_PATH: str = "/webhook"
    WEBHOOK_PORT: int = 8080

    # Rate limiting
    RATE_LIMIT_MESSAGES: int = 30
    RATE_LIMIT_WINDOW: int = 60
    TRIAL_DAYS: int = 3

    # ──────────────────────────────────────────
    # МОНИТОРИНГ
    # ──────────────────────────────────────────
    SENTRY_DSN: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # игнорировать лишние переменные из .env
    )


settings = Settings()
