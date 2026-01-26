from __future__ import annotations

import os
from pathlib import Path
import json
import logging
import time
import sqlite3
from dataclasses import dataclass, field
from typing import Any

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@dataclass
class Session:
    role: str | None = None
    step: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    last_update_id: int | None = None


class SessionStorage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id INTEGER PRIMARY KEY,
                    role TEXT,
                    step TEXT,
                    data TEXT,
                    last_update_id INTEGER
                )
                """,
            )

    def load_session(self, user_id: int) -> Session:
        cursor = self.connection.execute(
            "SELECT role, step, data, last_update_id FROM sessions WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return Session()
        role, step, data_raw, last_update_id = row
        data = json.loads(data_raw) if data_raw else {}
        return Session(
            role=role,
            step=step,
            data=data,
            last_update_id=last_update_id,
        )

    def save_session(self, user_id: int, session: Session) -> None:
        data_raw = json.dumps(session.data, ensure_ascii=False)
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO sessions (user_id, role, step, data, last_update_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    role = excluded.role,
                    step = excluded.step,
                    data = excluded.data,
                    last_update_id = excluded.last_update_id
                """,
                (
                    user_id,
                    session.role,
                    session.step,
                    data_raw,
                    session.last_update_id,
                ),
            )


class BotClient:
    def __init__(self, token: str, backend_base_url: str) -> None:
        self.token = token
        self.backend_base_url = backend_base_url.rstrip("/")
        self.api_url = f"https://api.telegram.org/bot{token}"
        default_db_path = Path(__file__).resolve().parents[2] / "data" / "telegram_sessions.db"
        session_db_path = os.getenv("SESSION_DB_PATH", str(default_db_path))
        self.session_storage = SessionStorage(session_db_path)
        self._ensure_long_polling()
        self._log_startup_diagnostics()
        self._staff_menu_label = "Профиль"
        self._staff_recipes_label = "Рецепты"
        self._staff_menu_back_label = "В меню"
        self._staff_recipes_back_label = "Назад"

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

    def _load_session(self, user_id: int) -> Session:
        return self.session_storage.load_session(user_id)

    def _save_session(self, user_id: int, session: Session) -> None:
        self.session_storage.save_session(user_id, session)

    def _reset_session(self) -> Session:
        return Session()

    def _send_role_prompt(self, chat_id: int, session: Session) -> Session:
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
        return session

    def _staff_menu_keyboard(self) -> dict[str, Any]:
        return {
            "keyboard": [
                [{"text": self._staff_menu_label}],
                [{"text": self._staff_recipes_label}],
            ],
            "resize_keyboard": True,
        }

    def _staff_back_keyboard(self, label: str) -> dict[str, Any]:
        return {
            "keyboard": [[{"text": label}]],
            "resize_keyboard": True,
        }

    def _send_staff_menu(self, chat_id: int, session: Session) -> Session:
        session.step = "staff_menu"
        self.send_message(
            chat_id,
            "Вы в меню сотрудника. Выберите раздел.",
            reply_markup=self._staff_menu_keyboard(),
        )
        return session

    def _repeat_current_question(self, chat_id: int, session: Session) -> Session:
        if session.step in (None, "choose_role"):
            return self._send_role_prompt(chat_id, session)
        if session.step == "owner_company":
            self.send_message(chat_id, "Введите название компании.")
            return session
        if session.step == "owner_name":
            self.send_message(chat_id, "Введите ваше имя.")
            return session
        if session.step == "owner_username":
            self.send_message(chat_id, "Придумайте логин для веб-кабинета.")
            return session
        if session.step == "owner_password":
            self.send_message(chat_id, "Придумайте пароль для веб-кабинета.")
            return session
        if session.step == "owner_timezone":
            self.send_message(
                chat_id,
                "Введите таймзону (например, Europe/Moscow) или отправьте '-' чтобы оставить по умолчанию.",
            )
            return session
        if session.step == "owner_location":
            self.send_message(
                chat_id,
                "Введите название точки (или отправьте '-' чтобы пропустить).",
            )
            return session
        if session.step == "staff_invite":
            self.send_message(chat_id, "Введите invite-код компании.")
            return session
        if session.step == "staff_name":
            self.send_message(chat_id, "Введите ваше имя.")
            return session
        if session.step == "staff_menu":
            return self._send_staff_menu(chat_id, session)
        if session.step == "staff_profile":
            return self._send_staff_profile(chat_id, session)
        if session.step == "staff_recipes":
            return self._send_staff_recipes(chat_id, session)
        self.send_message(chat_id, "Напишите /start, чтобы начать.")
        return session

    def _role_label(self, role: str | None) -> str:
        mapping = {
            "owner": "владелец",
            "manager": "менеджер",
            "staff": "сотрудник",
        }
        if not role:
            return "сотрудник"
        return mapping.get(role, role)

    def _send_staff_profile(self, chat_id: int, session: Session) -> Session:
        session.step = "staff_profile"
        name = session.data.get("staff_name") or "—"
        company = session.data.get("company_name") or "—"
        self.send_message(
            chat_id,
            f"Профиль сотрудника\nИмя: {name}\nОрганизация: {company}",
            reply_markup=self._staff_back_keyboard(self._staff_menu_back_label),
        )
        return session

    def _send_staff_recipes(self, chat_id: int, session: Session) -> Session:
        session.step = "staff_recipes"
        self.send_message(
            chat_id,
            "Рецепты пока пустые.",
            reply_markup=self._staff_back_keyboard(self._staff_recipes_back_label),
        )
        return session

    def _log_update_state(
        self,
        stage: str,
        update_id: int,
        update_type: str,
        chat_id: int | None,
        user_id: int | None,
        session: Session | None,
    ) -> None:
        logging.info(
            "Update %s: update_id=%s type=%s chat_id=%s user_id=%s session_role=%s session_step=%s last_update_id=%s",
            stage,
            update_id,
            update_type,
            chat_id,
            user_id,
            session.role if session else None,
            session.step if session else None,
            session.last_update_id if session else None,
        )

    def handle_start(self, chat_id: int, session: Session) -> Session:
        session = self._reset_session()
        return self._send_role_prompt(chat_id, session)

    def handle_message(self, chat_id: int, user_id: int, text: str, session: Session) -> Session:
        message = text.strip()
        if message.lower() == "/start":
            return self.handle_start(chat_id, session)

        role_choice = self._parse_role_choice(message)
        if session.step == "choose_role" or (not session.role and role_choice):
            if role_choice == "owner":
                session.role = "owner"
                session.step = "owner_company"
                self.send_message(chat_id, "Введите название компании.")
                return session
            if role_choice == "staff":
                session.role = "staff"
                session.step = "staff_invite"
                self.send_message(chat_id, "Введите invite-код компании.")
                return session
            self.send_message(chat_id, "Пожалуйста, выберите роль кнопкой ниже.")
            return self._send_role_prompt(chat_id, session)

        if session.step and session.step.startswith("owner_") and not session.role:
            session.role = "owner"
        if session.step and session.step.startswith("staff_") and not session.role:
            session.role = "staff"

        if session.role == "owner":
            return self._handle_owner_flow(chat_id, user_id, session, message)

        if session.role == "staff":
            return self._handle_staff_flow(chat_id, user_id, session, message)

        return self._repeat_current_question(chat_id, session)

    def _answer_callback(self, callback_id: str) -> None:
        requests.post(
            f"{self.api_url}/answerCallbackQuery",
            json={"callback_query_id": callback_id},
            timeout=10,
        )

    def handle_callback(self, chat_id: int, user_id: int, data: str, callback_id: str, session: Session) -> Session:
        self._answer_callback(callback_id)
        if data == "role_owner":
            session.role = "owner"
            session.step = "owner_company"
            self.send_message(chat_id, "Введите название компании.")
            return session
        if data == "role_staff":
            session.role = "staff"
            session.step = "staff_invite"
            self.send_message(chat_id, "Введите invite-код компании.")
            return session
        return self._repeat_current_question(chat_id, session)

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
    ) -> Session:
        if session.step == "owner_company":
            session.data["company_name"] = message
            session.step = "owner_name"
            self.send_message(chat_id, "Введите ваше имя.")
            return session
        if session.step == "owner_name":
            session.data["owner_name"] = message
            session.step = "owner_username"
            self.send_message(chat_id, "Придумайте логин для веб-кабинета.")
            return session
        if session.step == "owner_username":
            session.data["username"] = message
            session.step = "owner_password"
            self.send_message(chat_id, "Придумайте пароль для веб-кабинета.")
            return session
        if session.step == "owner_password":
            session.data["password"] = message
            session.step = "owner_timezone"
            self.send_message(
                chat_id,
                "Введите таймзону (например, Europe/Moscow) или отправьте '-' чтобы оставить по умолчанию.",
            )
            return session
        if session.step == "owner_timezone":
            timezone = None if message.strip() == "-" else message
            session.data["timezone"] = timezone
            session.step = "owner_location"
            self.send_message(
                chat_id,
                "Введите название точки (или отправьте '-' чтобы пропустить).",
            )
            return session
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
                return self._reset_session()
            self.send_message(chat_id, f"Ошибка онбординга: {response.text}")
            return self._reset_session()

        return self._repeat_current_question(chat_id, session)

    def _handle_staff_flow(
        self,
        chat_id: int,
        user_id: int,
        session: Session,
        message: str,
    ) -> Session:
        if session.step == "staff_menu":
            if message == self._staff_menu_label:
                return self._send_staff_profile(chat_id, session)
            if message == self._staff_recipes_label:
                return self._send_staff_recipes(chat_id, session)
            return self._send_staff_menu(chat_id, session)
        if session.step == "staff_profile":
            if message == self._staff_menu_back_label:
                return self._send_staff_menu(chat_id, session)
            return self._send_staff_profile(chat_id, session)
        if session.step == "staff_recipes":
            if message == self._staff_recipes_back_label:
                return self._send_staff_menu(chat_id, session)
            return self._send_staff_recipes(chat_id, session)
        if session.step == "staff_invite":
            session.data["invite_code"] = message
            session.step = "staff_name"
            self.send_message(chat_id, "Введите ваше имя.")
            return session
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
                data = response.json()
                role = data.get("role", "staff")
                company_name = data.get("company_name")
                session.data["staff_name"] = message
                if company_name:
                    session.data["company_name"] = company_name
                self.send_message(
                    chat_id,
                    f"Готово ✅ Вы добавлены как {self._role_label(role)}.",
                )
                return self._send_staff_menu(chat_id, session)
            self.send_message(chat_id, f"Ошибка invite-кода: {response.text}")
            return self._reset_session()

        return self._repeat_current_question(chat_id, session)

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
                        session = self._load_session(user_id)
                        if session.last_update_id is not None and update["update_id"] <= session.last_update_id:
                            self._log_update_state(
                                "ignored",
                                update["update_id"],
                                "callback",
                                chat_id,
                                user_id,
                                session,
                            )
                            continue
                        self._log_update_state(
                            "before",
                            update["update_id"],
                            "callback",
                            chat_id,
                            user_id,
                            session,
                        )
                        session = self.handle_callback(chat_id, user_id, data, callback_id, session)
                        session.last_update_id = update["update_id"]
                        self._save_session(user_id, session)
                        self._log_update_state(
                            "after",
                            update["update_id"],
                            "callback",
                            chat_id,
                            user_id,
                            session,
                        )
                    continue
                message = update.get("message")
                if not message or "text" not in message:
                    continue
                chat_id = message["chat"]["id"]
                user_id = message["from"]["id"]
                session = self._load_session(user_id)
                if session.last_update_id is not None and update["update_id"] <= session.last_update_id:
                    self._log_update_state(
                        "ignored",
                        update["update_id"],
                        "message",
                        chat_id,
                        user_id,
                        session,
                    )
                    continue
                self._log_update_state(
                    "before",
                    update["update_id"],
                    "message",
                    chat_id,
                    user_id,
                    session,
                )
                session = self.handle_message(chat_id, user_id, message["text"], session)
                session.last_update_id = update["update_id"]
                self._save_session(user_id, session)
                self._log_update_state(
                    "after",
                    update["update_id"],
                    "message",
                    chat_id,
                    user_id,
                    session,
                )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    backend_base_url = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    client = BotClient(token=token, backend_base_url=backend_base_url)
    client.run()


if __name__ == "__main__":
    main()
