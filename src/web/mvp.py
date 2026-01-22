from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex


class PolicySettings(BaseModel):
    shift_close_deadline_minutes: int = 90
    reminders_enabled: bool = True
    reminder_schedule_minutes: list[int] = Field(default_factory=lambda: [30, 60])
    require_opening_checklist: bool = True
    require_closing_checklist: bool = True
    require_open_photo: bool = False
    require_close_photo: bool = False
    require_cash_open: bool = False
    require_cash_close: bool = False
    tests_block_shift_closure: bool = True
    monthly_test_required: bool = True
    random_test_probability: float = 0.0
    high_incident_notify_owner: bool = True


class CompanyCreate(BaseModel):
    name: str
    timezone: str = "Europe/Moscow"


class Company(BaseModel):
    id: str
    name: str
    timezone: str
    created_at: datetime


class LocationCreate(BaseModel):
    name: str


class Location(BaseModel):
    id: str
    company_id: str
    name: str


class UserCreate(BaseModel):
    telegram_id: str
    name: str
    role: Literal["owner", "manager", "staff"] = "staff"
    status: Literal["active", "inactive"] = "active"


class User(BaseModel):
    id: str
    company_id: str
    telegram_id: str
    name: str
    role: str
    status: str


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
    telegram_id: str = ""
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


class InviteCreate(BaseModel):
    role_default: Literal["owner", "manager", "staff"] = "staff"
    expires_at: datetime | None = None


class Invite(BaseModel):
    code: str
    company_id: str
    role_default: str
    expires_at: datetime | None


class ChecklistTemplateCreate(BaseModel):
    type: Literal["open", "close"]
    items: list[str]


class ChecklistTemplate(BaseModel):
    id: str
    company_id: str
    type: str
    items: list[str]


class CashLog(BaseModel):
    type: Literal["open", "close"]
    amount: float
    created_at: datetime


class ShiftOpenRequest(BaseModel):
    location_id: str
    user_id: str
    open_checklist: list[str] = Field(default_factory=list)
    open_photo_url: str | None = None
    cash_open_amount: float | None = None


class ShiftCloseRequest(BaseModel):
    close_checklist: list[str] = Field(default_factory=list)
    close_photo_url: str | None = None
    cash_close_amount: float | None = None
    write_off_reason: str | None = None
    notes: str | None = None


class Shift(BaseModel):
    id: str
    company_id: str
    location_id: str
    user_id: str
    start_at: datetime
    end_at: datetime | None
    status: Literal["OPEN", "CLOSED", "EXPIRED"]
    close_deadline_at: datetime
    open_data: dict[str, Any]
    close_data: dict[str, Any] | None = None
    cash_logs: list[CashLog] = Field(default_factory=list)


class IncidentCreate(BaseModel):
    shift_id: str | None = None
    level: Literal["LOW", "MED", "HIGH"]
    category: str
    text: str
    media_url: str | None = None


class Incident(BaseModel):
    id: str
    company_id: str
    shift_id: str | None
    level: str
    category: str
    text: str
    media_url: str | None
    status: Literal["open", "resolved"]
    created_at: datetime


class TrainingSectionCreate(BaseModel):
    title: str
    order: int = 0


class TrainingSection(BaseModel):
    id: str
    company_id: str
    title: str
    order: int


class TrainingLessonCreate(BaseModel):
    section_id: str
    title: str
    body: str
    media_links: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class TrainingLesson(BaseModel):
    id: str
    company_id: str
    section_id: str
    title: str
    body: str
    media_links: list[str]
    tags: list[str]
    updated_at: datetime


class QuizCreate(BaseModel):
    title: str
    type: Literal["onboarding", "monthly", "random"]
    passing_score: int = 70


class Quiz(BaseModel):
    id: str
    company_id: str
    title: str
    type: str
    passing_score: int


class QuizQuestionCreate(BaseModel):
    text: str
    answers: list[str]
    correct_answers: list[int]
    explanation: str | None = None


class QuizQuestion(BaseModel):
    id: str
    quiz_id: str
    text: str
    answers: list[str]
    correct_answers: list[int]
    explanation: str | None


class QuizAttemptCreate(BaseModel):
    user_id: str
    answers: dict[str, list[int]]


class QuizAttempt(BaseModel):
    id: str
    quiz_id: str
    user_id: str
    started_at: datetime
    finished_at: datetime
    score: int
    passed: bool


class ScheduleEntryCreate(BaseModel):
    location_id: str
    user_id: str
    start_at: datetime
    end_at: datetime
    status: Literal["planned", "approved"] = "planned"


class ScheduleEntry(BaseModel):
    id: str
    company_id: str
    location_id: str
    user_id: str
    start_at: datetime
    end_at: datetime
    status: str


class MysteryShopperReportCreate(BaseModel):
    location_id: str
    user_id: str | None = None
    shift_id: str | None = None
    score: int
    answers: dict[str, Any]


class MysteryShopperReport(BaseModel):
    id: str
    company_id: str
    location_id: str
    user_id: str | None
    shift_id: str | None
    score: int
    answers: dict[str, Any]
    created_at: datetime


@dataclass
class Store:
    companies: dict[str, Company] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)
    credentials: dict[str, WebCredential] = field(default_factory=dict)
    invites: dict[str, Invite] = field(default_factory=dict)
    policies: dict[str, PolicySettings] = field(default_factory=dict)
    checklists: dict[str, ChecklistTemplate] = field(default_factory=dict)
    shifts: dict[str, Shift] = field(default_factory=dict)
    incidents: dict[str, Incident] = field(default_factory=dict)
    training_sections: dict[str, TrainingSection] = field(default_factory=dict)
    training_lessons: dict[str, TrainingLesson] = field(default_factory=dict)
    quizzes: dict[str, Quiz] = field(default_factory=dict)
    quiz_questions: dict[str, QuizQuestion] = field(default_factory=dict)
    quiz_attempts: dict[str, QuizAttempt] = field(default_factory=dict)
    schedule_entries: dict[str, ScheduleEntry] = field(default_factory=dict)
    mystery_reports: dict[str, MysteryShopperReport] = field(default_factory=dict)

    def _filter_by_company(self, collection: dict[str, BaseModel], company_id: str) -> list[BaseModel]:
        return [item for item in collection.values() if item.company_id == company_id]


store = Store()
router = APIRouter(prefix="/api")


def _get_policy(company_id: str) -> PolicySettings:
    return store.policies.get(company_id, PolicySettings())


def _ensure_company(company_id: str) -> Company:
    company = store.companies.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def _find_credential(username: str) -> WebCredential | None:
    return next((cred for cred in store.credentials.values() if cred.username == username), None)


@router.post("/onboarding/owner", response_model=OwnerOnboardingResponse)
def onboard_owner(payload: OwnerOnboardingRequest) -> OwnerOnboardingResponse:
    if _find_credential(payload.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    company_id = _new_id()
    company = Company(
        id=company_id,
        name=payload.company_name,
        timezone=payload.timezone,
        created_at=_utc_now(),
    )
    store.companies[company_id] = company
    location = None
    if payload.location_name:
        location = Location(
            id=_new_id(),
            company_id=company_id,
            name=payload.location_name,
        )
        store.locations[location.id] = location
    owner = User(
        id=_new_id(),
        company_id=company_id,
        telegram_id=payload.telegram_id,
        name=payload.owner_name,
        role="owner",
        status="active",
    )
    store.users[owner.id] = owner
    salt = secrets.token_hex(16)
    credential = WebCredential(
        id=_new_id(),
        company_id=company_id,
        user_id=owner.id,
        username=payload.username,
        password_hash=_hash_password(payload.password, salt),
        password_salt=salt,
        created_at=_utc_now(),
    )
    store.credentials[credential.id] = credential
    invite = Invite(
        code=_new_id()[:8],
        company_id=company_id,
        role_default="staff",
        expires_at=None,
    )
    store.invites[invite.code] = invite
    return OwnerOnboardingResponse(
        company=company,
        owner=owner,
        credential_id=credential.id,
        invite_code=invite.code,
        bot_invite_hint="Отправьте сотрудникам invite-code в Telegram-боте.",
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


@router.post("/companies", response_model=Company)
def create_company(payload: CompanyCreate) -> Company:
    company_id = _new_id()
    company = Company(
        id=company_id,
        name=payload.name,
        timezone=payload.timezone,
        created_at=_utc_now(),
    )
    store.companies[company_id] = company
    return company


@router.get("/companies/{company_id}", response_model=Company)
def get_company(company_id: str) -> Company:
    return _ensure_company(company_id)


@router.post("/companies/{company_id}/locations", response_model=Location)
def create_location(company_id: str, payload: LocationCreate) -> Location:
    _ensure_company(company_id)
    location = Location(id=_new_id(), company_id=company_id, name=payload.name)
    store.locations[location.id] = location
    return location


@router.post("/companies/{company_id}/users", response_model=User)
def create_user(company_id: str, payload: UserCreate) -> User:
    _ensure_company(company_id)
    user = User(
        id=_new_id(),
        company_id=company_id,
        telegram_id=payload.telegram_id,
        name=payload.name,
        role=payload.role,
        status=payload.status,
    )
    store.users[user.id] = user
    return user


@router.post("/companies/{company_id}/invites", response_model=Invite)
def create_invite(company_id: str, payload: InviteCreate) -> Invite:
    _ensure_company(company_id)
    code = _new_id()[:8]
    invite = Invite(
        code=code,
        company_id=company_id,
        role_default=payload.role_default,
        expires_at=payload.expires_at,
    )
    store.invites[invite.code] = invite
    return invite


@router.post("/companies/{company_id}/policies", response_model=PolicySettings)
def set_policy(company_id: str, payload: PolicySettings) -> PolicySettings:
    _ensure_company(company_id)
    store.policies[company_id] = payload
    return payload


@router.get("/companies/{company_id}/policies", response_model=PolicySettings)
def get_policy(company_id: str) -> PolicySettings:
    _ensure_company(company_id)
    return _get_policy(company_id)


@router.post("/companies/{company_id}/checklists", response_model=ChecklistTemplate)
def create_checklist(company_id: str, payload: ChecklistTemplateCreate) -> ChecklistTemplate:
    _ensure_company(company_id)
    checklist = ChecklistTemplate(
        id=_new_id(),
        company_id=company_id,
        type=payload.type,
        items=payload.items,
    )
    store.checklists[checklist.id] = checklist
    return checklist


def _validate_shift_open(policy: PolicySettings, payload: ShiftOpenRequest) -> None:
    if policy.require_opening_checklist and not payload.open_checklist:
        raise HTTPException(status_code=400, detail="Opening checklist required")
    if policy.require_open_photo and not payload.open_photo_url:
        raise HTTPException(status_code=400, detail="Opening photo required")
    if policy.require_cash_open and payload.cash_open_amount is None:
        raise HTTPException(status_code=400, detail="Opening cash amount required")


def _monthly_test_passed(company_id: str, user_id: str) -> bool:
    policy = _get_policy(company_id)
    if not policy.monthly_test_required:
        return True
    monthly_quiz_ids = {
        quiz.id for quiz in store.quizzes.values() if quiz.company_id == company_id and quiz.type == "monthly"
    }
    if not monthly_quiz_ids:
        return False
    attempts = [
        attempt
        for attempt in store.quiz_attempts.values()
        if attempt.quiz_id in monthly_quiz_ids and attempt.user_id == user_id and attempt.passed
    ]
    if not attempts:
        return False
    latest_attempt = max(attempts, key=lambda attempt: attempt.finished_at)
    return latest_attempt.finished_at >= _utc_now() - timedelta(days=30)


@router.post("/companies/{company_id}/shifts/open", response_model=Shift)
def open_shift(company_id: str, payload: ShiftOpenRequest) -> Shift:
    _ensure_company(company_id)
    policy = _get_policy(company_id)
    _validate_shift_open(policy, payload)
    if payload.user_id not in store.users:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.location_id not in store.locations:
        raise HTTPException(status_code=404, detail="Location not found")
    active_shift = next(
        (
            shift
            for shift in store.shifts.values()
            if shift.company_id == company_id
            and shift.user_id == payload.user_id
            and shift.status == "OPEN"
        ),
        None,
    )
    if active_shift:
        raise HTTPException(status_code=400, detail="User already has an open shift")
    started_at = _utc_now()
    deadline = started_at + timedelta(minutes=policy.shift_close_deadline_minutes)
    shift = Shift(
        id=_new_id(),
        company_id=company_id,
        location_id=payload.location_id,
        user_id=payload.user_id,
        start_at=started_at,
        end_at=None,
        status="OPEN",
        close_deadline_at=deadline,
        open_data={
            "checklist": payload.open_checklist,
            "photo_url": payload.open_photo_url,
        },
        close_data=None,
        cash_logs=[
            CashLog(type="open", amount=payload.cash_open_amount or 0.0, created_at=started_at)
        ]
        if payload.cash_open_amount is not None
        else [],
    )
    store.shifts[shift.id] = shift
    return shift


def _validate_shift_close(policy: PolicySettings, payload: ShiftCloseRequest) -> None:
    if policy.require_closing_checklist and not payload.close_checklist:
        raise HTTPException(status_code=400, detail="Closing checklist required")
    if policy.require_close_photo and not payload.close_photo_url:
        raise HTTPException(status_code=400, detail="Closing photo required")
    if policy.require_cash_close and payload.cash_close_amount is None:
        raise HTTPException(status_code=400, detail="Closing cash amount required")


@router.post("/companies/{company_id}/shifts/{shift_id}/close", response_model=Shift)
def close_shift(company_id: str, shift_id: str, payload: ShiftCloseRequest) -> Shift:
    _ensure_company(company_id)
    policy = _get_policy(company_id)
    shift = store.shifts.get(shift_id)
    if not shift or shift.company_id != company_id:
        raise HTTPException(status_code=404, detail="Shift not found")
    if shift.status != "OPEN":
        raise HTTPException(status_code=400, detail="Shift is not open")
    if _utc_now() > shift.close_deadline_at:
        shift.status = "EXPIRED"
        shift.end_at = _utc_now()
        store.shifts[shift.id] = shift
        raise HTTPException(status_code=400, detail="Shift expired and cannot be closed")
    if policy.tests_block_shift_closure and not _monthly_test_passed(company_id, shift.user_id):
        raise HTTPException(status_code=400, detail="Monthly test is overdue")
    _validate_shift_close(policy, payload)
    shift.status = "CLOSED"
    shift.end_at = _utc_now()
    shift.close_data = {
        "checklist": payload.close_checklist,
        "photo_url": payload.close_photo_url,
        "write_off_reason": payload.write_off_reason,
        "notes": payload.notes,
    }
    if payload.cash_close_amount is not None:
        shift.cash_logs.append(
            CashLog(type="close", amount=payload.cash_close_amount, created_at=_utc_now())
        )
    store.shifts[shift.id] = shift
    return shift


@router.get("/companies/{company_id}/shifts", response_model=list[Shift])
def list_shifts(company_id: str) -> list[Shift]:
    _ensure_company(company_id)
    return store._filter_by_company(store.shifts, company_id)


@router.post("/companies/{company_id}/incidents", response_model=Incident)
def create_incident(company_id: str, payload: IncidentCreate) -> Incident:
    _ensure_company(company_id)
    incident = Incident(
        id=_new_id(),
        company_id=company_id,
        shift_id=payload.shift_id,
        level=payload.level,
        category=payload.category,
        text=payload.text,
        media_url=payload.media_url,
        status="open",
        created_at=_utc_now(),
    )
    store.incidents[incident.id] = incident
    return incident


@router.get("/companies/{company_id}/incidents", response_model=list[Incident])
def list_incidents(company_id: str) -> list[Incident]:
    _ensure_company(company_id)
    return store._filter_by_company(store.incidents, company_id)


@router.post("/companies/{company_id}/training/sections", response_model=TrainingSection)
def create_training_section(company_id: str, payload: TrainingSectionCreate) -> TrainingSection:
    _ensure_company(company_id)
    section = TrainingSection(
        id=_new_id(),
        company_id=company_id,
        title=payload.title,
        order=payload.order,
    )
    store.training_sections[section.id] = section
    return section


@router.get("/companies/{company_id}/training/sections", response_model=list[TrainingSection])
def list_training_sections(company_id: str) -> list[TrainingSection]:
    _ensure_company(company_id)
    return store._filter_by_company(store.training_sections, company_id)


@router.post("/companies/{company_id}/training/lessons", response_model=TrainingLesson)
def create_training_lesson(company_id: str, payload: TrainingLessonCreate) -> TrainingLesson:
    _ensure_company(company_id)
    lesson = TrainingLesson(
        id=_new_id(),
        company_id=company_id,
        section_id=payload.section_id,
        title=payload.title,
        body=payload.body,
        media_links=payload.media_links,
        tags=payload.tags,
        updated_at=_utc_now(),
    )
    store.training_lessons[lesson.id] = lesson
    return lesson


@router.get("/companies/{company_id}/training/lessons", response_model=list[TrainingLesson])
def list_training_lessons(company_id: str) -> list[TrainingLesson]:
    _ensure_company(company_id)
    return store._filter_by_company(store.training_lessons, company_id)


@router.post("/companies/{company_id}/quizzes", response_model=Quiz)
def create_quiz(company_id: str, payload: QuizCreate) -> Quiz:
    _ensure_company(company_id)
    quiz = Quiz(
        id=_new_id(),
        company_id=company_id,
        title=payload.title,
        type=payload.type,
        passing_score=payload.passing_score,
    )
    store.quizzes[quiz.id] = quiz
    return quiz


@router.post("/companies/{company_id}/quizzes/{quiz_id}/questions", response_model=QuizQuestion)
def add_quiz_question(company_id: str, quiz_id: str, payload: QuizQuestionCreate) -> QuizQuestion:
    _ensure_company(company_id)
    quiz = store.quizzes.get(quiz_id)
    if not quiz or quiz.company_id != company_id:
        raise HTTPException(status_code=404, detail="Quiz not found")
    question = QuizQuestion(
        id=_new_id(),
        quiz_id=quiz_id,
        text=payload.text,
        answers=payload.answers,
        correct_answers=payload.correct_answers,
        explanation=payload.explanation,
    )
    store.quiz_questions[question.id] = question
    return question


def _score_attempt(quiz_id: str, answers: dict[str, list[int]]) -> int:
    quiz_questions = [q for q in store.quiz_questions.values() if q.quiz_id == quiz_id]
    if not quiz_questions:
        return 0
    correct = 0
    for question in quiz_questions:
        selected = answers.get(question.id, [])
        if sorted(selected) == sorted(question.correct_answers):
            correct += 1
    return round((correct / len(quiz_questions)) * 100)


@router.post("/companies/{company_id}/quizzes/{quiz_id}/attempts", response_model=QuizAttempt)
def create_quiz_attempt(
    company_id: str,
    quiz_id: str,
    payload: QuizAttemptCreate,
) -> QuizAttempt:
    _ensure_company(company_id)
    quiz = store.quizzes.get(quiz_id)
    if not quiz or quiz.company_id != company_id:
        raise HTTPException(status_code=404, detail="Quiz not found")
    started_at = _utc_now()
    score = _score_attempt(quiz_id, payload.answers)
    finished_at = _utc_now()
    attempt = QuizAttempt(
        id=_new_id(),
        quiz_id=quiz_id,
        user_id=payload.user_id,
        started_at=started_at,
        finished_at=finished_at,
        score=score,
        passed=score >= quiz.passing_score,
    )
    store.quiz_attempts[attempt.id] = attempt
    return attempt


@router.get("/companies/{company_id}/quizzes/{quiz_id}/attempts", response_model=list[QuizAttempt])
def list_quiz_attempts(company_id: str, quiz_id: str) -> list[QuizAttempt]:
    _ensure_company(company_id)
    quiz = store.quizzes.get(quiz_id)
    if not quiz or quiz.company_id != company_id:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return [attempt for attempt in store.quiz_attempts.values() if attempt.quiz_id == quiz_id]


@router.post("/companies/{company_id}/schedule", response_model=ScheduleEntry)
def create_schedule_entry(company_id: str, payload: ScheduleEntryCreate) -> ScheduleEntry:
    _ensure_company(company_id)
    entry = ScheduleEntry(
        id=_new_id(),
        company_id=company_id,
        location_id=payload.location_id,
        user_id=payload.user_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        status=payload.status,
    )
    store.schedule_entries[entry.id] = entry
    return entry


@router.get("/companies/{company_id}/schedule", response_model=list[ScheduleEntry])
def list_schedule_entries(company_id: str) -> list[ScheduleEntry]:
    _ensure_company(company_id)
    return store._filter_by_company(store.schedule_entries, company_id)


@router.post("/companies/{company_id}/mystery-shopper", response_model=MysteryShopperReport)
def create_mystery_report(
    company_id: str, payload: MysteryShopperReportCreate
) -> MysteryShopperReport:
    _ensure_company(company_id)
    report = MysteryShopperReport(
        id=_new_id(),
        company_id=company_id,
        location_id=payload.location_id,
        user_id=payload.user_id,
        shift_id=payload.shift_id,
        score=payload.score,
        answers=payload.answers,
        created_at=_utc_now(),
    )
    store.mystery_reports[report.id] = report
    return report


@router.get("/companies/{company_id}/mystery-shopper", response_model=list[MysteryShopperReport])
def list_mystery_reports(company_id: str) -> list[MysteryShopperReport]:
    _ensure_company(company_id)
    return store._filter_by_company(store.mystery_reports, company_id)
