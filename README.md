# yagoda-bot
Бот управления кофейней.

## Быстрая проверка связки сайт → бот
Ниже минимальный веб-сервер с кнопкой, которая отправляет тестовое сообщение в Telegram-бот.

### 1) Установите зависимости
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Получите Bot Token и Chat ID
1. Создайте бота через [BotFather](https://t.me/BotFather) и получите **TELEGRAM_BOT_TOKEN**.
2. Напишите боту любое сообщение (например, `/start`).
3. Откройте в браузере:
   ```
   https://api.telegram.org/bot<ВАШ_ТОКЕН>/getUpdates
   ```
4. Найдите в ответе блок с `"chat": {"id": ... }` — это ваш **TELEGRAM_CHAT_ID**.

Если `result` пустой, значит бот ещё не получил сообщений. Отправьте ему `/start` и обновите страницу.

### Частая ошибка
`Forbidden: bots can't send messages to bots` означает, что в `TELEGRAM_CHAT_ID` указан **chat_id другого бота**. Нужен ID пользователя или группы:
1. Напишите боту сообщение (в личном чате или в группе).
2. Откройте `https://api.telegram.org/bot<ВАШ_ТОКЕН>/getUpdates`.
3. Возьмите `chat.id` из сообщения пользователя или группы.

### 3) Проверка токена (без chat_id)
Если вы хотите проверить, что токен валиден, без `chat_id`, нажмите кнопку **«Проверить токен бота»** на странице. Это вызывает `getMe` в Telegram API и работает только с `TELEGRAM_BOT_TOKEN`.

### 4) Запустите сервер
```bash
export TELEGRAM_BOT_TOKEN="ваш_токен"
export TELEGRAM_CHAT_ID="ваш_chat_id"
uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

Откройте в браузере:
```
http://localhost:8000/demo
```

Нажмите кнопку — сообщение появится в Telegram.

## Переменные окружения
- `TELEGRAM_BOT_TOKEN` — токен бота от BotFather.
- `TELEGRAM_CHAT_ID` — чат, куда бот отправляет сообщение.
