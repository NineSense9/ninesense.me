from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time
from urllib.parse import parse_qs, urlparse

from argon2 import PasswordHasher
import pytest
from sqlalchemy import select

from ninesense_guestbook.admin_models import (
    AdminLoginChallenge,
    AdminRecoveryCode,
)
from ninesense_guestbook.models import Admin, AdminSession
from ninesense_guestbook.services.mfa import totp_at
from ninesense_guestbook.services.sessions import token_hash

from admin_test_helpers import PASSWORD, create_totp_admin, login_with_totp


@dataclass(frozen=True)
class SetupChallengeFixture:
    token: str
    id_hash: str
    admin_id: int
    secret: str
    current_code: str


@pytest.fixture
def setup_challenge(client, db_session, app):
    admin = Admin(
        username="ninesense",
        password_hash=PasswordHasher().hash(PASSWORD),
        active=True,
    )
    db_session.add(admin)
    db_session.commit()
    response = client.post(
        "/api/admin/session",
        json={"username": "ninesense", "password": PASSWORD},
    )
    token = response.json()["challenge_token"]
    secret = parse_qs(urlparse(response.json()["setup_uri"]).query)["secret"][0]
    return SetupChallengeFixture(
        token=token,
        id_hash=token_hash(token, app.state.settings.session_pepper),
        admin_id=admin.id,
        secret=secret,
        current_code=totp_at(secret, time.time()),
    )


def complete_mfa(client, challenge_token, code):
    return client.post(
        "/api/admin/session/mfa",
        json={"challenge_token": challenge_token, "code": code},
    )


def test_setup_code_enables_totp_and_returns_recovery_codes(
    client, db_session, setup_challenge
):
    response = complete_mfa(
        client,
        setup_challenge.token,
        setup_challenge.current_code,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["recovery_codes"]) == 10
    assert len(set(body["recovery_codes"])) == 10
    assert body["csrf_token"]
    assert "httponly" in response.headers["set-cookie"].lower()
    db_session.expire_all()
    admin = db_session.get(Admin, setup_challenge.admin_id)
    assert admin.totp_enabled_at is not None
    assert admin.totp_secret_ciphertext is not None
    assert setup_challenge.secret not in response.text
    assert db_session.get(AdminLoginChallenge, setup_challenge.id_hash) is None
    assert len(db_session.scalars(select(AdminRecoveryCode)).all()) == 10
    assert len(db_session.scalars(select(AdminSession)).all()) == 1


def test_fifth_wrong_totp_consumes_the_challenge(
    client, db_session, setup_challenge
):
    for _ in range(4):
        response = complete_mfa(client, setup_challenge.token, "000000")
        assert response.status_code == 401

    fifth = complete_mfa(client, setup_challenge.token, "000000")

    assert fifth.status_code == 401
    assert fifth.json() == {"detail": "验证信息无效或已过期。"}
    db_session.expire_all()
    assert db_session.get(AdminLoginChallenge, setup_challenge.id_hash) is None


def test_totp_login_creates_session_without_returning_secret(
    client, db_session, app
):
    _admin, secret = create_totp_admin(db_session, app)

    response = login_with_totp(client, secret)

    assert response.status_code == 200
    assert response.json()["username"] == "ninesense"
    assert "recovery_codes" not in response.json()
    assert secret not in response.text
    assert len(db_session.scalars(select(AdminSession)).all()) == 1


def test_recovery_code_logs_in_once_and_cannot_be_reused(
    client, db_session, setup_challenge
):
    setup = complete_mfa(
        client,
        setup_challenge.token,
        setup_challenge.current_code,
    )
    recovery_code = setup.json()["recovery_codes"][0]

    first_challenge = client.post(
        "/api/admin/session",
        json={"username": "ninesense", "password": PASSWORD},
    )
    first = complete_mfa(
        client,
        first_challenge.json()["challenge_token"],
        recovery_code,
    )
    assert first.status_code == 200

    second_challenge = client.post(
        "/api/admin/session",
        json={"username": "ninesense", "password": PASSWORD},
    )
    replay = complete_mfa(
        client,
        second_challenge.json()["challenge_token"],
        recovery_code,
    )
    assert replay.status_code == 401
    assert (
        len(
            db_session.scalars(
                select(AdminRecoveryCode).where(
                    AdminRecoveryCode.used_at.is_not(None)
                )
            ).all()
        )
        == 1
    )


def test_expired_and_replayed_challenges_are_rejected(
    client, db_session, setup_challenge
):
    challenge = db_session.get(AdminLoginChallenge, setup_challenge.id_hash)
    challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    expired = complete_mfa(
        client,
        setup_challenge.token,
        setup_challenge.current_code,
    )
    replay = complete_mfa(
        client,
        setup_challenge.token,
        setup_challenge.current_code,
    )

    assert expired.status_code == replay.status_code == 401
    assert expired.json() == replay.json() == {
        "detail": "验证信息无效或已过期。"
    }


def test_session_list_returns_public_metadata_only(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    first = login_with_totp(client, secret)
    assert first.status_code == 200
    second = login_with_totp(client, secret)
    assert second.status_code == 200

    response = client.get("/api/admin/sessions")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert sum(item["current"] for item in response.json()["items"]) == 1
    for item in response.json()["items"]:
        assert set(item) == {
            "public_id",
            "client_label",
            "created_at",
            "last_seen_at",
            "expires_at",
            "current",
        }
        assert "hash" not in str(item).lower()
        assert "ip" not in str(item).lower()


def test_owner_can_revoke_another_session_with_csrf(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    login_with_totp(client, secret)
    current_login = login_with_totp(client, secret)
    sessions = client.get("/api/admin/sessions").json()["items"]
    other = next(item for item in sessions if not item["current"])

    forged = client.delete(
        f"/api/admin/sessions/{other['public_id']}",
        headers={"X-CSRF-Token": "forged"},
    )
    revoked = client.delete(
        f"/api/admin/sessions/{other['public_id']}",
        headers={"X-CSRF-Token": current_login.json()["csrf_token"]},
    )

    assert forged.status_code == 403
    assert revoked.status_code == 204
    assert len(db_session.scalars(select(AdminSession)).all()) == 1


def test_reauthentication_requires_password_and_totp(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    login_response = login_with_totp(client, secret)
    headers = {"X-CSRF-Token": login_response.json()["csrf_token"]}

    wrong = client.post(
        "/api/admin/session/reauthenticate",
        headers=headers,
        json={"password": PASSWORD, "code": "000000"},
    )
    correct = client.post(
        "/api/admin/session/reauthenticate",
        headers=headers,
        json={"password": PASSWORD, "code": totp_at(secret, time.time())},
    )

    assert wrong.status_code == 401
    assert correct.status_code == 204
    db_session.expire_all()
    assert db_session.scalars(select(AdminSession)).one().last_reauthenticated_at


def test_recovery_code_regeneration_requires_recent_reauthentication(
    client, db_session, app
):
    _admin, secret = create_totp_admin(db_session, app)
    login_response = login_with_totp(client, secret)
    headers = {"X-CSRF-Token": login_response.json()["csrf_token"]}

    denied = client.post("/api/admin/mfa/recovery-codes", headers=headers)
    assert denied.status_code == 403

    reauthenticated = client.post(
        "/api/admin/session/reauthenticate",
        headers=headers,
        json={"password": PASSWORD, "code": totp_at(secret, time.time())},
    )
    assert reauthenticated.status_code == 204
    generated = client.post("/api/admin/mfa/recovery-codes", headers=headers)

    assert generated.status_code == 200
    assert len(generated.json()["recovery_codes"]) == 10
    assert len(db_session.scalars(select(AdminRecoveryCode)).all()) == 10


def test_recent_reauthentication_expires_after_five_minutes(
    client, db_session, app
):
    _admin, secret = create_totp_admin(db_session, app)
    login_response = login_with_totp(client, secret)
    headers = {"X-CSRF-Token": login_response.json()["csrf_token"]}
    client.post(
        "/api/admin/session/reauthenticate",
        headers=headers,
        json={"password": PASSWORD, "code": totp_at(secret, time.time())},
    )
    session = db_session.scalars(select(AdminSession)).one()
    session.last_reauthenticated_at = datetime.now(timezone.utc) - timedelta(minutes=6)
    db_session.commit()

    response = client.post("/api/admin/mfa/recovery-codes", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "请重新验证身份后再继续。"}


def test_disabling_mfa_requires_reauthentication_and_revokes_other_sessions(
    client, db_session, app
):
    admin, secret = create_totp_admin(db_session, app)
    login_with_totp(client, secret)
    current_login = login_with_totp(client, secret)
    headers = {"X-CSRF-Token": current_login.json()["csrf_token"]}
    client.post(
        "/api/admin/session/reauthenticate",
        headers=headers,
        json={"password": PASSWORD, "code": totp_at(secret, time.time())},
    )

    response = client.delete("/api/admin/mfa", headers=headers)

    assert response.status_code == 204
    db_session.expire_all()
    refreshed = db_session.get(Admin, admin.id)
    assert refreshed.totp_enabled_at is None
    assert refreshed.totp_secret_ciphertext is None
    assert len(db_session.scalars(select(AdminSession)).all()) == 1
