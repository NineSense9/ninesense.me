from datetime import datetime, timezone
import time

from argon2 import PasswordHasher

from ninesense_guestbook.models import Admin
from ninesense_guestbook.services.mfa import totp_at


PASSWORD = "A-secure-test-password-2026"


def create_totp_admin(db, app, username: str = "ninesense") -> tuple[Admin, str]:
    secret = "JBSWY3DPEHPK3PXP"
    encrypted = app.state.security_cipher.encrypt(secret)
    admin = Admin(
        username=username,
        password_hash=PasswordHasher().hash(PASSWORD),
        active=True,
        totp_secret_nonce=encrypted.nonce,
        totp_secret_ciphertext=encrypted.ciphertext,
        totp_secret_key_version=encrypted.key_version,
        totp_enabled_at=datetime.now(timezone.utc),
    )
    db.add(admin)
    db.commit()
    return admin, secret


def login_with_totp(client, secret: str, username: str = "ninesense"):
    challenge = client.post(
        "/api/admin/session",
        json={"username": username, "password": PASSWORD},
    )
    assert challenge.status_code == 202
    return client.post(
        "/api/admin/session/mfa",
        json={
            "challenge_token": challenge.json()["challenge_token"],
            "code": totp_at(secret, time.time()),
        },
    )
