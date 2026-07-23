# NineSense Administration Platform Implementation Roadmap

> **For agentic workers:** Execute one phase at a time in the current task. Each phase gets its own checked implementation plan, test gate, review, and deploy decision. Do not mix unfinished work from two phases in one release.

**Goal:** Deliver the complete NineSense administration platform described in `docs/specs/2026-07-23-admin-platform-design.md` without interrupting the existing public site or losing guestbook data.

**Architecture:** Keep the public site static. Store drafts and management data in FastAPI and SQLite, then publish immutable static snapshots through an atomic switch. Build the administration UI as a separate component-based application while preserving the current public pages and APIs during migration.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, SQLite WAL, React, Vite, Playwright, pytest, PowerShell release-contract tests, Nginx, systemd

---

## Delivery rules

1. Work on one feature branch per phase.
2. Start every behavior with a failing test and confirm the expected failure.
3. Keep the existing guestbook and public site usable at every commit.
4. Run the phase gate before merging or deploying.
5. Create a production-data backup and a tested rollback point before each migration.
6. Never commit production credentials, visitor data, databases, backups, logs, server addresses, local private-key names, or machine-specific paths.

## Phase 1: Administration foundation and account security

Detailed plan: `docs/plans/2026-07-23-admin-foundation-implementation-plan.md`

Deliverables:

- Component-based administration application and navigation shell
- Password challenge followed by mandatory TOTP setup/login
- One-time recovery codes
- Session list, session revocation, recent reauthentication
- Login history and append-only audit records
- In-app notification center and dashboard summary
- Existing message moderation migrated into the new shell
- Deployment and browser tests for the new administration build

Exit gate:

- Existing guestbook moderation flow passes end to end.
- Password alone never creates an authenticated session.
- TOTP, recovery code, session revocation, CSRF and reauthentication tests pass.
- The current production database upgrades and downgrades in an isolated copy.
- Desktop and tablet administration layouts have no horizontal overflow.

## Phase 2: Structured content and media library

The phase plan will map the final file structure before code changes and cover:

- Common content records and type-specific details
- Personal profile, projects, algorithms, Agent work, awards, timeline, articles, links and research
- Visual editor with Markdown import/export and conflict-safe autosave
- Search, tags, archive and SEO fields
- Protected originals, multi-size WebP generation, PDF handling and external video records
- ALT text, reference tracking, three-version image history and 30-day cleanup
- Migration of the current homepage content and assets into structured records

Exit gate:

- Every current meaningful homepage value can be represented by structured content.
- Existing assets remain available and originals are not publicly addressable.
- Draft conflict, image conversion, reference blocking and cleanup tests pass.
- Exported content can be opened as JSON, Markdown and original media without the application.

## Phase 3: Page builder and static publishing

The phase plan will cover:

- Structured page and module schemas
- Module library for hero, profile, projects, algorithms, Agent work, research, awards, timeline, articles, media, links and guestbook entry
- Add, copy, hide, delete and drag ordering
- Desktop, tablet and phone preview
- Pending-change review and publication notes
- Link, slug, media, ALT and layout publication checks
- Immutable static snapshots, atomic activation, history, structural diff and rollback
- Stable URLs and redirect records

Exit gate:

- The current homepage can be reproduced from page configuration without a visible regression.
- Stopping FastAPI does not break the published site.
- An interrupted publication leaves the old version online.
- A previous version can be restored as a new release without deleting history.

## Phase 4: Unified interaction, analytics and operations

The phase plan will cover:

- Unified guestbook, private-letter and content-comment moderation
- Per-content comment switches and a global emergency switch
- Internal notes, bulk moderation, spam state and 30-day recycle bin
- Progressive anti-abuse checks and suspicious-request CAPTCHA
- General notification queue, digest email and urgent alerts
- Cookie-free aggregate analytics and 90-day detail retention
- Service, database, job, storage, certificate and release health
- Local retention, encrypted off-site backup, open-format export and isolated restore

Exit gate:

- Contact details never appear in public APIs, pages, analytics or logs.
- Normal visitors submit without CAPTCHA and suspicious flows receive a challenge.
- Notification retry, aggregation and urgent delivery tests pass.
- A real encrypted backup restores successfully in an isolated environment.
- Full public, administration, security, privacy and deployment gates pass.

## Cross-phase file ownership

- `site/`: built public and administration release artifacts only
- `admin-app/`: administration UI source, components, routes and browser-facing API client
- `server/src/ninesense_guestbook/web/`: HTTP schemas and route adapters
- `server/src/ninesense_guestbook/services/`: business operations and external adapters
- `server/src/ninesense_guestbook/domain/`: state rules and pure domain behavior
- `server/src/ninesense_guestbook/*_models.py`: SQLAlchemy persistence models grouped by subsystem
- `server/alembic/versions/`: reversible schema migrations
- `server/tests/`: unit, API, migration, privacy and failure-path tests
- `tests/`: release contracts and browser end-to-end tests
- `deploy/`: Nginx, systemd, backup and release automation
- `docs/specs/`: approved product and architecture decisions
- `docs/plans/`: executable implementation plans and phase gates

## Design coverage matrix

| Approved design area | Implemented in |
| --- | --- |
| Static public architecture and modular backend | Phases 1 and 3 |
| Administration navigation and account security | Phase 1 |
| All content types, including research | Phase 2 |
| Visual and Markdown editing | Phase 2 |
| Structured page builder | Phase 3 |
| Protected media and image history | Phase 2 |
| Draft, preview, publication and rollback | Phase 3 |
| Guestbook, private letters and comments | Phase 4, building on Phase 1 moderation |
| Notifications | Phase 1 in-app foundation, Phase 4 email and digest expansion |
| Privacy-preserving analytics | Phase 4 |
| Audit, high-risk reauthentication and sessions | Phase 1 |
| Health, backup, export and isolated restore | Phase 4 |
| Error handling, tests and migration safety | Every phase gate |
| Public-repository boundary | Every commit and phase gate |

## Final release gate

Run from the repository root:

```powershell
server/.venv/Scripts/python -m ruff check server/src server/tests server/alembic
server/.venv/Scripts/python -W 'error::ResourceWarning' -m pytest server/tests
npm --prefix admin-app ci
npm --prefix admin-app run build
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-deploy-config.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-public-repo.ps1
npm ci
npm run test:e2e
```

Expected result: every command exits with code 0, pytest reports no failures or warnings promoted to errors, Playwright reports all tests passed, and all PowerShell contracts print `PASS`.
