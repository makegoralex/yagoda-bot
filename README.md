# yagoda-bot
Бот управления кофейней.

## Быстрая проверка связки сайт → бот
Ниже минимальный веб-сервер с кнопкой, которая проверяет токен бота через Telegram API.

### 1) Установите зависимости
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Получите Bot Token
Создайте бота через [BotFather](https://t.me/BotFather) и получите **TELEGRAM_BOT_TOKEN**.

### 3) Запустите сервер
```bash
export TELEGRAM_BOT_TOKEN="ваш_токен"
uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

Откройте в браузере:
```
http://localhost:8000/demo
```

Нажмите кнопку — появится статус проверки токена.

## Быстрый запуск Telegram-бота (онбординг владельца)
Бот поддерживает /start диалог: владелец создаёт компанию и задаёт логин/пароль, сотрудник вводит invite-код.

### 1) Запустите backend
```bash
uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

### 2) Запустите бота
```bash
export TELEGRAM_BOT_TOKEN="ваш_токен"
export BACKEND_BASE_URL="http://localhost:8000"
python -m src.bot.telegram_bot
```

## Переменные окружения
- `TELEGRAM_BOT_TOKEN` — токен бота от BotFather.
- `BACKEND_BASE_URL` — адрес backend API (по умолчанию `http://localhost:8000`).
