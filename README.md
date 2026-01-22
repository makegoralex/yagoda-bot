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

## Переменные окружения
- `TELEGRAM_BOT_TOKEN` — токен бота от BotFather.
