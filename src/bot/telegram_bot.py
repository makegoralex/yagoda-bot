from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests


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

    def send_message(self, chat_id: int, text: str) -> None:
        requests.post(
            f"{self.api_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
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

    def handle_start(self, chat_id: int, user_id: int) -> None:
        session = self._reset_session(user_id)
        session.step = "choose_role"
        self.send_message(
            chat_id,
            "Привет! Вы владелец/админ или сотрудник? Напишите: владелец или сотрудник.",
        )

    def handle_message(self, chat_id: int, user_id: int, text: str) -> None:
        message = text.strip()
        session = self._get_session(user_id)
        if message.lower() == "/start":
            self.handle_start(chat_id, user_id)
            return

        if session.step == "choose_role":
            if message.lower() in {"владелец", "админ"}:
                session.role = "owner"
                session.step = "owner_company"
                self.send_message(chat_id, "Введите название компании.")
                return
            if message.lower() == "сотрудник":
                session.role = "staff"
                session.step = "staff_invite"
                self.send_message(chat_id, "Введите invite-код компании.")
                return
            self.send_message(chat_id, "Пожалуйста, напишите: владелец или сотрудник.")
            return

        if session.role == "owner":
            self._handle_owner_flow(chat_id, user_id, session, message)
            return

        if session.role == "staff":
            self._handle_staff_flow(chat_id, user_id, session, message)
            return

        self.send_message(chat_id, "Напишите /start, чтобы начать.")

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
                "location_name": location_name,
            }
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
                time.sleep(2)
                continue
            payload = response.json()
            for update in payload.get("result", []):
                offset = update["update_id"] + 1
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
