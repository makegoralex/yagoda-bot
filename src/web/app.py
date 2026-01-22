from __future__ import annotations

import os

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
