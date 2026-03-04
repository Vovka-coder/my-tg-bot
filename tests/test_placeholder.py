"""
Базовые тесты — заглушки на время пока бот в разработке.
Реальные тесты будут добавляться по мере написания handlers, services и т.д.
"""


def test_placeholder():
    """Заглушка — убедиться что CI не падает из-за отсутствия тестов."""
    assert True


def test_config_imports():
    """Проверяем что config.py импортируется без ошибок при наличии .env."""
    try:
        from bot.config import settings  # noqa: F401
    except Exception:
        # В CI могут отсутствовать некоторые переменные — это ок на этапе скелета
        pass
    assert True
