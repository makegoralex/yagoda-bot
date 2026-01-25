from __future__ import annotations

import os
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@dataclass
class Session:
    role: str | None = None
    step: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class BotClient:
    def __init__(self, token: str, backend_base_url: str) -> None:
        self.token = token
        self.backend_base_url = backend_base_url.rstrip("/")
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.sessions: dict[int, Session] = {}
        self._ensure_long_polling()
        self._log_startup_diagnostics()

    def _ensure_long_polling(self) -> None:
        try:
            requests.post(
                f"{self.api_url}/deleteWebhook",
                json={"drop_pending_updates": True},
                timeout=10,
            )
        except requests.RequestException:
            logging.exception("Failed to clear webhook for long polling")

    def _log_startup_diagnostics(self) -> None:
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            if response.ok:
                username = response.json().get("result", {}).get("username")
                logging.info("Bot connected as @%s", username)
            else:
                logging.warning("getMe failed: %s", response.text)
        except requests.RequestException:
            logging.exception("getMe request failed")

        try:
            response = requests.get(f"{self.api_url}/getWebhookInfo", timeout=10)
            if response.ok:
                logging.info("Webhook info: %s", response.json())
            else:
                logging.warning("getWebhookInfo failed: %s", response.text)
        except requests.RequestException:
            logging.exception("getWebhookInfo request failed")

    def send_message(self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        requests.post(
            f"{self.api_url}/sendMessage",
            json=payload,
            timeout=10,
        )

    def _get_session(self, user_id: int) -> Session:
        session = self.sessions.get(user_id)
        if not session:
            session = Session()
            self.sessions[user_id] = session
        return session

    def _reset_session(self, user_id: int) -> Session:
        session = Session()
        self.sessions[user_id] = session
        return session

    def _send_role_prompt(self, chat_id: int, user_id: int, reset_session: bool = False) -> None:
        session = self._reset_session(user_id) if reset_session else self._get_session(user_id)
        session.step = "choose_role"
        session.role = None
        keyboard = {
            "keyboard": [
                [{"text": "Владелец"}],
                [{"text": "Сотрудник"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }
        self.send_message(
            chat_id,
            "Автодеплой работает ✅ (обновление 2026-01-23)\n"
            "Привет! Вы владелец/админ или сотрудник?",
            reply_markup=keyboard,
        )

    def handle_start(self, chat_id: int, user_id: int) -> None:
        self._send_role_prompt(chat_id, user_id, reset_session=True)

    def handle_message(self, chat_id: int, user_id: int, text: str) -> None:
        message = text.strip()
        session = self._get_session(user_id)
        if message.lower() == "/start":
            self.handle_start(chat_id, user_id)
            return

        role_choice = self._parse_role_choice(message)
        if session.step == "choose_role" or (not session.role and role_choice):
            if role_choice == "owner":
                session.role = "owner"
                session.step = "owner_company"
                self.send_message(chat_id, "Введите название компании.")
                return
            if role_choice == "staff":
                session.role = "staff"
                session.step = "staff_invite"
                self.send_message(chat_id, "Введите invite-код компании.")
                return
            self.send_message(chat_id, "Пожалуйста, выберите роль кнопкой ниже.")
            self._send_role_prompt(chat_id, user_id)
            return

        if session.step and session.step.startswith("owner_") and not session.role:
            session.role = "owner"
        if session.step and session.step.startswith("staff_") and not session.role:
            session.role = "staff"

        if session.role == "owner":
            self._handle_owner_flow(chat_id, user_id, session, message)
            return

        if session.role == "staff":
            self._handle_staff_flow(chat_id, user_id, session, message)
            return

        self._send_role_prompt(chat_id, user_id)

    def _answer_callback(self, callback_id: str) -> None:
        requests.post(
            f"{self.api_url}/answerCallbackQuery",
            json={"callback_query_id": callback_id},
            timeout=10,
        )

    def handle_callback(self, chat_id: int, user_id: int, data: str, callback_id: str) -> None:
        self._answer_callback(callback_id)
        session = self._get_session(user_id)
        if data == "role_owner":
            session.role = "owner"
            session.step = "owner_company"
            self.send_message(chat_id, "Введите название компании.")
            return
        if data == "role_staff":
            session.role = "staff"
            session.step = "staff_invite"
            self.send_message(chat_id, "Введите invite-код компании.")
            return
        self.send_message(chat_id, "Напишите /start, чтобы начать.")

    def _parse_role_choice(self, message: str) -> str | None:
        lowered = message.lower()
        if lowered in {"владелец", "админ"} or "влад" in lowered:
            return "owner"
        if lowered == "сотрудник" or "сотр" in lowered:
            return "staff"
        return None

    def _handle_owner_flow(
        self,
        chat_id: int,
        user_id: int,
        session: Session,
        message: str,
    ) -> None:
        if session.step == "owner_company":
            session.data["company_name"] = message
            session.step = "owner_name"
            self.send_message(chat_id, "Введите ваше имя.")
            return
        if session.step == "owner_name":
            session.data["owner_name"] = message
            session.step = "owner_username"
            self.send_message(chat_id, "Придумайте логин для веб-кабинета.")
            return
        if session.step == "owner_username":
            session.data["username"] = message
            session.step = "owner_password"
            self.send_message(chat_id, "Придумайте пароль для веб-кабинета.")
            return
        if session.step == "owner_password":
            session.data["password"] = message
            session.step = "owner_timezone"
            self.send_message(
                chat_id,
                "Введите таймзону (например, Europe/Moscow) или отправьте '-' чтобы оставить по умолчанию.",
            )
            return
        if session.step == "owner_timezone":
            timezone = None if message.strip() == "-" else message
            session.data["timezone"] = timezone
            session.step = "owner_location"
            self.send_message(
                chat_id,
                "Введите название точки (или отправьте '-' чтобы пропустить).",
            )
            return
        if session.step == "owner_location":
            location_name = None if message.strip() == "-" else message
            payload = {
                "company_name": session.data["company_name"],
                "owner_name": session.data["owner_name"],
                "username": session.data["username"],
                "password": session.data["password"],
                "telegram_id": str(user_id),
            }
            if session.data.get("timezone"):
                payload["timezone"] = session.data["timezone"]
            if location_name:
                payload["location_name"] = location_name
            response = requests.post(
                f"{self.backend_base_url}/api/onboarding/owner",
                json=payload,
                timeout=10,
            )
            if response.ok:
                data = response.json()
                invite_code = data["invite_code"]
                self.send_message(
                    chat_id,
                    "Компания создана ✅\n"
                    f"Invite-код для сотрудников: {invite_code}\n"
                    "Логин/пароль для веб-кабинета сохранены.",
                )
                self._reset_session(user_id)
                return
            self.send_message(chat_id, f"Ошибка онбординга: {response.text}")
            self._reset_session(user_id)
            return

        self.send_message(chat_id, "Напишите /start, чтобы начать сначала.")

    def _handle_staff_flow(
        self,
        chat_id: int,
        user_id: int,
        session: Session,
        message: str,
    ) -> None:
        if session.step == "staff_invite":
            session.data["invite_code"] = message
            session.step = "staff_name"
            self.send_message(chat_id, "Введите ваше имя.")
            return
        if session.step == "staff_name":
            payload = {
                "code": session.data["invite_code"],
                "telegram_id": str(user_id),
                "name": message,
            }
            response = requests.post(
                f"{self.backend_base_url}/api/onboarding/invite",
                json=payload,
                timeout=10,
            )
            if response.ok:
                role = response.json().get("role", "staff")
                self.send_message(
                    chat_id,
                    f"Готово ✅ Вы добавлены как {role}.",
                )
                self._reset_session(user_id)
                return
            self.send_message(chat_id, f"Ошибка invite-кода: {response.text}")
            self._reset_session(user_id)
            return

        self.send_message(chat_id, "Напишите /start, чтобы начать сначала.")

    def run(self) -> None:
        offset: int | None = None
        while True:
            response = requests.get(
                f"{self.api_url}/getUpdates",
                params={"timeout": 30, "offset": offset},
                timeout=40,
            )
            if not response.ok:
                logging.warning("getUpdates failed: %s", response.text)
                time.sleep(2)
                continue
            payload = response.json()
            for update in payload.get("result", []):
                offset = update["update_id"] + 1
                callback = update.get("callback_query")
                if callback:
                    message = callback.get("message") or {}
                    chat_id = message.get("chat", {}).get("id")
                    user_id = callback.get("from", {}).get("id")
                    data = callback.get("data")
                    callback_id = callback.get("id")
                    if chat_id and user_id and data and callback_id:
                        self.handle_callback(chat_id, user_id, data, callback_id)
                    continue
                message = update.get("message")
                if not message or "text" not in message:
                    continue
                chat_id = message["chat"]["id"]
                user_id = message["from"]["id"]
                self.handle_message(chat_id, user_id, message["text"])


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    backend_base_url = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    client = BotClient(token=token, backend_base_url=backend_base_url)
    client.run()


if __name__ == "__main__":
    main()
