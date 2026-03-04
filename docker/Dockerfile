FROM python:3.12-slim

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Зависимости (сначала requirements для кэширования слоёв)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY . .

# Непривилегированный пользователь
RUN adduser --disabled-password --gecos "" botuser
USER botuser

CMD ["python", "-m", "bot.main"]
