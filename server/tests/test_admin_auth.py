from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from sqlalchemy import select

from ninesense_guestbook.admin_models import AdminLoginChallenge
from ninesense_guestbook.models import Admin, AdminSession
from ninesense_guestbook.services.sessions import LoginAttemptLimiter

from admin_test_helpers import create_totp_admin, login_with_totp


PASSWORD = "A-secure-test-password-2026"


def create_admin(db_session):
    admin = Admin(
        username="ninesense",
        password_hash=PasswordHasher().hash(PASSWORD),
        active=True,
    )
    db_session.add(admin)
    db_session.commit()
    return admin


def login(client, password=PASSWORD):
    return client.post(
        "/api/admin/session",
        json={"username": "ninesense", "password": password},
    )


def test_password_login_creates_setup_challenge_without_session(
    client, db_session
):
    create_admin(db_session)

    response = login(client)

    assert response.status_code == 202
    assert response.json()["stage"] == "mfa_setup_required"
    assert response.json()["challenge_token"]
    assert response.json()["setup_uri"].startswith("otpauth://totp/")
    assert "set-cookie" not in response.headers
    assert db_session.scalars(select(AdminSession)).all() == []
    assert db_session.scalars(select(AdminLoginChallenge)).one().purpose == "setup"


def test_enabled_admin_receives_mfa_challenge_without_secret(
    client, db_session, app
):
    admin = create_admin(db_session)
    encrypted = app.state.security_cipher.encrypt("JBSWY3DPEHPK3PXP")
    admin.totp_secret_nonce = encrypted.nonce
    admin.totp_secret_ciphertext = encrypted.ciphertext
    admin.totp_secret_key_version = encrypted.key_version
    admin.totp_enabled_at = datetime.now(timezone.utc)
    db_session.commit()

    response = login(client)

    assert response.status_code == 202
    assert response.json()["stage"] == "mfa_required"
    assert "setup_uri" not in response.json()
    assert db_session.scalars(select(AdminSession)).all() == []


def test_login_limiter_progressively_increases_the_lock_period():
    limiter = LoginAttemptLimiter("secret")
    start = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)

    for _ in range(5):
        limiter.record_failure("192.0.2.1", "ninesense", start)

    assert limiter.is_locked("192.0.2.1", "ninesense", start + timedelta(seconds=29))
    assert not limiter.is_locked(
        "192.0.2.1", "ninesense", start + timedelta(seconds=31)
    )

    limiter.record_failure(
        "192.0.2.1", "ninesense", start + timedelta(seconds=31)
    )
    assert limiter.is_locked("192.0.2.1", "ninesense", start + timedelta(seconds=90))
    assert not limiter.is_locked(
        "192.0.2.1", "ninesense", start + timedelta(seconds=92)
    )


def test_correct_login_sets_hardened_cookie_and_stores_only_hash(
    client, db_session, app
):
    _admin, secret = create_totp_admin(db_session, app)

    response = login_with_totp(client, secret)

    assert response.status_code == 200
    body = response.json()
    assert body["csrf_token"]
    assert body["expires_at"].endswith("+00:00")
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "secure" not in cookie
    stored = db_session.scalars(select(AdminSession)).one()
    assert stored.id_hash not in response.headers["set-cookie"]
    assert body["csrf_token"] != stored.csrf_hash


def test_secure_cookie_flag_follows_production_setting(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    app.state.settings.cookie_secure = True

    response = login_with_totp(client, secret)

    assert "; secure" in response.headers["set-cookie"].lower()


def test_unknown_user_and_wrong_password_have_identical_responses(client, db_session):
    create_admin(db_session)

    wrong = login(client, "wrong-password")
    unknown = client.post(
        "/api/admin/session",
        json={"username": "does-not-exist", "password": "wrong-password"},
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "用户名或密码不正确。"}


def test_repeated_failures_temporarily_lock_login(client, db_session):
    create_admin(db_session)

    for _ in range(5):
        assert login(client, "wrong-password").status_code == 401

    locked = login(client)
    assert locked.status_code == 429
    assert locked.json() == {"detail": "登录尝试过多，请稍后再试。"}


def test_session_refresh_rotates_csrf_and_logout_revokes_session(
    client, db_session, app
):
    _admin, secret = create_totp_admin(db_session, app)
    first_csrf = login_with_totp(client, secret).json()["csrf_token"]

    current = client.get("/api/admin/session")
    assert current.status_code == 200
    assert current.json()["username"] == "ninesense"
    refreshed_csrf = current.json()["csrf_token"]
    assert refreshed_csrf != first_csrf

    rejected = client.delete(
        "/api/admin/session",
        headers={"X-CSRF-Token": first_csrf},
    )
    assert rejected.status_code == 403

    logout = client.delete(
        "/api/admin/session",
        headers={"X-CSRF-Token": refreshed_csrf},
    )
    assert logout.status_code == 204
    assert db_session.scalars(select(AdminSession)).all() == []
    assert client.get("/api/admin/session").status_code == 401


def test_logout_requires_csrf(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    login_with_totp(client, secret)

    response = client.delete("/api/admin/session")

    assert response.status_code == 403


def test_expired_session_is_rejected_and_removed(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    login_with_totp(client, secret)
    stored = db_session.scalars(select(AdminSession)).one()
    stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    response = client.get("/api/admin/session")

    assert response.status_code == 401
    db_session.expire_all()
    assert db_session.scalars(select(AdminSession)).all() == []
