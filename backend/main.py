"""DashZone Milestone 3 API — FastAPI backend for Team 117.

Base URL: http://localhost:8000/api
Every endpoint returns the same envelope:
    {"ok": bool, "code": int, "message": str, "data": ...}

Sessions are signed cookies (Starlette SessionMiddleware) holding user_id and
user_type. The frontend runs on http://localhost:3000, so CORS allows that
origin with credentials.

Run from this directory:
    .venv/bin/python -m uvicorn main:app --port 8000 --reload
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

import db
from auth import AuthError
from db import DatabaseError
from routers import admin, auth, customer, partner, rider, shared

load_dotenv()

logger = logging.getLogger("dashzone")

app = FastAPI(title="DashZone Milestone 3 API", version="1.0.0")

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
if not SESSION_SECRET:
    logger.warning(
        "SESSION_SECRET is not set; using the built-in dev secret. "
        "Set SESSION_SECRET in .env before sharing this server."
    )
    SESSION_SECRET = "dashzone-dev-secret-change-me"

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "code": -3, "message": exc.message, "data": None},
    )


@app.exception_handler(DatabaseError)
async def db_error_handler(request: Request, exc: DatabaseError):
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "code": -1,
            "message": "Something went wrong on our side. Please try again.",
            "data": None,
        },
    )


@app.get("/health")
def health():
    if db.ping():
        return {"ok": True, "code": 0, "message": "OK", "data": {"status": "ok", "database": "ok"}}
    return JSONResponse(
        status_code=503,
        content={
            "ok": False,
            "code": -1,
            "message": "The database is not reachable.",
            "data": {"status": "ok", "database": "down"},
        },
    )


app.include_router(auth.router, prefix="/api")
app.include_router(shared.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(partner.router, prefix="/api")
app.include_router(rider.router, prefix="/api")
app.include_router(customer.router, prefix="/api")
