# NineSense Administration Foundation Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current task. Use the checkboxes as the source of truth, follow TDD for every behavior, review the diff after every task, and stop at the deployment checkpoint before changing production.

**Goal:** Replace the single-purpose administration page with a secure administration foundation that supports mandatory TOTP, recovery codes, session control, auditing, notifications, a dashboard, and the existing guestbook moderation workflow.

**Architecture:** Keep FastAPI as a modular monolith and SQLite as the database. Add security and administration tables through one reversible Alembic migration, expose narrowly scoped administration APIs, and build a React/Vite administration application in isolation before Task 11 switches it into `site/admin/`. Existing public and moderation APIs remain compatible throughout the phase.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2, Alembic, SQLite WAL, Argon2, Python standard-library TOTP/HMAC, existing authenticated encryption service, React, React Router, Vite, QRCode, pytest, Playwright

---

## Locked file structure

### Create

- `admin-app/`: Vite source, routes, components, API client, auth state and styles
- `server/src/ninesense_guestbook/admin_models.py`: challenge, recovery, audit and notification models
- `server/src/ninesense_guestbook/services/mfa.py`: TOTP and recovery-code primitives
- `server/src/ninesense_guestbook/services/audit.py`: allowlisted audit writes
- `server/src/ninesense_guestbook/services/admin_notifications.py`: in-app notification operations
- `server/src/ninesense_guestbook/web/admin_security.py`: MFA, sessions and security APIs
- `server/src/ninesense_guestbook/web/admin_dashboard.py`: dashboard, audit and notification APIs
- `server/alembic/versions/0002_admin_foundation.py`: reversible foundation migration
- `server/tests/test_admin_foundation_models.py`: model and relationship tests
- `server/tests/test_mfa.py`: RFC vector, drift and recovery-code tests
- `server/tests/test_admin_security.py`: password challenge, MFA, recovery and sessions
- `server/tests/test_audit.py`: audit allowlist and event tests
- `server/tests/test_admin_notifications.py`: notification and dashboard tests
- `server/tests/test_migrations.py`: upgrade/downgrade tests
- `tests/admin-foundation-e2e.spec.js`: browser login, setup, session and inbox test

### Modify

- `package.json`, `playwright.config.js`: administration build and browser suites
- `site/admin/`: existing release until the Task 11 cutover
- `server/src/ninesense_guestbook/models.py`: extend `Admin` and `AdminSession`
- `server/src/ninesense_guestbook/config.py`, `app.py`: security key, cipher and routers
- `server/src/ninesense_guestbook/cli.py`: bootstrap and MFA recovery commands
- `server/src/ninesense_guestbook/web/auth.py`: two-stage login
- `server/src/ninesense_guestbook/services/sessions.py`: metadata, listing and revocation
- `server/alembic/env.py`: administration metadata discovery
- `server/tests/conftest.py` and current auth/security tests
- `tests/e2e_server.py`, `tests/guestbook-e2e.spec.js`: MFA-aware E2E flow
- `tests/test-admin-build.ps1`, `tests/test-static-release.ps1`, `tests/test-deploy-config.ps1`: isolated build and release contracts
- `deploy/guestbook.env.example`, `deploy/deploy-guestbook.sh`: key and build safeguards
- `README.md`: local build, MFA bootstrap and recovery

## Task 1: Freeze the baseline and add the administration build contract

**Files:**

- Create: `admin-app/package.json`
- Create: `admin-app/vite.config.js`
- Create: `admin-app/index.html`
- Create: `admin-app/src/main.jsx`
- Create: `admin-app/src/App.jsx`
- Create: `admin-app/src/styles/tokens.css`
- Create: `admin-app/src/styles/app.css`
- Create: `tests/test-admin-build.ps1`
- Modify: `package.json`
- Modify: `.gitignore`

- [x] **Step 1: Run the untouched baseline**

```powershell
server/.venv/Scripts/python -m ruff check server/src server/tests server/alembic
server/.venv/Scripts/python -W 'error::ResourceWarning' -m pytest server/tests
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-deploy-config.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-public-repo.ps1
npm run test:e2e
```

Expected: all commands exit 0. Record pytest and Playwright counts before changing files.

- [x] **Step 2: Write the failing Vite release contract**

Create `tests/test-admin-build.ps1` so the incomplete application can be verified without replacing the working `site/admin/` release:

```powershell
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root 'admin-app/dist'
$adminIndexPath = Join-Path $dist 'index.html'
$adminManifestPath = Join-Path $dist '.vite/manifest.json'
if (-not (Test-Path $adminIndexPath)) { throw 'Admin index missing' }
if (-not (Test-Path $adminManifestPath)) { throw 'Admin Vite manifest missing' }
$manifest = Get-Content -Raw -Encoding UTF8 $adminManifestPath | ConvertFrom-Json
$entry = @($manifest.PSObject.Properties.Value | Where-Object { $_.isEntry -and $_.src -eq 'index.html' }) | Select-Object -First 1
if (-not $entry -or -not $entry.isEntry) { throw 'Admin entry missing from manifest' }
if (-not (Test-Path (Join-Path $dist $entry.file))) {
  throw 'Admin JavaScript artifact missing'
}
foreach ($cssFile in @($entry.css)) {
  if (-not (Test-Path (Join-Path $dist $cssFile))) {
    throw "Admin CSS artifact missing: $cssFile"
  }
}
```

- [x] **Step 3: Confirm the expected failure**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-admin-build.ps1
```

Expected: FAIL with `Admin build index missing`.

- [x] **Step 4: Create the Vite application**

```powershell
npm init -y --prefix admin-app
npm install --prefix admin-app react react-dom react-router-dom qrcode
npm install --prefix admin-app --save-dev vite @vitejs/plugin-react
```

Set scripts in `admin-app/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

Use this Vite configuration:

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  base: "/admin/",
  plugins: [react()],
  build: {
    outDir: resolve(import.meta.dirname, "./dist"),
    emptyOutDir: true,
    manifest: true
  }
});
```

Use this bootstrap:

```jsx
// admin-app/src/main.jsx
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./styles/tokens.css";
import "./styles/app.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter basename="/admin"><App /></BrowserRouter>
  </React.StrictMode>
);
```

```jsx
// admin-app/src/App.jsx
export default function App() {
  return <main className="bootstrap-screen"><p>NINESENSE / PRIVATE CONSOLE</p><h1>管理平台正在初始化</h1></main>;
}
```

- [x] **Step 5: Build and pass the release contract**

Add `"build:admin": "npm --prefix admin-app run build"` to root scripts, then run:

```powershell
npm --prefix admin-app run build
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-admin-build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
```

Expected: both commands exit 0.

- [x] **Step 6: Commit**

```powershell
git add .gitignore package.json admin-app tests/test-admin-build.ps1 docs/plans/2026-07-23-admin-foundation-implementation-plan.md
git commit -m "build: add administration application pipeline"
```

## Task 2: Add the administration schema and reversible migration

**Files:**

- Create: `server/src/ninesense_guestbook/admin_models.py`
- Create: `server/alembic/versions/0002_admin_foundation.py`
- Create: `server/tests/test_admin_foundation_models.py`
- Create: `server/tests/test_migrations.py`
- Modify: `server/src/ninesense_guestbook/models.py`
- Modify: `server/alembic/env.py`
- Modify: `server/tests/conftest.py`

- [x] **Step 1: Write the failing model test**

```python
from datetime import datetime, timezone
from sqlalchemy import select
from ninesense_guestbook.admin_models import AdminNotification, AuditEvent
from ninesense_guestbook.models import Admin, AdminSession


def test_admin_foundation_rows_persist(db_session):
    admin = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add_all([
        AdminSession(
            id_hash="a" * 64,
            public_id="b" * 32,
            admin_id=admin.id,
            csrf_hash="c" * 64,
            client_label="Chrome / Windows",
            created_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        ),
        AuditEvent(admin_id=admin.id, action="session.login", outcome="success"),
        AdminNotification(severity="info", category="security", title="新会话", message="Chrome / Windows"),
    ])
    db_session.commit()
    assert db_session.scalar(select(AdminSession.public_id)) == "b" * 32
    assert db_session.scalar(select(AuditEvent.action)) == "session.login"
    assert db_session.scalar(select(AdminNotification.title)) == "新会话"
```

- [x] **Step 2: Confirm the import failure**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_admin_foundation_models.py -q
```

Expected: FAIL because `admin_models` does not exist.

- [x] **Step 3: Add exact model fields**

Extend `Admin`:

```python
totp_secret_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
totp_secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
totp_secret_key_version: Mapped[int | None] = mapped_column(Integer)
totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Extend `AdminSession`:

```python
public_id: Mapped[str] = mapped_column(String(32), unique=True, default=lambda: uuid4().hex)
client_label: Mapped[str] = mapped_column(String(80), default="Unknown device")
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
last_reauthenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Create `admin_models.py` with:

```python
class AdminLoginChallenge(Base):
    __tablename__ = "admin_login_challenges"
    id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(16))
    secret_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    secret_key_version: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AdminRecoveryCode(Base):
    __tablename__ = "admin_recovery_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    outcome: Mapped[str] = mapped_column(String(16))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AdminNotification(Base):
    __tablename__ = "admin_notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [x] **Step 4: Add migration and round-trip test**

Revision `0002_admin_foundation` uses `down_revision = "0001_guestbook"`. Upgrade deletes existing sessions to force a fresh login, adds the fields above, creates the four tables and indexes, and adds a unique index for `admin_sessions.public_id`. Downgrade removes them with Alembic batch operations.

```python
def test_admin_foundation_migration_round_trip(tmp_path, monkeypatch):
    database = tmp_path / "migration.sqlite3"
    monkeypatch.setenv("NINESENSE_DATABASE_URL", f"sqlite:///{database}")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(f"sqlite:///{database}")).get_table_names())
    assert {"admin_login_challenges", "admin_recovery_codes", "audit_events", "admin_notifications"} <= tables
    command.downgrade(config, "0001_guestbook")
    tables = set(inspect(create_engine(f"sqlite:///{database}")).get_table_names())
    assert "audit_events" not in tables
```

- [x] **Step 5: Import metadata and pass tests**

Import `admin_models` in `server/alembic/env.py` and `server/tests/conftest.py`, then run:

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_admin_foundation_models.py server/tests/test_migrations.py -q
```

Expected: PASS.

- [x] **Step 6: Commit**

```powershell
git add server/src/ninesense_guestbook/models.py server/src/ninesense_guestbook/admin_models.py server/alembic server/tests/test_admin_foundation_models.py server/tests/test_migrations.py server/tests/conftest.py
git commit -m "feat: add administration foundation schema"
```

## Task 3: Implement TOTP and recovery-code primitives

**Files:**

- Create: `server/src/ninesense_guestbook/services/mfa.py`
- Create: `server/tests/test_mfa.py`

- [x] **Step 1: Write RFC and recovery-code tests**

```python
from ninesense_guestbook.services.mfa import generate_recovery_codes, hash_recovery_code, totp_at, verify_totp


def test_totp_matches_rfc6238_sha1_vector():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp_at(secret, 59, digits=8) == "94287082"


def test_totp_accepts_one_step_clock_drift_only():
    secret = "JBSWY3DPEHPK3PXP"
    code = totp_at(secret, 1_800_000_000)
    assert verify_totp(secret, code, 1_800_000_030)
    assert not verify_totp(secret, code, 1_800_000_090)


def test_recovery_codes_are_unique_and_only_hashes_persist():
    codes = generate_recovery_codes()
    assert len(codes) == len(set(codes)) == 10
    assert all(len(code.replace("-", "")) == 16 for code in codes)
    assert hash_recovery_code(codes[0], "pepper") != codes[0]
```

- [x] **Step 2: Confirm failure**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_mfa.py -q
```

Expected: FAIL because `services.mfa` does not exist.

- [x] **Step 3: Implement the pure service**

Implement the complete pure service:

```python
import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote, urlencode


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    normalized = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized + padding, casefold=True)


def totp_at(
    secret: str,
    unix_time: int | float,
    digits: int = 6,
    period: int = 30,
) -> str:
    if digits not in {6, 8} or period <= 0:
        raise ValueError("invalid TOTP parameters")
    counter = int(unix_time) // period
    digest = hmac.new(
        _decode_secret(secret),
        struct.pack(">Q", counter),
        hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**digits)).zfill(digits)


def verify_totp(
    secret: str,
    code: str,
    unix_time: int | float,
    window: int = 1,
) -> bool:
    normalized = code.strip()
    if len(normalized) != 6 or not normalized.isascii() or not normalized.isdigit():
        return False
    return any(
        hmac.compare_digest(totp_at(secret, unix_time + step * 30), normalized)
        for step in range(-window, window + 1)
    )


def build_otpauth_uri(
    secret: str,
    username: str,
    issuer: str = "NineSense",
) -> str:
    label = quote(f"{issuer}:{username.strip()}", safe="")
    query = urlencode({
        "secret": secret,
        "issuer": issuer,
        "algorithm": "SHA1",
        "digits": 6,
        "period": 30,
    })
    return f"otpauth://totp/{label}?{query}"


def generate_recovery_codes(count: int = 10) -> list[str]:
    if count < 1 or count > 20:
        raise ValueError("invalid recovery code count")
    codes = []
    while len(codes) < count:
        raw = secrets.token_hex(8).upper()
        code = "-".join(raw[index : index + 4] for index in range(0, 16, 4))
        if code not in codes:
            codes.append(code)
    return codes


def normalize_recovery_code(code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").upper()
    if len(normalized) != 16 or any(char not in "0123456789ABCDEF" for char in normalized):
        raise ValueError("invalid recovery code")
    return normalized


def hash_recovery_code(code: str, pepper: str) -> str:
    return hmac.new(
        pepper.encode("utf-8"),
        normalize_recovery_code(code).encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
```

- [x] **Step 4: Run and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_mfa.py -q
git add server/src/ninesense_guestbook/services/mfa.py server/tests/test_mfa.py
git commit -m "feat: add TOTP and recovery code primitives"
```

Expected: 3 tests pass and the commit succeeds.

## Task 4: Add redacted audit recording

**Files:**

- Create: `server/src/ninesense_guestbook/services/audit.py`
- Create: `server/tests/test_audit.py`

- [x] **Step 1: Write the failing allowlist test**

```python
def test_audit_accepts_allowlisted_details_and_rejects_secrets(db_session):
    record_audit(db_session, action="session.login", outcome="success", details={"client_label": "Chrome / Windows"})
    db_session.commit()
    event = db_session.scalar(select(AuditEvent))
    assert event.details_json == '{"client_label":"Chrome / Windows"}'
    with pytest.raises(ValueError, match="audit detail key"):
        record_audit(db_session, action="session.login", outcome="failure", details={"password": "secret"})
```

- [x] **Step 2: Confirm failure**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_audit.py -q
```

Expected: FAIL because `services.audit` does not exist.

- [x] **Step 3: Implement the audit boundary**

Expose `record_audit(db, *, action, outcome, admin_id=None, target_type=None, target_id=None, details=None)` and permit only:

```python
ALLOWED_DETAIL_KEYS = frozenset({"client_label", "reason_code", "changed_fields", "release_version", "record_count"})
```

Serialize compact sorted JSON. Reject unknown keys, invalid outcomes, nested objects and scalar values longer than 160 characters. `changed_fields` may be a flat list of at most 30 strings; all other values are scalar strings or integers. Add the row without committing so the business change and audit event share a transaction.

- [x] **Step 4: Run and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_audit.py -q
git add server/src/ninesense_guestbook/services/audit.py server/tests/test_audit.py
git commit -m "feat: add redacted administration audit log"
```

Expected: PASS.

## Task 5: Convert password login into a short-lived challenge

**Files:**

- Modify: `server/src/ninesense_guestbook/config.py`
- Modify: `server/src/ninesense_guestbook/app.py`
- Modify: `server/src/ninesense_guestbook/web/auth.py`
- Modify: `server/src/ninesense_guestbook/services/sessions.py`
- Modify: `server/tests/conftest.py`
- Modify: `server/tests/test_admin_auth.py`

- [x] **Step 1: Write challenge tests**

```python
def test_password_login_creates_setup_challenge_without_session(client, db_session):
    create_admin(db_session)
    response = login(client)
    assert response.status_code == 202
    assert response.json()["stage"] == "mfa_setup_required"
    assert response.json()["challenge_token"]
    assert response.json()["setup_uri"].startswith("otpauth://totp/")
    assert "set-cookie" not in response.headers
    assert db_session.scalars(select(AdminSession)).all() == []


def test_enabled_admin_receives_challenge_without_secret(client, db_session, app):
    admin = create_admin(db_session)
    encrypted = app.state.security_cipher.encrypt("JBSWY3DPEHPK3PXP")
    admin.totp_secret_nonce = encrypted.nonce
    admin.totp_secret_ciphertext = encrypted.ciphertext
    admin.totp_secret_key_version = encrypted.key_version
    admin.totp_enabled_at = datetime.now(timezone.utc)
    db_session.commit()
    body = login(client).json()
    assert body["stage"] == "mfa_required"
    assert "setup_uri" not in body
```

- [x] **Step 2: Confirm the old 200 response fails**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_admin_auth.py -q
```

Expected: FAIL because password login still creates a session.

- [x] **Step 3: Add separate encryption settings**

Add:

```python
security_key: str
login_challenge_minutes: int = 5
```

Initialize `app.state.security_cipher = ContactCipher.from_urlsafe_key(settings.security_key)`. Test settings use a distinct fixed key.

- [x] **Step 4: Implement challenge creation**

After password verification, generate a 32-byte URL-safe token and persist only its HMAC hash. Disabled TOTP creates purpose `setup`, generates and encrypts a pending TOTP secret, and returns `setup_uri`; enabled TOTP creates purpose `login` and returns no secret. Both responses use status 202:

```json
{
  "stage": "mfa_required",
  "challenge_token": "one-time raw token",
  "expires_at": "ISO-8601 UTC timestamp"
}
```

Setup uses `mfa_setup_required`. Delete expired challenges for the same admin. Audit password success/failure without username, IP, password or tokens.

Extend `LoginAttemptLimiter` with deterministic progressive lock intervals: failures 1–4 are not locked, failure 5 locks for 30 seconds, and each later failure doubles the interval up to 15 minutes. A successful password verification clears the entry. Add direct service tests with explicit timestamps so the suite does not sleep.

- [x] **Step 5: Run tests and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_admin_auth.py server/tests/test_security_regressions.py -q
git add server/src/ninesense_guestbook/config.py server/src/ninesense_guestbook/app.py server/src/ninesense_guestbook/web/auth.py server/src/ninesense_guestbook/services/sessions.py server/tests/conftest.py server/tests/test_admin_auth.py server/tests/test_security_regressions.py
git commit -m "feat: require a login challenge before admin sessions"
```

Expected: challenge tests pass; session-dependent helpers are completed in Task 6.

## Task 6: Complete MFA setup, TOTP login and recovery login

**Files:**

- Create: `server/src/ninesense_guestbook/web/admin_security.py`
- Create: `server/tests/test_admin_security.py`
- Create: `server/tests/admin_test_helpers.py`
- Modify: `server/src/ninesense_guestbook/app.py`
- Modify: `server/src/ninesense_guestbook/web/auth.py`
- Modify: `server/src/ninesense_guestbook/services/sessions.py`

- [x] **Step 1: Write failing API tests**

Create shared test helpers first:

```python
# server/tests/admin_test_helpers.py
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
```

In `test_admin_security.py`, define the setup fixture explicitly:

```python
from dataclasses import dataclass
import time
from urllib.parse import parse_qs, urlparse

from argon2 import PasswordHasher
import pytest

from ninesense_guestbook.admin_models import AdminLoginChallenge, AdminRecoveryCode
from ninesense_guestbook.models import Admin
from ninesense_guestbook.services.mfa import totp_at
from ninesense_guestbook.services.sessions import token_hash


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
```

Then add these assertions:

```python
def test_setup_code_enables_totp_and_returns_recovery_codes(client, db_session, setup_challenge):
    response = client.post("/api/admin/session/mfa", json={
        "challenge_token": setup_challenge.token,
        "code": setup_challenge.current_code,
    })
    assert response.status_code == 200
    assert len(response.json()["recovery_codes"]) == 10
    assert len(set(response.json()["recovery_codes"])) == 10
    assert response.json()["csrf_token"]
    assert "httponly" in response.headers["set-cookie"].lower()
    admin = db_session.get(Admin, setup_challenge.admin_id)
    assert admin.totp_enabled_at is not None
    assert admin.totp_secret_ciphertext is not None
    assert setup_challenge.secret not in response.text
    assert db_session.get(AdminLoginChallenge, setup_challenge.id_hash) is None
    assert len(db_session.scalars(select(AdminRecoveryCode)).all()) == 10
```

Add separate tests that assert: five wrong OTPs consume the challenge; enabled admins log in without receiving the secret; one recovery code logs in exactly once; expired and replayed challenges receive the same generic 401 response.

- [x] **Step 2: Confirm the missing route**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_admin_security.py -q
```

Expected: FAIL with 404 for `/api/admin/session/mfa`.

- [x] **Step 3: Implement the completion endpoint**

Use this request schema:

```python
class MfaCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_token: str = Field(min_length=32, max_length=200)
    code: str = Field(min_length=6, max_length=32)
```

`POST /api/admin/session/mfa` hashes and loads the challenge, rejects expired/replayed/five-attempt challenges, verifies the setup secret or enabled secret, and accepts either TOTP or one unused recovery code for ordinary login. Failure increments and commits `attempts`. Setup success stores the encrypted secret, creates 10 recovery hashes, and returns raw codes once. Recovery success sets `used_at`. Success deletes the challenge, creates the session, records audit, commits once and sets the hardened cookie.

Return this shape, omitting `recovery_codes` on ordinary login:

```json
{
  "username": "ninesense",
  "csrf_token": "raw in-memory token",
  "expires_at": "ISO-8601 UTC timestamp",
  "recovery_codes": ["ABCD-EF01-2345-6789"]
}
```

- [x] **Step 4: Run focused tests**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_mfa.py server/tests/test_admin_auth.py server/tests/test_admin_security.py -q
```

Expected: all pass.

- [x] **Step 5: Commit**

```powershell
git add server/src/ninesense_guestbook/web/admin_security.py server/src/ninesense_guestbook/web/auth.py server/src/ninesense_guestbook/services/sessions.py server/src/ninesense_guestbook/app.py server/tests/admin_test_helpers.py server/tests/test_admin_security.py server/tests/test_admin_auth.py
git commit -m "feat: add mandatory MFA and recovery login"
```

## Task 7: Add session management and recent reauthentication

**Files:**

- Modify: `server/src/ninesense_guestbook/services/sessions.py`
- Modify: `server/src/ninesense_guestbook/web/admin_security.py`
- Modify: `server/src/ninesense_guestbook/web/admin.py`
- Modify: `server/tests/test_admin_security.py`
- Modify: `server/tests/test_moderation.py`

- [x] **Step 1: Write failing session-control tests**

Add tests that verify the session list returns only `public_id`, `client_label`, `created_at`, `last_seen_at`, `expires_at`, and `current`; another session can be revoked with valid CSRF; forged CSRF fails; reauthentication requires password plus TOTP/recovery code; recent reauthentication expires after five minutes; recovery-code regeneration revokes every old code.

Use this response allowlist assertion:

```python
item = client.get("/api/admin/sessions").json()["items"][0]
assert set(item) == {"public_id", "client_label", "created_at", "last_seen_at", "expires_at", "current"}
assert "hash" not in str(item).lower()
assert "ip" not in str(item).lower()
```

- [x] **Step 2: Confirm missing endpoints**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_admin_security.py -q
```

Expected: FAIL with 404 for session-management routes.

- [x] **Step 3: Implement exact routes**

```text
GET    /api/admin/sessions
DELETE /api/admin/sessions/{public_id}
POST   /api/admin/session/reauthenticate
POST   /api/admin/mfa/recovery-codes
DELETE /api/admin/mfa
POST   /api/admin/messages/{message_id}/contact
```

All mutations require CSRF. Reauthentication verifies the current password plus TOTP or an unused recovery code and sets `last_reauthenticated_at`. Recovery regeneration and MFA disable call:

```python
def require_recent_reauthentication(current: CurrentSession, now: datetime) -> None:
    last = current.row.last_reauthenticated_at
    if last is None or as_utc(last) < as_utc(now) - timedelta(minutes=5):
        raise HTTPException(status_code=403, detail="请重新验证身份后再继续。")
```

Regeneration returns 10 raw codes once and replaces old rows transactionally. Disabling MFA clears the encrypted secret, deletes recovery codes and revokes other sessions. `require_session` refreshes `last_seen_at` at most every five minutes. Store only a derived browser/OS family label, never the raw User-Agent.

Message detail continues to return `has_contact` but no decrypted value. The dedicated contact endpoint requires CSRF and recent reauthentication, returns the contact once, and writes `message.contact_viewed` to the audit log in the same transaction. Update moderation tests to prove ordinary authenticated detail responses never contain the contact plaintext.

- [x] **Step 4: Run and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_admin_security.py server/tests/test_moderation.py server/tests/test_security_regressions.py -q
git add server/src/ninesense_guestbook/services/sessions.py server/src/ninesense_guestbook/web/admin_security.py server/src/ninesense_guestbook/web/admin.py server/tests/test_admin_security.py server/tests/test_moderation.py server/tests/test_security_regressions.py
git commit -m "feat: add admin session and reauthentication controls"
```

Expected: all tests pass and response bodies contain no hashes, IPs, secrets or raw user agents.

## Task 8: Add notifications, audit browsing and dashboard summary

**Files:**

- Create: `server/src/ninesense_guestbook/services/admin_notifications.py`
- Create: `server/src/ninesense_guestbook/web/admin_dashboard.py`
- Create: `server/tests/test_admin_notifications.py`
- Modify: `server/src/ninesense_guestbook/app.py`

- [x] **Step 1: Write failing API tests**

```python
def test_dashboard_reports_foundation_counts(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    assert login_with_totp(client, secret).status_code == 200
    response = client.get("/api/admin/dashboard")
    assert response.status_code == 200
    assert set(response.json()) == {
        "pending_interactions",
        "unread_notifications",
        "active_sessions",
        "recent_security_events",
    }
```

Add tests for unread filtering and cursor pagination, CSRF on mark-read/read-all, and audit response field allowlisting.

- [x] **Step 2: Confirm 404 failures**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_admin_notifications.py -q
```

Expected: FAIL for `/api/admin/dashboard`.

- [x] **Step 3: Implement service and routes**

```text
GET   /api/admin/dashboard
GET   /api/admin/notifications?unread=true&cursor=&limit=20
PATCH /api/admin/notifications/{id}/read
POST  /api/admin/notifications/read-all
GET   /api/admin/audit?cursor=&limit=50&action=
```

Use cursor ordering `(created_at, id)`. Validate severity against `info`, `warning`, `critical`; title to 120 characters; message to 500. The audit response includes only action, outcome, target type/id, allowlisted details and timestamp.

Create security notifications for a newly authenticated device and for a progressive login lock. Deduplicate repeated lock notifications for the same short-lived limiter token and severity window; notification text contains no username, IP or raw user agent.

- [x] **Step 4: Run and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_admin_notifications.py server/tests/test_audit.py -q
git add server/src/ninesense_guestbook/services/admin_notifications.py server/src/ninesense_guestbook/web/admin_dashboard.py server/src/ninesense_guestbook/app.py server/tests/test_admin_notifications.py
git commit -m "feat: add admin dashboard notifications and audit feed"
```

Expected: PASS.

## Task 9: Build staged login and MFA setup

**Files:**

- Create: `admin-app/src/api/client.js`
- Create: `admin-app/src/auth/AuthContext.jsx`
- Create: `admin-app/src/pages/LoginPage.jsx`
- Modify: `admin-app/src/App.jsx`
- Modify: `admin-app/src/styles/app.css`
- Create: `tests/admin-foundation-e2e.spec.js`
- Modify: `playwright.config.js`
- Modify: `tests/e2e_server.py`

- [x] **Step 1: Write a failing browser setup test**

```js
test("owner enrolls MFA and receives recovery codes once", async ({ page }) => {
  await page.goto("/admin/");
  await page.getByLabel("账户").fill("ninesense");
  await page.getByLabel("密码").fill("E2E-secure-password-2026");
  await page.getByRole("button", { name: "继续" }).click();
  await expect(page.getByRole("heading", { name: "设置两步验证" })).toBeVisible();
  await expect(page.locator("canvas[aria-label='两步验证二维码']")).toBeVisible();
  const code = await page.request.get("/__e2e/current-totp").then(response => response.json());
  await page.getByLabel("动态验证码").fill(code.value);
  await page.getByRole("button", { name: "启用并登录" }).click();
  await expect(page.getByRole("heading", { name: "保存恢复码" })).toBeVisible();
  await expect(page.getByTestId("recovery-code")).toHaveCount(10);
});
```

Register `/__e2e/current-totp` only when `Settings.testing` is true. Production settings default to false and the route must be absent.

Add `testing: bool = False` to `Settings`, pass `testing=True` only in `tests/e2e_server.py`, and add an API test proving the route returns 404 with the normal test fixture.

- [x] **Step 2: Confirm failure**

```powershell
npm --prefix admin-app run build
npx playwright test tests/admin-foundation-e2e.spec.js
```

Expected: FAIL because staged login is not implemented.

- [x] **Step 3: Implement the in-memory API client**

```js
let csrfToken = "";

export function setCsrfToken(value) {
  csrfToken = value || "";
}

export async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (options.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(path, { ...options, method, headers });
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (response.status === 401) {
    setCsrfToken("");
    window.dispatchEvent(new Event("ninesense:session-expired"));
  }
  if (!response.ok) throw new Error(data?.detail || "操作没有完成，请稍后再试。");
  return data;
}
```

- [x] **Step 4: Implement the three login stages**

Keep challenge tokens and raw recovery codes in React memory only. Render QR from `setup_uri` with `qrcode.toCanvas` and show a copyable manual secret. After MFA completion, store only CSRF in module memory, clear password/code/challenge values and route to the recovery acknowledgement or dashboard. Never add registration, email reset, localStorage, sessionStorage or HTML injection.

- [x] **Step 5: Build, test and commit**

```powershell
npm --prefix admin-app run build
npx playwright test tests/admin-foundation-e2e.spec.js
git add admin-app site/admin tests/admin-foundation-e2e.spec.js playwright.config.js tests/e2e_server.py
git commit -m "feat: add staged administration MFA login"
```

Expected: setup test passes.

## Task 10: Build the administration shell, dashboard and security pages

**Files:**

- Create: `admin-app/src/layout/AdminShell.jsx`
- Create: `admin-app/src/pages/DashboardPage.jsx`
- Create: `admin-app/src/pages/SecurityPage.jsx`
- Create: `admin-app/src/pages/NotificationsPage.jsx`
- Modify: `admin-app/src/App.jsx`
- Modify: `admin-app/src/auth/AuthContext.jsx`
- Modify: `admin-app/src/styles/app.css`
- Modify: `tests/admin-foundation-e2e.spec.js`

- [x] **Step 1: Extend the failing browser test**

Assert navigation labels `总览`, `互动`, `内容`, `页面`, `媒体`, `发布`, `统计`, `运维`, `设置与安全`; dashboard counts; unread notifications; session list; session revocation; and logout. Future modules render `将在后续阶段启用` without calling nonexistent APIs.

- [x] **Step 2: Confirm route failures**

```powershell
npm --prefix admin-app run build
npx playwright test tests/admin-foundation-e2e.spec.js
```

Expected: FAIL because shell routes do not exist.

- [x] **Step 3: Implement routes**

```jsx
<Route element={<RequireSession />}>
  <Route element={<AdminShell />}>
    <Route index element={<DashboardPage />} />
    <Route path="inbox" element={<FutureModule name="互动" />} />
    <Route path="notifications" element={<NotificationsPage />} />
    <Route path="security" element={<SecurityPage />} />
    <Route path="content" element={<FutureModule name="内容" />} />
    <Route path="pages" element={<FutureModule name="页面" />} />
    <Route path="media" element={<FutureModule name="媒体" />} />
    <Route path="publishing" element={<FutureModule name="发布" />} />
    <Route path="analytics" element={<FutureModule name="统计" />} />
    <Route path="operations" element={<FutureModule name="运维" />} />
  </Route>
</Route>
```

Session restoration calls `GET /api/admin/session`, keeps rotated CSRF in memory, and shows a neutral loading screen. Security actions use confirmation dialogs; recovery regeneration and MFA disable require the reauthentication form first.

- [x] **Step 4: Verify responsive shell and commit**

```powershell
npm --prefix admin-app run build
npx playwright test tests/admin-foundation-e2e.spec.js
git add admin-app site/admin tests/admin-foundation-e2e.spec.js
git commit -m "feat: add administration dashboard and security console"
```

Expected: pass at 1440×1000 and 768×1024; dashboard, notifications, security summary and logout remain usable without overflow at 390×844.

## Task 11: Move existing moderation into the shell

**Files:**

- Create: `admin-app/src/pages/InboxPage.jsx`
- Create: `admin-app/src/components/ConfirmDialog.jsx`
- Create: `admin-app/src/components/Paginator.jsx`
- Modify: `admin-app/src/styles/app.css`
- Modify: `tests/guestbook-e2e.spec.js`
- Modify: `tests/admin-foundation-e2e.spec.js`

- [ ] **Step 1: Convert E2E selectors to accessible roles**

Keep every current behavior assertion: public approval, public reply, private handling, contact reveal, status updates, responsive widths, no page errors and no failed assets. Replace `#dashboard` and `.inbox-item` with role/name selectors.

- [ ] **Step 2: Confirm moderation failure**

```powershell
npm --prefix admin-app run build
npx playwright test tests/guestbook-e2e.spec.js
```

Expected: FAIL because the new shell has no functional inbox.

- [ ] **Step 3: Implement against existing APIs**

```text
GET    /api/admin/messages
GET    /api/admin/messages/{id}
PATCH  /api/admin/messages/{id}/status
PUT    /api/admin/messages/{id}/reply
DELETE /api/admin/messages/{id}/reply
DELETE /api/admin/messages/{id}
POST   /api/admin/outbox/{id}/retry
```

Preserve status/type/search filters, cursor pagination, contact reveal, reply editing, notification retry, status actions and destructive confirmation. Contact reveal prompts for recent reauthentication when required and calls the dedicated `POST /api/admin/messages/{id}/contact` endpoint. Render visitor content through React text nodes and never use `dangerouslySetInnerHTML`.

Replace the temporary inbox route from Task 10 with `<Route path="inbox" element={<InboxPage />} />` after the functional page is implemented.

- [ ] **Step 4: Run both browser suites and commit**

```powershell
npm --prefix admin-app run build
npx playwright test tests/guestbook-e2e.spec.js tests/admin-foundation-e2e.spec.js
git add admin-app site/admin tests/guestbook-e2e.spec.js tests/admin-foundation-e2e.spec.js
git commit -m "feat: move moderation into the administration shell"
```

Expected: both suites pass with no page errors or failed assets.

## Task 12: Harden CLI, deployment and recovery documentation

**Files:**

- Modify: `server/src/ninesense_guestbook/cli.py`
- Modify: `server/tests/test_cli.py`
- Modify: `deploy/guestbook.env.example`
- Modify: `deploy/deploy-guestbook.sh`
- Modify: `tests/test-deploy-config.ps1`
- Modify: `README.md`

- [ ] **Step 1: Write failing CLI and deployment contracts**

Require:

```text
NINESENSE_SECURITY_KEY=
security key different from contact key
site/admin/.vite/manifest.json
reset-admin-mfa command
list-admin-sessions command
revoke-admin-sessions command
```

The reset command is interactive, requires the account password twice, clears TOTP/recovery/challenges, revokes every session, and writes a notification and audit event.

- [ ] **Step 2: Confirm failures**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_cli.py -q
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-deploy-config.ps1
```

Expected: FAIL because commands and key contract are absent.

- [ ] **Step 3: Implement safeguards and documentation**

Generate `NINESENSE_SECURITY_KEY` separately in the same URL-safe 32-byte format as `CONTACT_KEY`. Reject equal keys. For an existing environment file that predates this setting, append a newly generated key with the existing owner and mode preserved before starting the upgraded service. Verify the Vite manifest before release, run Alembic, and retain the existing rollback trap. README documents local build, first MFA enrollment, recovery-code storage, session revocation, terminal-only MFA reset and the HTTPS requirement.

- [ ] **Step 4: Run and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_cli.py -q
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-deploy-config.ps1
git add server/src/ninesense_guestbook/cli.py server/tests/test_cli.py deploy tests/test-deploy-config.ps1 README.md
git commit -m "ops: secure administration bootstrap and recovery"
```

Expected: PASS.

## Task 13: Run the phase gate and stop before production

**Files:**

- Modify only files required to fix failures found by the complete gate
- Update: `docs/plans/2026-07-23-admin-foundation-implementation-plan.md`

- [ ] **Step 1: Run backend gates**

```powershell
server/.venv/Scripts/python -m ruff check server/src server/tests server/alembic
server/.venv/Scripts/python -W 'error::ResourceWarning' -m pytest server/tests
```

Expected: exit 0, no failures and no warnings promoted to errors.

- [ ] **Step 2: Rebuild from a clean administration install**

Resolve `admin-app/node_modules` and verify it is inside the repository before removal, then run:

```powershell
Remove-Item -Recurse -Force admin-app/node_modules
npm --prefix admin-app ci
npm --prefix admin-app run build
```

Expected: clean install and build exit 0.

- [ ] **Step 3: Run release, privacy and browser gates**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-deploy-config.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-public-repo.ps1
npm ci
npm run test:e2e
```

Expected: all scripts print `PASS`; Playwright reports both suites passed.

- [ ] **Step 4: Test migration on an isolated production-data copy**

Create a protected backup with the existing backup command, copy it into an isolated directory, run `alembic upgrade head`, execute API smoke checks, run `alembic downgrade 0001_guestbook`, and upgrade to head again. Compare message, admin and outbox row counts before and after. Never downgrade the live database.

- [ ] **Step 5: Review the diff**

```powershell
git status --short
git diff --check
git log --oneline --decorate -15
```

Expected: only intended phase files differ, no whitespace errors, and commits correspond to Tasks 1–12.

- [ ] **Step 6: Commit gate fixes and report the checkpoint**

If the gate required fixes, stage only those files and commit `test: complete administration foundation gate`. If no files changed, do not create an empty commit. Report exact test counts, isolated migration result, current commit and rollback commit, then request explicit approval before any production deployment.
