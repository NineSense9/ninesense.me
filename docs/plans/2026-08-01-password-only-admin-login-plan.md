# Password-only Administrator Login Implementation Plan

**Goal:** Allow the current production administrator to log in with a password and retain the existing 30-day server-side session without MFA blocking access.

**Architecture:** Add an MFA feature flag. When disabled, the existing password endpoint creates the same hashed session and hardened cookie previously created after MFA; sensitive reauthentication requires the password only. When enabled, all existing MFA behavior remains unchanged.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic Settings, React, pytest.

---

### Task 1: Lock password-only behavior with tests

- [x] Add a failing test proving a disabled-MFA password login creates a 30-day session and no login challenge.
- [x] Add a failing test proving disabled-MFA sensitive reauthentication accepts a password without a dynamic code.
- [x] Run both tests and observe the current MFA challenge behavior fail them.

### Task 2: Implement the switch

- [x] Add `mfa_enabled` to settings and deployment defaults.
- [x] Create sessions directly after a correct password when MFA is disabled.
- [x] Make reauthentication skip the dynamic factor only when MFA is disabled.
- [x] Return the MFA state to the administration client and hide unused code inputs.
- [x] Run focused authentication and administration security tests.

### Task 3: Release and production verification

- [x] Run the complete backend, frontend, static, deployment and browser test gate.
- [ ] Commit, push and deploy with a database/environment backup.
- [ ] Set production `NINESENSE_MFA_ENABLED=false`, verify direct login behavior, and confirm MFA secrets remain absent.
