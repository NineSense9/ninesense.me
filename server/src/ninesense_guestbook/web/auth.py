from datetime import datetime, timezone

from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..models import Admin
from ..services.sessions import (
    as_utc,
    create_session,
    require_csrf,
    require_session,
    revoke_session,
    rotate_csrf,
)


router = APIRouter(prefix="/api/admin", tags=["admin-auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


@router.post("/session")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    client_ip = request.client.host if request.client is not None else "unknown"
    limiter = request.app.state.login_limiter
    if limiter.is_locked(client_ip, payload.username, now):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过多，请稍后再试。",
        )

    with request.app.state.session_factory() as db:
        admin = db.scalar(select(Admin).where(Admin.username == payload.username.strip()))
        password_hash = admin.password_hash if admin is not None else request.app.state.dummy_hash
        try:
            password_valid = request.app.state.password_hasher.verify(
                password_hash,
                payload.password,
            )
        except (VerificationError, VerifyMismatchError):
            password_valid = False

        if admin is None or not admin.active or not password_valid:
            limiter.record_failure(client_ip, payload.username, now)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码不正确。",
            )

        limiter.record_success(client_ip, payload.username, now)
        if request.app.state.password_hasher.check_needs_rehash(admin.password_hash):
            admin.password_hash = request.app.state.password_hasher.hash(payload.password)
        settings = request.app.state.settings
        tokens = create_session(
            db,
            admin.id,
            settings.session_pepper,
            settings.session_hours,
            now,
        )
        db.commit()

    response.set_cookie(
        key=settings.cookie_name,
        value=tokens.session_token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {
        "csrf_token": tokens.csrf_token,
        "expires_at": tokens.expires_at.isoformat(),
    }


@router.get("/session")
def current_session(request: Request) -> dict[str, str]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        csrf_token = rotate_csrf(current, request.app.state.settings.session_pepper)
        db.commit()
        return {
            "username": current.admin.username,
            "csrf_token": csrf_token,
            "expires_at": as_utc(current.row.expires_at).isoformat(),
        }


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        revoke_session(db, current)
        db.commit()

    settings = request.app.state.settings
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )

