from datetime import datetime, timedelta, timezone
import secrets

from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from ..admin_models import AdminLoginChallenge
from ..models import Admin
from ..services.audit import record_audit
from ..services.admin_notifications import create_notification_once
from ..services.mfa import build_otpauth_uri, generate_totp_secret
from ..services.sessions import (
    as_utc,
    require_csrf,
    require_session,
    revoke_session,
    rotate_csrf,
    token_hash,
    touch_session,
)


router = APIRouter(prefix="/api/admin", tags=["admin-auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


@router.post("/session", status_code=status.HTTP_202_ACCEPTED)
def login(payload: LoginRequest, request: Request) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    client_ip = request.client.host if request.client is not None else "unknown"
    limiter = request.app.state.login_limiter
    if limiter.is_locked(client_ip, payload.username, now):
        with request.app.state.session_factory() as db:
            create_notification_once(
                db,
                severity="warning",
                category="security",
                title="后台登录已临时锁定",
                message="连续验证失败，登录入口已暂时限制。",
                now=now,
            )
            record_audit(
                db,
                action="session.password",
                outcome="denied",
                details={"reason_code": "rate_limited"},
            )
            db.commit()
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
            record_audit(
                db,
                action="session.password",
                outcome="failure",
                admin_id=admin.id if admin is not None else None,
                details={"reason_code": "invalid_credentials"},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码不正确。",
            )

        limiter.record_success(client_ip, payload.username, now)
        if request.app.state.password_hasher.check_needs_rehash(admin.password_hash):
            admin.password_hash = request.app.state.password_hasher.hash(payload.password)
        settings = request.app.state.settings
        db.execute(
            delete(AdminLoginChallenge).where(
                AdminLoginChallenge.admin_id == admin.id,
                AdminLoginChallenge.expires_at <= now,
            )
        )
        raw_challenge = secrets.token_urlsafe(32)
        challenge = AdminLoginChallenge(
            id_hash=token_hash(raw_challenge, settings.session_pepper),
            admin_id=admin.id,
            purpose="login" if admin.totp_enabled_at is not None else "setup",
            expires_at=now + timedelta(minutes=settings.login_challenge_minutes),
        )
        response_body = {
            "stage": "mfa_required",
            "challenge_token": raw_challenge,
            "expires_at": challenge.expires_at.isoformat(),
        }
        if challenge.purpose == "setup":
            secret = generate_totp_secret()
            encrypted = request.app.state.security_cipher.encrypt(secret)
            challenge.secret_nonce = encrypted.nonce
            challenge.secret_ciphertext = encrypted.ciphertext
            challenge.secret_key_version = encrypted.key_version
            response_body["stage"] = "mfa_setup_required"
            response_body["setup_uri"] = build_otpauth_uri(
                secret,
                admin.username,
            )
        db.add(challenge)
        record_audit(
            db,
            action="session.password",
            outcome="success",
            admin_id=admin.id,
        )
        db.commit()
        return response_body


@router.get("/session")
def current_session(request: Request) -> dict[str, str]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        touch_session(current)
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
