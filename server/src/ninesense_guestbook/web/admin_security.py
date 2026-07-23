from datetime import datetime, timezone

from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from ..admin_models import AdminLoginChallenge, AdminRecoveryCode
from ..models import Admin, AdminSession
from ..services.audit import record_audit
from ..services.crypto import EncryptedContact
from ..services.mfa import (
    generate_recovery_codes,
    hash_recovery_code,
    verify_totp,
)
from ..services.sessions import (
    as_utc,
    create_session,
    derive_client_label,
    require_csrf,
    require_recent_reauthentication,
    require_session,
    token_hash,
    touch_session,
)


router = APIRouter(prefix="/api/admin", tags=["admin-security"])


class MfaCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_token: str = Field(min_length=32, max_length=200)
    code: str = Field(min_length=6, max_length=32)


class ReauthenticationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=200)
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


def valid_admin_factor(
    db,
    request: Request,
    admin: Admin,
    code: str,
    now: datetime,
) -> tuple[bool, AdminRecoveryCode | None]:
    secret = decrypt_admin_secret(request, admin)
    if verify_totp(secret, code, now.timestamp()):
        return True, None
    try:
        recovery_hash = hash_recovery_code(code, request.app.state.settings.session_pepper)
    except ValueError:
        return False, None
    row = db.scalar(
        select(AdminRecoveryCode).where(
            AdminRecoveryCode.admin_id == admin.id,
            AdminRecoveryCode.code_hash == recovery_hash,
            AdminRecoveryCode.used_at.is_(None),
        )
    )
    return row is not None, row


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
            valid, recovery_row = valid_admin_factor(
                db,
                request,
                admin,
                payload.code,
                now,
            )
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
            derive_client_label(request.headers.get("user-agent", "")),
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


@router.get("/sessions")
def list_sessions(request: Request) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        touched = touch_session(current)
        rows = list(
            db.scalars(
                select(AdminSession)
                .where(AdminSession.admin_id == current.admin.id)
                .order_by(AdminSession.created_at.desc(), AdminSession.public_id.desc())
            )
        )
        if touched:
            db.commit()
        return {
            "items": [
                {
                    "public_id": row.public_id,
                    "client_label": row.client_label,
                    "created_at": as_utc(row.created_at).isoformat(),
                    "last_seen_at": as_utc(row.last_seen_at).isoformat(),
                    "expires_at": as_utc(row.expires_at).isoformat(),
                    "current": row.id_hash == current.row.id_hash,
                }
                for row in rows
            ]
        }


@router.delete("/sessions/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(public_id: str, request: Request, response: Response) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.scalar(
            select(AdminSession).where(
                AdminSession.admin_id == current.admin.id,
                AdminSession.public_id == public_id,
            )
        )
        if row is None:
            raise HTTPException(status_code=404, detail="会话不存在。")
        deleting_current = row.id_hash == current.row.id_hash
        db.delete(row)
        record_audit(
            db,
            action="session.revoked",
            outcome="success",
            admin_id=current.admin.id,
            target_type="session",
            target_id=public_id,
        )
        db.commit()
    if deleting_current:
        settings = request.app.state.settings
        response.delete_cookie(
            key=settings.cookie_name,
            path="/",
            secure=settings.cookie_secure,
            httponly=True,
            samesite="strict",
        )


@router.post(
    "/session/reauthenticate",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reauthenticate(
    payload: ReauthenticationRequest,
    request: Request,
) -> None:
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        try:
            password_valid = request.app.state.password_hasher.verify(
                current.admin.password_hash,
                payload.password,
            )
        except (VerificationError, VerifyMismatchError):
            password_valid = False
        factor_valid, recovery_row = valid_admin_factor(
            db,
            request,
            current.admin,
            payload.code,
            now,
        )
        if not password_valid or not factor_valid:
            record_audit(
                db,
                action="session.reauthenticate",
                outcome="failure",
                admin_id=current.admin.id,
                details={"reason_code": "invalid_credentials"},
            )
            db.commit()
            raise HTTPException(status_code=401, detail="身份验证失败。")
        if recovery_row is not None:
            recovery_row.used_at = now
        current.row.last_reauthenticated_at = now
        record_audit(
            db,
            action="session.reauthenticate",
            outcome="success",
            admin_id=current.admin.id,
        )
        db.commit()


@router.post("/mfa/recovery-codes")
def regenerate_recovery_codes(request: Request) -> dict[str, list[str]]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        require_recent_reauthentication(current)
        db.execute(
            delete(AdminRecoveryCode).where(
                AdminRecoveryCode.admin_id == current.admin.id
            )
        )
        codes = generate_recovery_codes()
        db.add_all(
            [
                AdminRecoveryCode(
                    admin_id=current.admin.id,
                    code_hash=hash_recovery_code(
                        code,
                        request.app.state.settings.session_pepper,
                    ),
                )
                for code in codes
            ]
        )
        record_audit(
            db,
            action="mfa.recovery_codes_regenerated",
            outcome="success",
            admin_id=current.admin.id,
            details={"record_count": len(codes)},
        )
        db.commit()
        return {"recovery_codes": codes}


@router.delete("/mfa", status_code=status.HTTP_204_NO_CONTENT)
def disable_mfa(request: Request) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        require_recent_reauthentication(current)
        current.admin.totp_secret_nonce = None
        current.admin.totp_secret_ciphertext = None
        current.admin.totp_secret_key_version = None
        current.admin.totp_enabled_at = None
        db.execute(
            delete(AdminRecoveryCode).where(
                AdminRecoveryCode.admin_id == current.admin.id
            )
        )
        db.execute(
            delete(AdminLoginChallenge).where(
                AdminLoginChallenge.admin_id == current.admin.id
            )
        )
        db.execute(
            delete(AdminSession).where(
                AdminSession.admin_id == current.admin.id,
                AdminSession.id_hash != current.row.id_hash,
            )
        )
        record_audit(
            db,
            action="mfa.disabled",
            outcome="success",
            admin_id=current.admin.id,
        )
        db.commit()
