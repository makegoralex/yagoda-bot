from __future__ import annotations

import os
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.web.mvp import router as mvp_router
from src.web.mvp import load_store

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
app.include_router(mvp_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo", response_class=HTMLResponse)
def demo_page(request: Request) -> HTMLResponse:
    store = load_store()
    companies = list(store.companies.values())
    users = list(store.users.values())
    return templates.TemplateResponse(
        "demo.html",
        {"request": request, "companies": companies, "users": users},
    )


def _render_company_page(request: Request, company_id: str) -> HTMLResponse:
    store = load_store()
    company = store.companies.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    users = [user for user in store.users.values() if user.company_id == company_id]
    return templates.TemplateResponse(
        "company.html",
        {"request": request, "company": company, "users": users},
    )


@app.get("/companies/{company_id}", response_class=HTMLResponse)
def company_page(request: Request, company_id: str) -> HTMLResponse:
    return _render_company_page(request, company_id)


@app.get("/company/{company_id}", response_class=HTMLResponse)
def company_page_alias(request: Request, company_id: str) -> HTMLResponse:
    return _render_company_page(request, company_id)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise HTTPException(
            status_code=500,
            detail=f"Missing required environment variable: {name}",
        )
    return value


@app.post("/api/check-token")
def check_token() -> JSONResponse:
    token = _get_required_env("TELEGRAM_BOT_TOKEN")
    response = requests.get(
        f"https://api.telegram.org/bot{token}/getMe",
        timeout=10,
    )

    if not response.ok:
        raise HTTPException(status_code=500, detail=response.text)

    payload = response.json()
    return JSONResponse(
        {
            "status": "ok",
            "telegram_status": response.status_code,
            "telegram_response": payload,
            "bot_username": payload.get("result", {}).get("username"),
        }
    )
