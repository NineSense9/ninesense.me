# Persistent Administrator Session Implementation Plan

**Goal:** Keep a successfully verified administrator signed in on the same browser for 30 days while preserving password, TOTP, CSRF, logout, session revocation, and server-side expiry checks.

**Architecture:** Reuse the existing server-side `admin_sessions` row and HttpOnly session cookie as the trusted-browser credential. Change only the default lifetime from 8 hours to 720 hours and verify that the database expiry and cookie `Max-Age` agree; no new table, bypass token, or MFA weakening is introduced.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic Settings, pytest, Nginx/systemd deployment.

---

### Task 1: Lock the 30-day session contract

**Files:**
- Modify: `server/tests/test_admin_security.py`

- [x] Add a test that completes TOTP setup and asserts the stored session expires 30 days after creation.
- [x] Assert the response cookie has `Max-Age=2592000`, remains `HttpOnly`, and uses `SameSite=strict`.
- [x] Run the focused test and confirm it fails because the current default is 8 hours.

### Task 2: Change the shared default and deployment configuration

**Files:**
- Modify: `server/src/ninesense_guestbook/config.py`
- Modify: `deploy/guestbook.env.example`
- Modify: `deploy/deploy-guestbook.sh`
- Modify: `README.md`

- [x] Change the default `session_hours` to `720`.
- [x] Set new deployment environments to `NINESENSE_SESSION_HOURS=720`.
- [x] Document that one successful TOTP login keeps the same browser signed in for 30 days unless the user logs out, revokes the session, or clears cookies.
- [x] Run focused authentication tests and confirm logout still removes the session.

### Task 3: Verify, publish, deploy, and rotate the exposed MFA secret

**Files:**
- No additional source files unless verification finds a defect.

- [x] Run Ruff, all backend tests, the admin build, release contracts, and browser tests.
- [ ] Commit and push `main`.
- [ ] Deploy through the existing backup-and-rollback script.
- [ ] Update production `NINESENSE_SESSION_HOURS` to `720` before restart.
- [ ] Reset the exposed TOTP secret and revoke old sessions/challenges/recovery codes.
- [ ] Verify the next login creates a 30-day session and the old secret no longer authenticates.
