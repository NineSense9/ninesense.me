from datetime import datetime, timezone

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select

from ninesense_guestbook.admin_models import (
    AdminLoginChallenge,
    AdminNotification,
    AdminRecoveryCode,
    AuditEvent,
)
from ninesense_guestbook.cli import (
    create_admin_record,
    list_admin_sessions,
    reset_admin_mfa,
    revoke_admin_sessions,
    validate_admin_password,
)
from ninesense_guestbook.models import Admin, AdminSession


def test_admin_password_must_be_long_and_varied():
    for password in ("short", "alllowercasepassword", "ALLUPPERCASEPASSWORD", "123456789012"):
        with pytest.raises(ValueError):
            validate_admin_password(password)

    validate_admin_password("Strong-password-2026")


def test_create_admin_refuses_to_add_a_second_account(db_session):
    create_admin_record(db_session, "ninesense", "Strong-password-2026")

    with pytest.raises(ValueError, match="already exists"):
        create_admin_record(db_session, "another", "Another-password-2026")

    assert len(db_session.scalars(select(Admin)).all()) == 1


def test_reset_admin_mfa_verifies_password_and_revokes_security_state(db_session):
    password = "Strong-password-2026"
    admin = Admin(
        username="ninesense",
        password_hash=PasswordHasher().hash(password),
        active=True,
        totp_secret_nonce=b"n" * 12,
        totp_secret_ciphertext=b"ciphertext",
        totp_secret_key_version=1,
    )
    db_session.add(admin)
    db_session.flush()
    db_session.add_all(
        [
            AdminSession(
                id_hash="a" * 64,
                admin_id=admin.id,
                csrf_hash="b" * 64,
                expires_at=datetime.now(timezone.utc),
            ),
            AdminRecoveryCode(admin_id=admin.id, code_hash="c" * 64),
            AdminLoginChallenge(
                id_hash="d" * 64,
                admin_id=admin.id,
                purpose="login",
                expires_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db_session.commit()

    with pytest.raises(ValueError, match="password is incorrect"):
        reset_admin_mfa(db_session, "ninesense", "wrong-password")

    reset_admin_mfa(db_session, "ninesense", password)
    db_session.expire_all()
    refreshed = db_session.get(Admin, admin.id)
    assert refreshed.totp_secret_ciphertext is None
    assert db_session.scalars(select(AdminSession)).all() == []
    assert db_session.scalars(select(AdminRecoveryCode)).all() == []
    assert db_session.scalars(select(AdminLoginChallenge)).all() == []
    assert db_session.scalars(select(AdminNotification)).one().category == "security"
    assert db_session.scalars(select(AuditEvent)).one().action == "mfa.reset_from_cli"


def test_list_and_revoke_admin_sessions_use_public_metadata(db_session):
    admin = Admin(username="ninesense", password_hash="unused", active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add(
        AdminSession(
            id_hash="e" * 64,
            public_id="f" * 32,
            admin_id=admin.id,
            csrf_hash="0" * 64,
            client_label="Chrome / Windows",
            expires_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    listed = list_admin_sessions(db_session, "ninesense")
    assert listed == [
        {
            "public_id": "f" * 32,
            "client_label": "Chrome / Windows",
            "expires_at": listed[0]["expires_at"],
        }
    ]
    assert "id_hash" not in listed[0]
    assert revoke_admin_sessions(db_session, "ninesense") == 1
    assert db_session.scalars(select(AdminSession)).all() == []
