FROM python:3.13-slim

# Метаданные
LABEL maintainer="ScheduleGenerator"
LABEL description="Web Schedule Generator — FastAPI + SQLite"

# Рабочая директория
WORKDIR /app

# Системные зависимости (нужны для bcrypt и компиляции)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости отдельным слоем (кэш Docker не сбрасывается при смене кода)
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаём директорию для БД (если её нет)
RUN mkdir -p /app/data

# Переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV SECRET_KEY="change-this-in-production-use-env-file"

# Открываем порт
EXPOSE 8000

# Запуск приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]