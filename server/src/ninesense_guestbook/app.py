import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from argon2 import PasswordHasher
from sqlalchemy import select

from .admin_models import AdminLoginChallenge
from .config import Settings, get_settings
from .db import build_session_factory
from .models import Admin
from .services.crypto import ContactCipher, EncryptedContact
from .services.mfa import totp_at
from .services.outbox import outbox_worker
from .services.rate_limit import SubmissionLimiter
from .services.sessions import LoginAttemptLimiter
from .web.admin import outbox_router, router as admin_router
from .web.admin_dashboard import router as admin_dashboard_router
from .web.admin_security import router as admin_security_router
from .web.auth import router as auth_router
from .web.middleware import ApiProtectionMiddleware
from .web.public import router as public_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    engine, session_factory = build_session_factory(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        worker = None
        if resolved_settings.smtp_host and resolved_settings.notification_to:
            worker = asyncio.create_task(outbox_worker(application))
        try:
            yield
        finally:
            if worker is not None:
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass

    app = FastAPI(
        title="NineSense Guestbook",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.contact_cipher = ContactCipher.from_urlsafe_key(resolved_settings.contact_key)
    app.state.security_cipher = ContactCipher.from_urlsafe_key(
        resolved_settings.security_key
    )
    app.state.submission_limiter = SubmissionLimiter(resolved_settings.rate_limit_key)
    app.state.login_limiter = LoginAttemptLimiter(resolved_settings.rate_limit_key)
    app.state.password_hasher = PasswordHasher()
    app.state.dummy_hash = app.state.password_hasher.hash("not-a-real-password")
    app.add_middleware(ApiProtectionMiddleware, max_body_bytes=32 * 1024)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    if resolved_settings.testing:

        @app.get("/__e2e/current-totp")
        def current_e2e_totp():
            with app.state.session_factory() as db:
                challenge = db.scalar(
                    select(AdminLoginChallenge)
                    .where(AdminLoginChallenge.purpose == "setup")
                    .order_by(AdminLoginChallenge.created_at.desc())
                    .limit(1)
                )
                if challenge is not None:
                    encrypted = EncryptedContact(
                        challenge.secret_nonce,
                        challenge.secret_ciphertext,
                        challenge.secret_key_version,
                    )
                else:
                    admin = db.scalar(
                        select(Admin).where(Admin.totp_enabled_at.is_not(None)).limit(1)
                    )
                    if admin is None:
                        return {"value": ""}
                    encrypted = EncryptedContact(
                        admin.totp_secret_nonce,
                        admin.totp_secret_ciphertext,
                        admin.totp_secret_key_version,
                    )
                if (
                    encrypted.nonce is None
                    or encrypted.ciphertext is None
                    or encrypted.key_version is None
                ):
                    return {"value": ""}
                secret = app.state.security_cipher.decrypt(encrypted)
                return {"value": totp_at(secret, datetime.now(timezone.utc).timestamp())}

    app.include_router(public_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(outbox_router)
    app.include_router(admin_security_router)
    app.include_router(admin_dashboard_router)
    return app
