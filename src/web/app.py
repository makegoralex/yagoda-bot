from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="src/web/templates")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo", response_class=HTMLResponse)
def demo_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("demo.html", {"request": request})


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise HTTPException(
            status_code=500,
            detail=f"Missing required environment variable: {name}",
        )
    return value


@app.post("/api/send-test")
def send_test_message() -> JSONResponse:
    token = _get_required_env("TELEGRAM_BOT_TOKEN")
    chat_id = _get_required_env("TELEGRAM_CHAT_ID")

    payload = {
        "chat_id": chat_id,
        "text": (
            "✅ Проверка связи сайта и бота. "
            f"Время: {datetime.now(timezone.utc).isoformat()}"
        ),
    }

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=10,
    )

    if not response.ok:
        raise HTTPException(status_code=500, detail=response.text)

    return JSONResponse(
        {
            "status": "ok",
            "telegram_status": response.status_code,
            "telegram_response": response.json(),
        }
    )
