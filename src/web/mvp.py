from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import secrets
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
    role: str


@dataclass
class Store:
    companies: dict[str, Company] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)
    invites: dict[str, Invite] = field(default_factory=dict)
    credentials: dict[str, WebCredential] = field(default_factory=dict)


store = Store()
router = APIRouter(prefix="/api")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def _find_credential(username: str) -> WebCredential | None:
    return next((cred for cred in store.credentials.values() if cred.username == username), None)


def _ensure_invite(code: str) -> Invite:
    invite = store.invites.get(code)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.expires_at and invite.expires_at <= _utc_now():
        raise HTTPException(status_code=400, detail="Invite expired")
    return invite


def _find_user_by_telegram(company_id: str, telegram_id: str) -> User | None:
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
    if _find_credential(payload.username):
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
    return OwnerOnboardingResponse(
        company=company,
        owner=owner,
        credential_id=credential.id,
        invite_code=invite.code,
        bot_invite_hint="Отправьте invite-код сотрудникам для входа в Telegram-бот.",
    )


@router.post("/onboarding/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    credential = _find_credential(payload.username)
    if not credential:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    hashed = _hash_password(payload.password, credential.password_salt)
    if hashed != credential.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return LoginResponse(
        user_id=credential.user_id,
        company_id=credential.company_id,
        authenticated=True,
    )


@router.post("/onboarding/invite", response_model=InviteRedeemResponse)
def redeem_invite(payload: InviteRedeemRequest) -> InviteRedeemResponse:
    invite = _ensure_invite(payload.code)
    existing = _find_user_by_telegram(invite.company_id, payload.telegram_id)
    if existing:
        return InviteRedeemResponse(
            user=existing,
            company_id=invite.company_id,
            role=existing.role,
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
    return InviteRedeemResponse(
        user=user,
        company_id=invite.company_id,
        role=user.role,
    )
