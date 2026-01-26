from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex


class Company(BaseModel):
    id: str
    name: str
    timezone: str
    created_at: datetime


class User(BaseModel):
    id: str
    company_id: str
    telegram_id: str
    name: str
    role: Literal["owner", "manager", "staff"]
    status: Literal["active", "inactive"]


class Invite(BaseModel):
    code: str
    company_id: str
    role_default: Literal["owner", "manager", "staff"]
    expires_at: datetime | None


class WebCredential(BaseModel):
    id: str
    company_id: str
    user_id: str
    username: str
    password_hash: str
    password_salt: str
    created_at: datetime


class OwnerOnboardingRequest(BaseModel):
    company_name: str
    timezone: str = "Europe/Moscow"
    location_name: str | None = "Основная точка"
    owner_name: str
    telegram_id: str
    username: str
    password: str


class OwnerOnboardingResponse(BaseModel):
    company: Company
    owner: User
    credential_id: str
    invite_code: str
    bot_invite_hint: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user_id: str
    company_id: str
    authenticated: bool


class InviteRedeemRequest(BaseModel):
    code: str
    telegram_id: str
    name: str


class InviteRedeemResponse(BaseModel):
    user: User
    company_id: str
    company_name: str
    role: str


@dataclass
class Store:
    companies: dict[str, Company] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)
    invites: dict[str, Invite] = field(default_factory=dict)
    credentials: dict[str, WebCredential] = field(default_factory=dict)


def _model_to_dict(model: BaseModel) -> dict[str, object]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class StoreStorage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _table_exists(self, connection: sqlite3.Connection, table_name: str) -> bool:
        cursor = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def _table_columns(self, connection: sqlite3.Connection, table_name: str) -> set[str]:
        cursor = connection.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}

    def _load_companies_fallback(self, connection: sqlite3.Connection) -> dict[str, Company]:
        if not self._table_exists(connection, "companies"):
            return {}
        columns = self._table_columns(connection, "companies")
        if not {"id", "name"} <= columns:
            return {}
        timezone_column = "timezone" if "timezone" in columns else None
        created_at_column = "created_at" if "created_at" in columns else None
        select_columns = ["id", "name"]
        if timezone_column:
            select_columns.append(timezone_column)
        if created_at_column:
            select_columns.append(created_at_column)
        cursor = connection.execute(
            f"SELECT {', '.join(select_columns)} FROM companies",
        )
        companies: dict[str, Company] = {}
        for row in cursor.fetchall():
            row_data = dict(zip(select_columns, row))
            company = Company(
                id=row_data["id"],
                name=row_data["name"],
                timezone=row_data.get("timezone") or "Europe/Moscow",
                created_at=row_data.get("created_at") or _utc_now(),
            )
            companies[company.id] = company
        return companies

    def _load_users_fallback(self, connection: sqlite3.Connection) -> dict[str, User]:
        if not self._table_exists(connection, "users"):
            return {}
        columns = self._table_columns(connection, "users")
        if not {"id", "company_id", "name"} <= columns:
            return {}
        telegram_column = "telegram_id" if "telegram_id" in columns else None
        role_column = "role" if "role" in columns else None
        status_column = "status" if "status" in columns else None
        select_columns = ["id", "company_id", "name"]
        if telegram_column:
            select_columns.append(telegram_column)
        if role_column:
            select_columns.append(role_column)
        if status_column:
            select_columns.append(status_column)
        cursor = connection.execute(
            f"SELECT {', '.join(select_columns)} FROM users",
        )
        users: dict[str, User] = {}
        for row in cursor.fetchall():
            row_data = dict(zip(select_columns, row))
            user = User(
                id=row_data["id"],
                company_id=row_data["company_id"],
                telegram_id=row_data.get("telegram_id") or "",
                name=row_data["name"],
                role=row_data.get("role") or "staff",
                status=row_data.get("status") or "active",
            )
            users[user.id] = user
        return users

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mvp_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """,
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    timezone TEXT,
                    created_at TEXT
                )
                """,
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    telegram_id TEXT,
                    name TEXT NOT NULL,
                    role TEXT,
                    status TEXT
                )
                """,
            )

    def load_store(self) -> Store:
        with self._connect() as connection:
            cursor = connection.execute("SELECT key, value FROM mvp_state")
            rows = cursor.fetchall()
        data = {key: json.loads(value) for key, value in rows}
        companies = {
            item["id"]: Company(**item)
            for item in data.get("companies", [])
        }
        users = {
            item["id"]: User(**item)
            for item in data.get("users", [])
        }
        if not companies or not users:
            with self._connect() as connection:
                if not companies:
                    companies = self._load_companies_fallback(connection)
                if not users:
                    users = self._load_users_fallback(connection)
        invites = {
            item["code"]: Invite(**item)
            for item in data.get("invites", [])
        }
        credentials = {
            item["id"]: WebCredential(**item)
            for item in data.get("credentials", [])
        }
        return Store(
            companies=companies,
            users=users,
            invites=invites,
            credentials=credentials,
        )

    def save_store(self, store: Store) -> None:
        payloads = {
            "companies": [_model_to_dict(item) for item in store.companies.values()],
            "users": [_model_to_dict(item) for item in store.users.values()],
            "invites": [_model_to_dict(item) for item in store.invites.values()],
            "credentials": [_model_to_dict(item) for item in store.credentials.values()],
        }
        with self._connect() as connection:
            for key, value in payloads.items():
                connection.execute(
                    """
                    INSERT INTO mvp_state (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, json.dumps(value, ensure_ascii=False, default=str)),
                )
            for company in store.companies.values():
                connection.execute(
                    """
                    INSERT INTO companies (id, name, timezone, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        timezone = excluded.timezone,
                        created_at = excluded.created_at
                    """,
                    (
                        company.id,
                        company.name,
                        company.timezone,
                        str(company.created_at),
                    ),
                )
            for user in store.users.values():
                connection.execute(
                    """
                    INSERT INTO users (id, company_id, telegram_id, name, role, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        company_id = excluded.company_id,
                        telegram_id = excluded.telegram_id,
                        name = excluded.name,
                        role = excluded.role,
                        status = excluded.status
                    """,
                    (
                        user.id,
                        user.company_id,
                        user.telegram_id,
                        user.name,
                        user.role,
                        user.status,
                    ),
                )


default_db_path = Path(__file__).resolve().parents[2] / "data" / "mvp.db"
storage = StoreStorage(os.getenv("MVP_DB_PATH", str(default_db_path)))


def load_store() -> Store:
    return storage.load_store()


def save_store(store: Store) -> None:
    storage.save_store(store)
router = APIRouter(prefix="/api")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def _find_credential(store: Store, username: str) -> WebCredential | None:
    return next((cred for cred in store.credentials.values() if cred.username == username), None)


def _ensure_invite(store: Store, code: str) -> Invite:
    invite = store.invites.get(code)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.expires_at and invite.expires_at <= _utc_now():
        raise HTTPException(status_code=400, detail="Invite expired")
    return invite


def _find_user_by_telegram(store: Store, company_id: str, telegram_id: str) -> User | None:
    return next(
        (
            user
            for user in store.users.values()
            if user.company_id == company_id and user.telegram_id == telegram_id
        ),
        None,
    )


@router.post("/onboarding/owner", response_model=OwnerOnboardingResponse)
def onboard_owner(payload: OwnerOnboardingRequest) -> OwnerOnboardingResponse:
    store = load_store()
    if _find_credential(store, payload.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    company = Company(
        id=_new_id(),
        name=payload.company_name,
        timezone=payload.timezone,
        created_at=_utc_now(),
    )
    store.companies[company.id] = company
    owner = User(
        id=_new_id(),
        company_id=company.id,
        telegram_id=payload.telegram_id,
        name=payload.owner_name,
        role="owner",
        status="active",
    )
    store.users[owner.id] = owner
    salt = secrets.token_hex(16)
    credential = WebCredential(
        id=_new_id(),
        company_id=company.id,
        user_id=owner.id,
        username=payload.username,
        password_hash=_hash_password(payload.password, salt),
        password_salt=salt,
        created_at=_utc_now(),
    )
    store.credentials[credential.id] = credential
    invite = Invite(
        code=_new_id()[:8],
        company_id=company.id,
        role_default="staff",
        expires_at=None,
    )
    store.invites[invite.code] = invite
    save_store(store)
    return OwnerOnboardingResponse(
        company=company,
        owner=owner,
        credential_id=credential.id,
        invite_code=invite.code,
        bot_invite_hint="Отправьте invite-код сотрудникам для входа в Telegram-бот.",
    )


@router.post("/onboarding/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    store = load_store()
    credential = _find_credential(store, payload.username)
    if not credential:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    hashed = _hash_password(payload.password, credential.password_salt)
    if hashed != credential.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = store.users.get(credential.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner accounts can login")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="User is inactive")
    return LoginResponse(
        user_id=credential.user_id,
        company_id=credential.company_id,
        authenticated=True,
    )


@router.post("/onboarding/invite", response_model=InviteRedeemResponse)
def redeem_invite(payload: InviteRedeemRequest) -> InviteRedeemResponse:
    store = load_store()
    invite = _ensure_invite(store, payload.code)
    company = store.companies.get(invite.company_id)
    company_name = company.name if company else ""
    existing = _find_user_by_telegram(store, invite.company_id, payload.telegram_id)
    if existing:
        updated = existing.model_copy(
            update={"role": invite.role_default, "name": payload.name},
        )
        store.users[updated.id] = updated
        save_store(store)
        return InviteRedeemResponse(
            user=updated,
            company_id=invite.company_id,
            company_name=company_name,
            role=updated.role,
        )
    user = User(
        id=_new_id(),
        company_id=invite.company_id,
        telegram_id=payload.telegram_id,
        name=payload.name,
        role=invite.role_default,
        status="active",
    )
    store.users[user.id] = user
    save_store(store)
    return InviteRedeemResponse(
        user=user,
        company_id=invite.company_id,
        company_name=company_name,
        role=user.role,
    )
