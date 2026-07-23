from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from ..admin_models import AdminLoginChallenge, AdminRecoveryCode
from ..models import Admin
from ..services.audit import record_audit
from ..services.crypto import EncryptedContact
from ..services.mfa import (
    generate_recovery_codes,
    hash_recovery_code,
    normalize_recovery_code,
    verify_totp,
)
from ..services.sessions import as_utc, create_session, token_hash


router = APIRouter(prefix="/api/admin", tags=["admin-security"])


class MfaCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_token: str = Field(min_length=32, max_length=200)
    code: str = Field(min_length=6, max_length=32)


def invalid_challenge() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="验证信息无效或已过期。",
    )


def decrypt_challenge_secret(request: Request, challenge: AdminLoginChallenge) -> str:
    if (
        challenge.secret_nonce is None
        or challenge.secret_ciphertext is None
        or challenge.secret_key_version is None
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="两步验证配置不完整。",
        )
    return request.app.state.security_cipher.decrypt(
        EncryptedContact(
            nonce=challenge.secret_nonce,
            ciphertext=challenge.secret_ciphertext,
            key_version=challenge.secret_key_version,
        )
    )


def decrypt_admin_secret(request: Request, admin: Admin) -> str:
    if (
        admin.totp_secret_nonce is None
        or admin.totp_secret_ciphertext is None
        or admin.totp_secret_key_version is None
        or admin.totp_enabled_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="两步验证配置不完整。",
        )
    return request.app.state.security_cipher.decrypt(
        EncryptedContact(
            nonce=admin.totp_secret_nonce,
            ciphertext=admin.totp_secret_ciphertext,
            key_version=admin.totp_secret_key_version,
        )
    )


def set_session_cookie(response: Response, request: Request, session_token: str) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        key=settings.cookie_name,
        value=session_token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


@router.post("/session/mfa")
def complete_mfa(
    payload: MfaCompletionRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    settings = request.app.state.settings
    challenge_hash = token_hash(payload.challenge_token, settings.session_pepper)

    with request.app.state.session_factory() as db:
        challenge = db.get(AdminLoginChallenge, challenge_hash)
        if challenge is None:
            raise invalid_challenge()
        if as_utc(challenge.expires_at) <= now or challenge.attempts >= 5:
            db.delete(challenge)
            db.commit()
            raise invalid_challenge()

        admin = db.get(Admin, challenge.admin_id)
        if admin is None or not admin.active:
            db.delete(challenge)
            db.commit()
            raise invalid_challenge()

        recovery_row = None
        if challenge.purpose == "setup":
            secret = decrypt_challenge_secret(request, challenge)
            valid = verify_totp(secret, payload.code, now.timestamp())
        elif challenge.purpose == "login":
            secret = decrypt_admin_secret(request, admin)
            valid = verify_totp(secret, payload.code, now.timestamp())
            if not valid:
                try:
                    recovery_hash = hash_recovery_code(
                        normalize_recovery_code(payload.code),
                        settings.session_pepper,
                    )
                except ValueError:
                    recovery_hash = ""
                if recovery_hash:
                    recovery_row = db.scalar(
                        select(AdminRecoveryCode).where(
                            AdminRecoveryCode.admin_id == admin.id,
                            AdminRecoveryCode.code_hash == recovery_hash,
                            AdminRecoveryCode.used_at.is_(None),
                        )
                    )
                    valid = recovery_row is not None
        else:
            valid = False

        if not valid:
            challenge.attempts += 1
            record_audit(
                db,
                action="session.mfa",
                outcome="failure",
                admin_id=admin.id,
                details={"reason_code": "invalid_code"},
            )
            if challenge.attempts >= 5:
                db.delete(challenge)
            db.commit()
            raise invalid_challenge()

        raw_recovery_codes = None
        if challenge.purpose == "setup":
            admin.totp_secret_nonce = challenge.secret_nonce
            admin.totp_secret_ciphertext = challenge.secret_ciphertext
            admin.totp_secret_key_version = challenge.secret_key_version
            admin.totp_enabled_at = now
            db.execute(
                delete(AdminRecoveryCode).where(
                    AdminRecoveryCode.admin_id == admin.id
                )
            )
            raw_recovery_codes = generate_recovery_codes()
            db.add_all(
                [
                    AdminRecoveryCode(
                        admin_id=admin.id,
                        code_hash=hash_recovery_code(
                            code,
                            settings.session_pepper,
                        ),
                    )
                    for code in raw_recovery_codes
                ]
            )
        elif recovery_row is not None:
            recovery_row.used_at = now

        db.delete(challenge)
        tokens = create_session(
            db,
            admin.id,
            settings.session_pepper,
            settings.session_hours,
            now,
        )
        record_audit(
            db,
            action="session.login",
            outcome="success",
            admin_id=admin.id,
        )
        db.commit()

    set_session_cookie(response, request, tokens.session_token)
    result: dict[str, object] = {
        "username": admin.username,
        "csrf_token": tokens.csrf_token,
        "expires_at": tokens.expires_at.isoformat(),
    }
    if raw_recovery_codes is not None:
        result["recovery_codes"] = raw_recovery_codes
    return result
