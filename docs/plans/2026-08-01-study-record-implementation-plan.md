# NineSense Study Record Implementation Plan

> **For implementation:** Execute this plan inline in the current goal, task by task. Use the checkboxes as the source of truth, follow TDD for every backend behavior, inspect the diff after each task, and do not use subagents. Stop before production deployment unless the user explicitly authorizes it.

**Goal:** Add a public read-only study record, a secure administration workflow, four-subject focus timing, complete long-term history, monthly statistics, and an editable postgraduate-exam timeline without changing the existing authentication or deployment architecture.

**Architecture:** Keep the public site as static HTML/CSS/JavaScript and add `/records/` plus `/records/study/`. Extend the existing FastAPI modular monolith with isolated study models, services, public read APIs and authenticated administration APIs backed by the existing SQLite database. Extend the existing React/Vite administration application with mobile-capable “today” and timer workflows plus desktop-first schedule, history, focus-record and exam-event pages.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2, Alembic, SQLite WAL, Pydantic, Python `zoneinfo`, React 19, React Router 7, Vite 8, pytest, Playwright, PowerShell release contracts, Nginx, systemd

---

## Locked File Structure

### Create

- `site/records/index.html`: low-profile “More Records” index.
- `site/records/records.css`: records-index styles shared only by `/records/`.
- `site/records/study/index.html`: public read-only study page.
- `site/records/study/study.css`: editorial responsive study-page styles.
- `site/records/study/study.js`: safe public API rendering and navigation.
- `server/src/ninesense_guestbook/study_models.py`: schedule, day, task, timer, focus-session and exam-event tables.
- `server/src/ninesense_guestbook/domain/study.py`: enums, date/subject/status rules and pure calculations.
- `server/src/ninesense_guestbook/services/study_days.py`: template selection and daily snapshot generation.
- `server/src/ninesense_guestbook/services/study_timer.py`: server-authoritative timer state machine.
- `server/src/ninesense_guestbook/services/study_stats.py`: completion, recent-history and monthly aggregations.
- `server/src/ninesense_guestbook/web/study_schemas.py`: strict public and administration request schemas.
- `server/src/ninesense_guestbook/web/study_public.py`: public GET-only study API.
- `server/src/ninesense_guestbook/web/study_admin.py`: authenticated schedule, task, timer, history, exam and export API.
- `server/alembic/versions/0003_study_record.py`: reversible study schema migration.
- `server/tests/test_study_models.py`: model constraints and registration.
- `server/tests/test_study_days.py`: schedule effectiveness and daily generation.
- `server/tests/test_study_timer.py`: timer state machine and concurrency.
- `server/tests/test_study_stats.py`: time and completion aggregations.
- `server/tests/test_study_public_api.py`: public field whitelist and 30-day boundary.
- `server/tests/test_study_admin_api.py`: authenticated CRUD, audit and complete history.
- `admin-app/src/pages/study/StudyLayout.jsx`: study sub-navigation and outlet.
- `admin-app/src/pages/study/StudyTodayPage.jsx`: mobile-first current-day workspace.
- `admin-app/src/pages/study/StudySchedulePage.jsx`: effective-date weekly template editor.
- `admin-app/src/pages/study/StudyHistoryPage.jsx`: complete historical day browser.
- `admin-app/src/pages/study/StudyFocusPage.jsx`: focus records, correction and export.
- `admin-app/src/pages/study/StudyExamPage.jsx`: exam timeline editor.
- `admin-app/src/pages/study/StudyTimerPanel.jsx`: timer controls and local reminders.
- `admin-app/src/pages/study/StudyTaskEditor.jsx`: current-day task editing.
- `admin-app/src/pages/study/studyApi.js`: study-specific API helpers.
- `admin-app/src/styles/study.css`: study administration layout and responsive rules.
- `tests/study-record-e2e.spec.js`: public and administration browser flow.

### Modify

- `site/index.html`: add the low-profile footer route to `/records/`.
- `server/src/ninesense_guestbook/app.py`: register study routers and model metadata.
- `server/alembic/env.py`: import study metadata.
- `server/tests/conftest.py`: register study models in test metadata.
- `server/tests/test_models.py`: include study tables in the metadata contract.
- `server/tests/test_migrations.py`: add 0003 upgrade/downgrade and legacy-data preservation checks.
- `server/src/ninesense_guestbook/services/audit.py`: allow only the bounded study audit detail fields that are actually needed.
- `admin-app/src/App.jsx`: add nested study routes.
- `admin-app/src/layout/AdminShell.jsx`: add the `学习管理` navigation entry.
- `admin-app/src/main.jsx`: import study styles.
- `admin-app/src/styles/app.css`: shared panel and mobile-shell adjustments only where required.
- `tests/test-static-release.ps1`: require records assets, noindex, safe rendering and breakpoints.
- `tests/test-admin-build.ps1`: require the study route in built sources.
- `tests/e2e_server.py`: register study metadata and deterministic test clock data.
- `playwright.config.js`: include the study E2E suite.
- `deploy/ninesense-nginx.conf`: serve records routes with CSP and `X-Robots-Tag`.
- `deploy/deploy-guestbook.sh`: add records and study API smoke checks.
- `tests/test-deploy-config.ps1`: verify records locations and noindex headers.
- `README.md`: document local study checks, data retention and deployment boundary.
- `docs/specs/2026-08-01-study-record-design.md`: mark the approved design as entering implementation.

## Task 1: Freeze the Baseline and Add Static Route Scaffolds

**Files:**

- Create: `site/records/index.html`
- Create: `site/records/records.css`
- Create: `site/records/study/index.html`
- Create: `site/records/study/study.css`
- Create: `site/records/study/study.js`
- Modify: `site/index.html`
- Modify: `tests/test-static-release.ps1`

- [x] **Step 1: Run and record the untouched baseline**

```powershell
server/.venv/Scripts/python -m ruff check server/src server/tests server/alembic
server/.venv/Scripts/python -W 'error::ResourceWarning' -m pytest server/tests
npm --prefix admin-app run build
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-admin-build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-deploy-config.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-public-repo.ps1
npm run test:e2e
```

Expected: every command exits with code 0. Record pytest and Playwright counts in the goal progress notes.

- [x] **Step 2: Add the failing static release contract**

Extend `$required` in `tests/test-static-release.ps1`:

```powershell
'records/index.html', 'records/records.css',
'records/study/index.html', 'records/study/study.css', 'records/study/study.js'
```

Add exact contracts:

```powershell
if ($index -notmatch 'href="\./records/"') {
  throw 'Homepage records entry missing'
}

$studyRoot = Join-Path $site 'records/study'
$study = [IO.File]::ReadAllText((Join-Path $studyRoot 'index.html'), [Text.Encoding]::UTF8)
$studyCss = [IO.File]::ReadAllText((Join-Path $studyRoot 'study.css'), [Text.Encoding]::UTF8)
$studyJs = [IO.File]::ReadAllText((Join-Path $studyRoot 'study.js'), [Text.Encoding]::UTF8)
foreach ($contract in @(
  'name="robots" content="noindex, nofollow"',
  'id="study-today"', 'id="study-overview"',
  'id="study-recent"', 'id="study-exams"',
  'aria-live="polite"'
)) {
  if ($study -notmatch [regex]::Escape($contract)) {
    throw "Study page contract missing: $contract"
  }
}
if ($studyCss -notmatch 'max-width:\s*900px') { throw 'Study tablet breakpoint missing' }
if ($studyCss -notmatch 'max-width:\s*560px') { throw 'Study mobile breakpoint missing' }
if ($studyCss -notmatch 'prefers-reduced-motion') { throw 'Study reduced-motion rules missing' }
if ($studyJs -match '\.innerHTML|insertAdjacentHTML') { throw 'Study page must use safe DOM rendering' }
if ($studyJs -notmatch '\.textContent') { throw 'Study page textContent rendering missing' }
```

- [x] **Step 3: Verify the contract fails for the intended reason**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
```

Expected: FAIL with `Missing release files` or `Homepage records entry missing`.

- [x] **Step 4: Add minimal accessible route scaffolds**

Use this structure in `site/records/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>更多记录 · NineSense</title>
  <link rel="stylesheet" href="./records.css">
</head>
<body>
  <header><a href="../">NineSense</a><span>MORE RECORDS</span></header>
  <main>
    <a class="record-entry" href="./study/">
      <small>STUDY RECORD / 2026</small>
      <h1>备考记录</h1>
      <p>每天的计划、专注时间和考研节点。</p>
    </a>
  </main>
</body>
</html>
```

Use this semantic skeleton in `site/records/study/index.html`:

```html
<main>
  <section id="study-today" aria-labelledby="today-title">
    <h1 id="today-title">备考记录</h1>
    <p id="study-status" aria-live="polite">正在读取今天的记录</p>
  </section>
  <section id="study-overview" aria-labelledby="overview-title"><h2 id="overview-title">专注总览</h2></section>
  <section id="study-recent" aria-labelledby="recent-title"><h2 id="recent-title">最近 30 天</h2></section>
  <section id="study-exams" aria-labelledby="exam-title"><h2 id="exam-title">考研时间表</h2></section>
</main>
<script src="./study.js" defer></script>
```

In `study.js`, add only the safe initial state:

```js
const statusNode = document.getElementById("study-status");
statusNode.textContent = "学习数据接口将在后续任务接入";
```

Add a footer link in `site/index.html`:

```html
<a href="./records/">更多记录&nbsp;&nbsp;↗</a>
```

- [x] **Step 5: Pass the static contract and inspect 1440/390 widths**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
```

Expected: PASS. Open `/records/` and `/records/study/`; confirm no horizontal overflow at 1440 and 390 pixels.

- [x] **Step 6: Commit the route scaffold**

```powershell
git add site/index.html site/records tests/test-static-release.ps1
git commit -m "feat: add study record route scaffolds"
```

## Task 2: Add the Study Schema and Reversible Migration

**Files:**

- Create: `server/src/ninesense_guestbook/study_models.py`
- Create: `server/alembic/versions/0003_study_record.py`
- Create: `server/tests/test_study_models.py`
- Modify: `server/alembic/env.py`
- Modify: `server/tests/conftest.py`
- Modify: `server/tests/test_models.py`
- Modify: `server/tests/test_migrations.py`

- [x] **Step 1: Write failing metadata and constraint tests**

Create `server/tests/test_study_models.py`:

```python
from datetime import date, datetime, time, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from ninesense_guestbook.models import Admin
from ninesense_guestbook.study_models import (
    ExamEvent,
    FocusSession,
    FocusTimer,
    StudyDay,
    StudyScheduleEntry,
    StudyTask,
)


def test_study_rows_persist(db_session):
    admin = Admin(username="owner", password_hash="hash", active=True)
    day = StudyDay(study_date=date(2026, 8, 1), reflection="今天复盘")
    db_session.add_all([admin, day])
    db_session.flush()
    db_session.add_all([
        StudyScheduleEntry(
            weekday=5, task_kind="study", subject="408",
            start_time=time(8, 30), end_time=time(12),
            title="408", description="上午学习",
            effective_from=date(2026, 8, 1), position=10, active=True,
        ),
        StudyTask(
            day_id=day.id, task_kind="study", subject="408",
            start_time=time(8, 30), end_time=time(12),
            title="数据结构", description="图论复盘",
            status="planned", position=10,
        ),
        FocusTimer(
            admin_id=admin.id, subject="408", phase="focus",
            preset_kind="50_10", focus_seconds=3000, break_seconds=600,
            state="running", started_at=datetime.now(timezone.utc),
            planned_end_at=datetime.now(timezone.utc), idempotency_key="a" * 32,
        ),
        FocusSession(
            admin_id=admin.id, subject="408", planned_seconds=3000,
            started_at=datetime.now(timezone.utc), ended_at=datetime.now(timezone.utc),
            effective_seconds=1800, completion_kind="early_saved", source="manual",
        ),
        ExamEvent(
            kind="registration", title="网上报名", date_status="estimated",
            start_date=date(2026, 10, 1), description="日期待确认",
            countdown_target=False, position=10, active=True,
        ),
    ])
    db_session.commit()


def test_only_one_active_timer_per_admin(db_session):
    admin = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(admin)
    db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all([
        FocusTimer(admin_id=admin.id, subject="408", phase="focus", preset_kind="25_5", focus_seconds=1500, break_seconds=300, state="running", started_at=now, planned_end_at=now, idempotency_key="a" * 32),
        FocusTimer(admin_id=admin.id, subject="math", phase="focus", preset_kind="25_5", focus_seconds=1500, break_seconds=300, state="running", started_at=now, planned_end_at=now, idempotency_key="b" * 32),
    ])
    with pytest.raises(IntegrityError):
        db_session.commit()
```

Update `server/tests/test_models.py` to assert the six new table names.

- [x] **Step 2: Verify the model tests fail**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_models.py server/tests/test_models.py -q
```

Expected: FAIL because `study_models` does not exist.

- [x] **Step 3: Implement focused SQLAlchemy models**

Create `study_models.py` with one class per table. The critical constraints must be explicit:

```python
from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import utcnow


class FocusTimer(Base):
    __tablename__ = "focus_timers"
    __table_args__ = (
        UniqueConstraint("admin_id", name="uq_focus_timers_admin_id"),
        UniqueConstraint("idempotency_key", name="uq_focus_timers_idempotency_key"),
        CheckConstraint("((phase = 'focus' AND focus_seconds BETWEEN 60 AND 14400) OR (phase = 'break' AND focus_seconds = 0))", name="ck_focus_timer_focus_seconds"),
        CheckConstraint("break_seconds BETWEEN 0 AND 3600", name="ck_focus_timer_break_seconds"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"))
    subject: Mapped[str | None] = mapped_column(String(16))
    phase: Mapped[str] = mapped_column(String(16))
    preset_kind: Mapped[str] = mapped_column(String(16))
    focus_seconds: Mapped[int] = mapped_column(Integer)
    break_seconds: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    planned_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accumulated_pause_seconds: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
```

Define the remaining models explicitly:

```python
class StudyScheduleEntry(Base):
    __tablename__ = "study_schedule_entries"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_study_schedule_weekday"),
        CheckConstraint("end_time > start_time", name="ck_study_schedule_time_order"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, index=True)
    task_kind: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str | None] = mapped_column(String(16))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_until: Mapped[date | None] = mapped_column(Date)
    position: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StudyDay(Base):
    __tablename__ = "study_days"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    reflection: Mapped[str] = mapped_column(Text, default="")
    generated_from: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StudyTask(Base):
    __tablename__ = "study_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("study_days.id", ondelete="CASCADE"), index=True)
    task_kind: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str | None] = mapped_column(String(16))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="planned", index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FocusSession(Base):
    __tablename__ = "focus_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"), index=True)
    source_timer_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    subject: Mapped[str] = mapped_column(String(16), index=True)
    planned_seconds: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_seconds: Mapped[int] = mapped_column(Integer)
    completion_kind: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    correction_reason: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ExamEvent(Base):
    __tablename__ = "exam_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(120))
    date_status: Mapped[str] = mapped_column(String(16))
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(String(500))
    countdown_target: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
```

Add model check constraints for task kind, subject, task status, timer phase/state, focus-session source/completion kind and exam date status. Add the partial unique countdown-target index in the migration.

- [x] **Step 4: Add and test migration 0003**

Import metadata in `server/alembic/env.py` and `server/tests/conftest.py`:

```python
from ninesense_guestbook import admin_models, models, study_models  # noqa: F401
```

Create `0003_study_record.py` with `down_revision = "0002_admin_foundation"`, six table creations, indexes on dates/statuses, the one-target partial index, and a downgrade that drops them in reverse dependency order.

Extend `test_migrations.py`:

```python
def test_study_record_migration_round_trip(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'study.sqlite3'}"
    monkeypatch.setenv("NINESENSE_DATABASE_URL", database_url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    assert {"study_schedule_entries", "study_days", "study_tasks", "focus_timers", "focus_sessions", "exam_events"} <= table_names(database_url)
    command.downgrade(config, "0002_admin_foundation")
    assert "study_days" not in table_names(database_url)
```

- [x] **Step 5: Run focused schema tests**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_models.py server/tests/test_models.py server/tests/test_migrations.py -q
```

Expected: PASS.

- [x] **Step 6: Commit the schema**

```powershell
git add server/src/ninesense_guestbook/study_models.py server/alembic server/tests
git commit -m "feat: add study record schema"
```

## Task 3: Implement Daily Plan Generation and Task Rules

**Files:**

- Create: `server/src/ninesense_guestbook/domain/study.py`
- Create: `server/src/ninesense_guestbook/services/study_days.py`
- Create: `server/tests/test_study_days.py`

- [x] **Step 1: Write failing schedule-generation tests**

```python
from datetime import date, time

from sqlalchemy import select

from ninesense_guestbook.services.study_days import ensure_today, get_or_create_day
from ninesense_guestbook.study_models import StudyScheduleEntry, StudyTask


def test_ensure_today_snapshots_only_the_effective_template(db_session):
    db_session.add_all([
        StudyScheduleEntry(weekday=5, task_kind="study", subject="408", start_time=time(8, 30), end_time=time(12), title="旧计划", description="", effective_from=date(2026, 7, 1), effective_until=date(2026, 7, 31), position=10, active=True),
        StudyScheduleEntry(weekday=5, task_kind="study", subject="408", start_time=time(8, 30), end_time=time(12), title="新计划", description="数据结构", effective_from=date(2026, 8, 1), position=10, active=True),
    ])
    db_session.commit()

    day = ensure_today(db_session, date(2026, 8, 1))
    db_session.commit()
    tasks = list(db_session.scalars(select(StudyTask).where(StudyTask.day_id == day.id)))
    assert [task.title for task in tasks] == ["新计划"]


def test_generated_day_is_immutable_when_template_changes(db_session):
    entry = StudyScheduleEntry(weekday=5, task_kind="study", subject="408", start_time=time(8, 30), end_time=time(12), title="原计划", description="", effective_from=date(2026, 8, 1), position=10, active=True)
    db_session.add(entry)
    db_session.commit()
    first = ensure_today(db_session, date(2026, 8, 1))
    entry.title = "修改后的模板"
    db_session.commit()
    second = ensure_today(db_session, date(2026, 8, 1))
    assert first.id == second.id
    assert db_session.scalar(select(StudyTask.title).where(StudyTask.day_id == first.id)) == "原计划"


def test_missing_template_creates_an_empty_day_without_rollover(db_session):
    day = get_or_create_day(db_session, date(2026, 8, 2), generate_from_template=True)
    db_session.commit()
    assert day.study_date == date(2026, 8, 2)
    assert list(db_session.scalars(select(StudyTask))) == []
```

- [x] **Step 2: Verify the tests fail**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_days.py -q
```

Expected: FAIL because the service is missing.

- [x] **Step 3: Add domain enums and pure validation**

```python
# domain/study.py
from enum import StrEnum


class Subject(StrEnum):
    MATH = "math"
    CS408 = "408"
    ENGLISH = "english"
    POLITICS = "politics"


class TaskStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"


FINAL_TASK_STATUSES = frozenset({TaskStatus.COMPLETED, TaskStatus.INCOMPLETE, TaskStatus.CANCELLED})


def counts_toward_completion(task_kind: str, status: str) -> bool:
    return task_kind == "study" and status in {TaskStatus.COMPLETED, TaskStatus.INCOMPLETE}
```

- [x] **Step 4: Implement snapshot generation**

```python
# services/study_days.py
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..study_models import StudyDay, StudyScheduleEntry, StudyTask


def get_or_create_day(db: Session, study_date: date, *, generate_from_template: bool) -> StudyDay:
    existing = db.scalar(select(StudyDay).where(StudyDay.study_date == study_date))
    if existing is not None:
        return existing
    day = StudyDay(study_date=study_date, reflection="")
    db.add(day)
    db.flush()
    if generate_from_template:
        entries = list(db.scalars(
            select(StudyScheduleEntry)
            .where(
                StudyScheduleEntry.active.is_(True),
                StudyScheduleEntry.weekday == study_date.weekday(),
                StudyScheduleEntry.effective_from <= study_date,
                or_(StudyScheduleEntry.effective_until.is_(None), StudyScheduleEntry.effective_until >= study_date),
            )
            .order_by(StudyScheduleEntry.position, StudyScheduleEntry.start_time)
        ))
        for entry in entries:
            db.add(StudyTask(
                day_id=day.id, task_kind=entry.task_kind, subject=entry.subject,
                start_time=entry.start_time, end_time=entry.end_time,
                title=entry.title, description=entry.description,
                status="planned", position=entry.position,
            ))
    return day


def ensure_today(db: Session, today: date) -> StudyDay:
    return get_or_create_day(db, today, generate_from_template=True)
```

- [x] **Step 5: Add boundary tests for rest and no rollover**

```python
def test_rest_template_generates_a_subjectless_rest_task(db_session):
    db_session.add(StudyScheduleEntry(weekday=5, task_kind="rest", subject=None, start_time=time(14), end_time=time(17, 30), title="下午休息", description="", effective_from=date(2026, 8, 1), position=20, active=True))
    db_session.commit()
    day = ensure_today(db_session, date(2026, 8, 1))
    db_session.commit()
    task = db_session.scalar(select(StudyTask).where(StudyTask.day_id == day.id))
    assert task.task_kind == "rest"
    assert task.subject is None


def test_incomplete_task_does_not_roll_into_tomorrow(db_session):
    first = get_or_create_day(db_session, date(2026, 8, 1), generate_from_template=False)
    db_session.add(StudyTask(day_id=first.id, task_kind="study", subject="408", start_time=time(8, 30), end_time=time(12), title="未完成任务", description="", status="incomplete", position=10))
    db_session.commit()
    second = get_or_create_day(db_session, date(2026, 8, 2), generate_from_template=False)
    db_session.commit()
    assert list(db_session.scalars(select(StudyTask).where(StudyTask.day_id == second.id))) == []


def test_admin_can_create_a_past_blank_day_without_current_template(db_session):
    day = get_or_create_day(db_session, date(2025, 1, 5), generate_from_template=False)
    db_session.commit()
    assert day.study_date == date(2025, 1, 5)
    assert list(db_session.scalars(select(StudyTask).where(StudyTask.day_id == day.id))) == []
```

- [x] **Step 6: Run and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_days.py -q
server/.venv/Scripts/python -m ruff check server/src/ninesense_guestbook/domain server/src/ninesense_guestbook/services/study_days.py server/tests/test_study_days.py
git add server/src/ninesense_guestbook/domain/study.py server/src/ninesense_guestbook/services/study_days.py server/tests/test_study_days.py
git commit -m "feat: generate daily study plans"
```

## Task 4: Implement the Server-Authoritative Focus Timer

**Files:**

- Create: `server/src/ninesense_guestbook/services/study_timer.py`
- Create: `server/tests/test_study_timer.py`

- [x] **Step 1: Write failing timer-state tests**

```python
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from ninesense_guestbook.services.study_timer import (
    discard_timer,
    finish_timer,
    pause_timer,
    reconcile_timer,
    resume_timer,
    start_break_timer,
    start_timer,
)
from ninesense_guestbook.models import Admin
from ninesense_guestbook.study_models import FocusSession, FocusTimer


NOW = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def admin(db_session):
    row = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(row)
    db_session.commit()
    return row


def test_timer_continues_without_browser_and_completes_once(db_session, admin):
    timer = start_timer(db_session, admin.id, "408", "25_5", 1500, 300, "a" * 32, NOW)
    db_session.commit()
    reconcile_timer(db_session, admin.id, NOW + timedelta(minutes=26))
    db_session.commit()
    reconcile_timer(db_session, admin.id, NOW + timedelta(minutes=27))
    db_session.commit()
    assert db_session.scalar(select(FocusTimer)) is None
    assert len(list(db_session.scalars(select(FocusSession)))) == 1


def test_pause_extends_planned_end_and_excludes_paused_time(db_session, admin):
    timer = start_timer(db_session, admin.id, "math", "50_10", 3000, 600, "b" * 32, NOW)
    pause_timer(db_session, timer, NOW + timedelta(minutes=10))
    resume_timer(db_session, timer, NOW + timedelta(minutes=15))
    assert timer.accumulated_pause_seconds == 300
    assert timer.planned_end_at == NOW + timedelta(minutes=55)


def test_early_finish_can_save_or_discard(db_session, admin):
    saved = start_timer(db_session, admin.id, "english", "custom", 2400, 0, "c" * 32, NOW)
    session = finish_timer(db_session, saved, save=True, now=NOW + timedelta(minutes=12))
    assert session.effective_seconds == 720
    discarded = start_timer(db_session, admin.id, "politics", "custom", 1200, 0, "d" * 32, NOW)
    assert discard_timer(db_session, discarded) is None


def test_second_active_timer_is_rejected(db_session, admin):
    start_timer(db_session, admin.id, "408", "25_5", 1500, 300, "e" * 32, NOW)
    with pytest.raises(HTTPException) as error:
        start_timer(db_session, admin.id, "math", "25_5", 1500, 300, "f" * 32, NOW)
    assert error.value.status_code == 409
```

Add an `admin` fixture to `test_study_timer.py` that inserts one active `Admin`.

- [x] **Step 2: Verify the timer tests fail**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_timer.py -q
```

- [x] **Step 3: Implement start, pause and resume**

```python
def start_timer(db, admin_id, subject, preset_kind, focus_seconds, break_seconds, idempotency_key, now):
    existing = db.scalar(select(FocusTimer).where(FocusTimer.admin_id == admin_id))
    if existing is not None:
        if existing.idempotency_key == idempotency_key:
            return existing
        raise HTTPException(status_code=409, detail="已有正在运行的计时器")
    timer = FocusTimer(
        admin_id=admin_id, subject=subject, phase="focus", preset_kind=preset_kind,
        focus_seconds=focus_seconds, break_seconds=break_seconds, state="running",
        started_at=now, planned_end_at=now + timedelta(seconds=focus_seconds),
        idempotency_key=idempotency_key,
    )
    db.add(timer)
    db.flush()
    return timer


def pause_timer(db, timer, now):
    if timer.state != "running":
        raise HTTPException(status_code=409, detail="计时器当前不能暂停")
    timer.state = "paused"
    timer.paused_at = now
    return timer


def resume_timer(db, timer, now):
    if timer.state != "paused" or timer.paused_at is None:
        raise HTTPException(status_code=409, detail="计时器当前不能恢复")
    paused_seconds = max(0, int((now - as_utc(timer.paused_at)).total_seconds()))
    timer.accumulated_pause_seconds += paused_seconds
    timer.planned_end_at = as_utc(timer.planned_end_at) + timedelta(seconds=paused_seconds)
    timer.paused_at = None
    timer.state = "running"
    return timer
```

- [x] **Step 4: Implement exactly-once reconciliation and early finish**

`reconcile_timer` must lock the row through the current transaction, create a `FocusSession` with `source_timer_id=timer.id`, flush it, and delete the timer. Catch a unique-session race by rolling back and returning the existing session.

```python
def effective_seconds(timer, now):
    end = min(as_utc(now), as_utc(timer.planned_end_at))
    elapsed = int((end - as_utc(timer.started_at)).total_seconds())
    if timer.state == "paused" and timer.paused_at is not None:
        elapsed -= int((end - as_utc(timer.paused_at)).total_seconds())
    return max(0, min(timer.focus_seconds, elapsed - timer.accumulated_pause_seconds))
```

Break timers use `phase="break"`, have `subject=None`, never create `FocusSession`, and delete themselves when due.

```python
def start_break_timer(db, admin_id, break_seconds, idempotency_key, now):
    existing = db.scalar(select(FocusTimer).where(FocusTimer.admin_id == admin_id))
    if existing is not None:
        if existing.idempotency_key == idempotency_key:
            return existing
        raise HTTPException(status_code=409, detail="已有正在运行的计时器")
    timer = FocusTimer(
        admin_id=admin_id, subject=None, phase="break", preset_kind="break",
        focus_seconds=0, break_seconds=break_seconds, state="running",
        started_at=now, planned_end_at=now + timedelta(seconds=break_seconds),
        idempotency_key=idempotency_key,
    )
    db.add(timer)
    db.flush()
    return timer
```

- [x] **Step 5: Add tests for duplicate idempotency, break phase and UTC-naive SQLite reads**

Expected assertions:

```python
first = start_timer(db_session, admin.id, "408", "25_5", 1500, 300, "same-key-value-000000000000000", NOW)
duplicate = start_timer(db_session, admin.id, "408", "25_5", 1500, 300, "same-key-value-000000000000000", NOW + timedelta(seconds=1))
assert duplicate.id == first.id
break_timer = start_break_timer(db_session, admin.id, 300, "break-key-value-00000000000000", NOW)
assert reconcile_timer(db_session, admin.id, NOW + timedelta(minutes=6)) is None
assert db_session.get(FocusTimer, break_timer.id) is None
assert as_utc(timer.started_at).tzinfo is not None
```

- [x] **Step 6: Run and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_timer.py -q
server/.venv/Scripts/python -m ruff check server/src/ninesense_guestbook/services/study_timer.py server/tests/test_study_timer.py
git add server/src/ninesense_guestbook/services/study_timer.py server/tests/test_study_timer.py
git commit -m "feat: add persistent focus timer"
```

## Task 5: Implement Statistics and Complete History Queries

**Files:**

- Create: `server/src/ninesense_guestbook/services/study_stats.py`
- Create: `server/tests/test_study_stats.py`

- [ ] **Step 1: Write failing aggregation tests**

```python
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from ninesense_guestbook.models import Admin
from ninesense_guestbook.study_models import FocusSession, StudyDay

from ninesense_guestbook.services.study_stats import admin_history, completion_summary, month_summary, public_recent_days


def test_completion_excludes_rest_cancelled_and_open_tasks():
    tasks = [
        SimpleNamespace(task_kind="study", status="completed"),
        SimpleNamespace(task_kind="study", status="incomplete"),
        SimpleNamespace(task_kind="study", status="planned"),
        SimpleNamespace(task_kind="study", status="cancelled"),
        SimpleNamespace(task_kind="rest", status="planned"),
    ]
    summary = completion_summary(tasks)
    assert summary == {"completed": 1, "closed": 2, "rate": 0.5}


def test_month_summary_uses_effective_seconds_and_subjects(db_session):
    admin = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add_all([
        FocusSession(admin_id=admin.id, subject="408", planned_seconds=3600, started_at=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc), ended_at=datetime(2026, 8, 1, 1, 0, tzinfo=timezone.utc), effective_seconds=3600, completion_kind="completed", source="timer"),
        FocusSession(admin_id=admin.id, subject="math", planned_seconds=3600, started_at=datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc), ended_at=datetime(2026, 8, 2, 1, 0, tzinfo=timezone.utc), effective_seconds=3600, completion_kind="completed", source="manual", correction_reason="补录"),
    ])
    db_session.commit()
    result = month_summary(db_session, "2026-08")
    assert result["total_seconds"] == 7200
    assert result["subjects"]["408"] == 3600
    assert result["subjects"]["math"] == 3600
    assert result["subjects"]["politics"] == 0


def test_public_recent_is_capped_at_thirty_days(db_session):
    db_session.add_all([StudyDay(study_date=date(2026, 8, 1) - timedelta(days=offset), reflection=str(offset)) for offset in range(45)])
    db_session.commit()
    rows = public_recent_days(db_session, date(2026, 8, 1), requested_days=90)
    assert len(rows) <= 30
    assert min(row.study_date for row in rows) >= date(2026, 7, 3)


def test_admin_history_has_no_thirty_day_cap(db_session):
    db_session.add_all([StudyDay(study_date=date(2025, 1, 1), reflection="旧记录"), StudyDay(study_date=date(2026, 8, 1), reflection="新记录")])
    db_session.commit()
    rows = admin_history(db_session, date(2025, 1, 1), date(2026, 8, 1))
    assert any(row.study_date.year == 2025 for row in rows)
```

- [ ] **Step 2: Verify the tests fail**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_stats.py -q
```

- [ ] **Step 3: Implement pure completion and date-range helpers**

```python
def completion_summary(tasks):
    closed = [task for task in tasks if task.task_kind == "study" and task.status in {"completed", "incomplete"}]
    completed = sum(task.status == "completed" for task in closed)
    return {
        "completed": completed,
        "closed": len(closed),
        "rate": completed / len(closed) if closed else None,
    }


def recent_window(today, requested_days):
    days = max(1, min(requested_days, 30))
    return today - timedelta(days=days - 1), today
```

- [ ] **Step 4: Implement monthly SQL aggregation**

Use Shanghai natural-month boundaries converted to UTC before querying `FocusSession.started_at`. Return all four subjects, even when zero:

```python
SUBJECTS = ("math", "408", "english", "politics")

def month_summary(db, month_text):
    start_local = datetime.strptime(month_text + "-01", "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    next_local = (start_local.replace(day=28) + timedelta(days=4)).replace(day=1)
    rows = db.execute(
        select(FocusSession.subject, func.sum(FocusSession.effective_seconds))
        .where(FocusSession.started_at >= start_local.astimezone(timezone.utc), FocusSession.started_at < next_local.astimezone(timezone.utc))
        .group_by(FocusSession.subject)
    ).all()
    values = {subject: 0 for subject in SUBJECTS}
    values.update({subject: int(total or 0) for subject, total in rows})
    return {"month": month_text, "total_seconds": sum(values.values()), "subjects": values}
```

Extend the function with daily trend and completion data using the same local boundaries:

```python
    sessions = list(db.scalars(select(FocusSession).where(FocusSession.started_at >= start_local.astimezone(timezone.utc), FocusSession.started_at < next_local.astimezone(timezone.utc))))
    daily = {}
    for session in sessions:
        key = as_utc(session.started_at).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
        daily[key] = daily.get(key, 0) + session.effective_seconds
    tasks = list(db.scalars(
        select(StudyTask)
        .join(StudyDay, StudyTask.day_id == StudyDay.id)
        .where(StudyDay.study_date >= start_local.date(), StudyDay.study_date < next_local.date())
    ))
    completion = completion_summary(tasks)
    return {
        "month": month_text,
        "total_seconds": sum(values.values()),
        "subjects": values,
        "daily": [{"date": key, "seconds": daily[key]} for key in sorted(daily)],
        "completion": completion,
    }
```

- [ ] **Step 5: Run and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_stats.py -q
git add server/src/ninesense_guestbook/services/study_stats.py server/tests/test_study_stats.py
git commit -m "feat: aggregate study history"
```

## Task 6: Add the Public Read-Only Study API

**Files:**

- Create: `server/src/ninesense_guestbook/web/study_schemas.py`
- Create: `server/src/ninesense_guestbook/web/study_public.py`
- Create: `server/tests/test_study_public_api.py`
- Modify: `server/src/ninesense_guestbook/app.py`

- [ ] **Step 1: Write failing public API tests**

```python
from datetime import date, datetime, time, timedelta, timezone

from ninesense_guestbook.models import Admin
from ninesense_guestbook.study_models import FocusTimer, StudyDay, StudyScheduleEntry


def test_public_today_generates_only_today_and_whitelists_timer(client, db_session):
    admin = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add(StudyScheduleEntry(weekday=5, task_kind="study", subject="408", start_time=time(8, 30), end_time=time(12), title="408", description="数据结构", effective_from=date(2026, 8, 1), position=10, active=True))
    now = datetime.now(timezone.utc)
    db_session.add(FocusTimer(admin_id=admin.id, subject="408", phase="focus", preset_kind="25_5", focus_seconds=1500, break_seconds=300, state="running", started_at=now, planned_end_at=now + timedelta(minutes=25), idempotency_key="a" * 32))
    db_session.commit()
    response = client.get("/api/study/today")
    assert response.status_code == 200
    payload = response.json()
    assert payload["active_subject"] == "408"
    assert "started_at" not in payload
    assert "planned_end_at" not in payload
    assert set(payload["tasks"][0]) == {"id", "kind", "subject", "start_time", "end_time", "title", "description", "status"}


def test_public_recent_rejects_more_than_thirty_days(client):
    response = client.get("/api/study/recent?days=31")
    assert response.status_code == 422


def test_public_routes_have_no_write_methods(client):
    assert client.post("/api/study/today", json={}).status_code == 405
    assert client.patch("/api/study/today", json={}).status_code == 405


def test_public_month_does_not_return_reflection_or_task_body(client, db_session):
    db_session.add(StudyDay(study_date=date(2025, 1, 1), reflection="完整旧复盘"))
    db_session.commit()
    payload = client.get("/api/study/months/2025-01").json()
    assert "reflection" not in payload
    assert "tasks" not in payload
```

- [ ] **Step 2: Verify the API tests fail**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_public_api.py -q
```

- [ ] **Step 3: Define strict response schemas**

```python
class PublicStudyTask(BaseModel):
    id: int
    kind: Literal["study", "rest"]
    subject: Literal["math", "408", "english", "politics"] | None
    start_time: str
    end_time: str
    title: str
    description: str
    status: Literal["planned", "in_progress", "completed", "incomplete", "cancelled"]


class PublicToday(BaseModel):
    date: str
    countdown_days: int | None
    countdown_target: str | None
    next_exam_event: dict[str, object] | None
    active_subject: Literal["math", "408", "english", "politics"] | None
    updated_at: str
    reflection: str
    completion: dict[str, int | float | None]
    tasks: list[PublicStudyTask]
```

Use `ConfigDict(extra="forbid")` on every request schema. Response schemas are the public field whitelist.

- [ ] **Step 4: Implement GET-only routes**

```python
router = APIRouter(prefix="/api/study", tags=["study-public"])


@router.get("/today", response_model=PublicToday)
def today(request: Request, response: Response):
    today_local = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    with request.app.state.session_factory() as db:
        day = ensure_today(db, today_local)
        admin_id = active_admin_id(db)
        timer = reconcile_timer(db, admin_id=admin_id, now=datetime.now(timezone.utc)) if admin_id is not None else None
        payload = build_public_today(db, day, timer, today_local)
        db.commit()
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=30"
    return payload


@router.get("/recent")
def recent(request: Request, days: int = Query(default=30, ge=1, le=30)):
    today_local = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    with request.app.state.session_factory() as db:
        return build_public_recent(db, today_local, days)


@router.get("/months/{month}")
def month(request: Request, month: str = Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    with request.app.state.session_factory() as db:
        return month_summary(db, month)


@router.get("/exams")
def exams(request: Request):
    with request.app.state.session_factory() as db:
        rows = list(db.scalars(select(ExamEvent).where(ExamEvent.active.is_(True)).order_by(ExamEvent.start_date, ExamEvent.position)))
        return {"items": [public_exam_payload(row) for row in rows]}
```

Implement the helper used above:

```python
def active_admin_id(db: Session) -> int | None:
    return db.scalar(select(Admin.id).where(Admin.active.is_(True)).order_by(Admin.id).limit(1))
```

When it returns `None`, public responses use `active_subject=None`.

- [ ] **Step 5: Register the router and pass tests**

```python
from .web.study_public import router as study_public_router
app.include_router(study_public_router)
```

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_public_api.py -q
```

- [ ] **Step 6: Commit**

```powershell
git add server/src/ninesense_guestbook/app.py server/src/ninesense_guestbook/web/study_public.py server/src/ninesense_guestbook/web/study_schemas.py server/tests/test_study_public_api.py
git commit -m "feat: expose public study data"
```

## Task 7: Add Administration APIs for Plans, Tasks and Exam Events

**Files:**

- Create: `server/src/ninesense_guestbook/web/study_admin.py`
- Create: `server/tests/test_study_admin_api.py`
- Modify: `server/src/ninesense_guestbook/web/study_schemas.py`
- Modify: `server/src/ninesense_guestbook/app.py`
- Modify: `server/src/ninesense_guestbook/services/audit.py`

- [ ] **Step 1: Write failing authentication and CRUD tests**

```python
from datetime import date

import pytest

from ninesense_guestbook.admin_models import AuditEvent
from ninesense_guestbook.study_models import ExamEvent, StudyDay
from admin_test_helpers import create_totp_admin, login_with_totp


@pytest.fixture
def authenticated_client(client, app, db_session):
    _, secret = create_totp_admin(db_session, app)
    login = login_with_totp(client, secret)
    client.headers.update({"X-CSRF-Token": login.json()["csrf_token"]})
    return client


def test_study_admin_requires_session_and_csrf(client):
    assert client.get("/api/admin/study/days/2026-08-01").status_code == 401


def test_admin_creates_schedule_and_updates_today(client, app, db_session):
    admin, secret = create_totp_admin(db_session, app)
    login = login_with_totp(client, secret)
    csrf = login.json()["csrf_token"]
    created = client.post("/api/admin/study/schedule", headers={"X-CSRF-Token": csrf}, json={
        "weekday": 5, "kind": "study", "subject": "408",
        "start_time": "08:30", "end_time": "12:00",
        "title": "408", "description": "数据结构",
        "effective_from": "2026-08-01", "effective_until": None,
        "position": 10, "active": True,
    })
    assert created.status_code == 201
    day = client.get("/api/admin/study/days/2026-08-01")
    task_id = day.json()["tasks"][0]["id"]
    updated = client.patch(f"/api/admin/study/tasks/{task_id}", headers={"X-CSRF-Token": csrf}, json={"status": "completed", "title": "图论复盘"})
    assert updated.json()["status"] == "completed"


def test_admin_history_is_not_limited_to_thirty_days(authenticated_client, db_session):
    db_session.add(StudyDay(study_date=date(2025, 1, 1), reflection="旧记录"))
    db_session.commit()
    response = authenticated_client.get("/api/admin/study/history?from=2025-01-01&to=2026-08-01")
    assert any(item["date"].startswith("2025-") for item in response.json()["items"])
```

- [ ] **Step 2: Verify the tests fail**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_admin_api.py -q
```

- [ ] **Step 3: Add strict mutation schemas**

```python
class ScheduleEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weekday: int = Field(ge=0, le=6)
    kind: Literal["study", "rest"]
    subject: Literal["math", "408", "english", "politics"] | None
    start_time: time
    end_time: time
    title: str
    description: str = ""
    effective_from: date
    effective_until: date | None = None
    position: int = Field(ge=0, le=10000)
    active: bool = True

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.kind == "study" and self.subject is None:
            raise ValueError("study tasks require a subject")
        if self.kind == "rest" and self.subject is not None:
            raise ValueError("rest tasks cannot have a subject")
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("effective_until must not precede effective_from")
        return self
```

Add `TaskCreate`, `TaskUpdate`, `ReflectionUpdate`, `ExamEventInput` and date-range query validators with concrete maximum text lengths from the design.

- [ ] **Step 4: Implement schedule, day, task and exam routes**

Every mutation begins with:

```python
with request.app.state.session_factory() as db:
    current = require_session(request, db)
    require_csrf(request, current)
```

Route set:

```text
GET    /api/admin/study/schedule
POST   /api/admin/study/schedule
PATCH  /api/admin/study/schedule/{entry_id}
DELETE /api/admin/study/schedule/{entry_id}
GET    /api/admin/study/days/{study_date}
POST   /api/admin/study/days/{study_date}
PATCH  /api/admin/study/days/{study_date}/reflection
POST   /api/admin/study/days/{study_date}/tasks
PATCH  /api/admin/study/tasks/{task_id}
DELETE /api/admin/study/tasks/{task_id}
GET    /api/admin/study/history
GET    /api/admin/study/exams
POST   /api/admin/study/exams
PATCH  /api/admin/study/exams/{event_id}
DELETE /api/admin/study/exams/{event_id}
```

Use the existing audit service without placing task text or reflections in details:

```python
record_audit(
    db,
    action="study.task.updated",
    outcome="success",
    admin_id=current.admin.id,
    target_type="study_task",
    target_id=str(task.id),
    details={"changed_fields": sorted(changed_fields)},
)
```

- [ ] **Step 5: Enforce one countdown target transactionally**

When setting `countdown_target=True`, clear the flag from other events in the same transaction before flushing the target event. Add this sequential replacement test:

```python
def test_setting_countdown_target_replaces_the_previous_target(authenticated_client, db_session):
    first = authenticated_client.post("/api/admin/study/exams", json={"kind": "registration", "title": "报名", "date_status": "estimated", "start_date": "2026-10-01", "end_date": None, "description": "", "source_url": None, "countdown_target": True, "position": 10, "active": True})
    second = authenticated_client.post("/api/admin/study/exams", json={"kind": "exam", "title": "初试", "date_status": "estimated", "start_date": "2026-12-20", "end_date": None, "description": "", "source_url": None, "countdown_target": True, "position": 20, "active": True})
    assert first.status_code == 201
    assert second.status_code == 201
    targets = list(db_session.scalars(select(ExamEvent).where(ExamEvent.countdown_target.is_(True), ExamEvent.active.is_(True))))
    assert [row.id for row in targets] == [second.json()["id"]]
```

- [ ] **Step 6: Pass tests and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_admin_api.py server/tests/test_audit.py -q
git add server/src/ninesense_guestbook/app.py server/src/ninesense_guestbook/services/audit.py server/src/ninesense_guestbook/web/study_admin.py server/src/ninesense_guestbook/web/study_schemas.py server/tests/test_study_admin_api.py
git commit -m "feat: manage study plans and exams"
```

## Task 8: Add Timer, Focus History and Export Administration APIs

**Files:**

- Modify: `server/src/ninesense_guestbook/web/study_admin.py`
- Modify: `server/src/ninesense_guestbook/web/study_schemas.py`
- Modify: `server/tests/test_study_admin_api.py`

- [ ] **Step 1: Write failing timer and correction API tests**

```python
def test_timer_lifecycle_and_public_state(authenticated_client):
    started = authenticated_client.post("/api/admin/study/timer/start", json={"subject": "408", "preset": "25_5", "focus_seconds": 1500, "break_seconds": 300, "idempotency_key": "a" * 32})
    assert started.status_code == 201
    assert authenticated_client.post("/api/admin/study/timer/pause").json()["state"] == "paused"
    assert authenticated_client.post("/api/admin/study/timer/resume").json()["state"] == "running"
    finished = authenticated_client.post("/api/admin/study/timer/finish", json={"save": True})
    assert finished.json()["session"]["effective_seconds"] >= 0


def test_manual_focus_correction_is_audited(authenticated_client, db_session):
    created = authenticated_client.post("/api/admin/study/focus", json={"subject": "math", "started_at": "2026-08-01T06:00:00Z", "ended_at": "2026-08-01T07:00:00Z", "effective_seconds": 3600, "reason": "补录线下学习"})
    session_id = created.json()["id"]
    authenticated_client.patch(f"/api/admin/study/focus/{session_id}", json={"effective_seconds": 3300, "reason": "扣除中断时间"})
    actions = [row.action for row in db_session.scalars(select(AuditEvent))]
    assert "study.focus.created" in actions
    assert "study.focus.updated" in actions


def test_json_and_csv_exports_include_complete_history(authenticated_client, db_session):
    db_session.add(StudyDay(study_date=date(2025, 1, 1), reflection="长期保留"))
    db_session.commit()
    json_response = authenticated_client.get("/api/admin/study/export.json")
    assert json_response.status_code == 200
    csv_response = authenticated_client.get("/api/admin/study/focus.csv")
    assert csv_response.headers["content-type"].startswith("text/csv")
```

- [ ] **Step 2: Add timer and manual-record schemas**

```python
class TimerStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: Literal["math", "408", "english", "politics"]
    preset: Literal["25_5", "50_10", "custom"]
    focus_seconds: int = Field(ge=60, le=14400)
    break_seconds: int = Field(ge=0, le=3600)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9_-]{32,64}$")


class FocusRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: Literal["math", "408", "english", "politics"]
    started_at: datetime
    ended_at: datetime
    effective_seconds: int = Field(ge=60, le=43200)
    reason: str = Field(min_length=2, max_length=160)
```

- [ ] **Step 3: Add timer routes**

```text
GET  /api/admin/study/timer
POST /api/admin/study/timer/start
POST /api/admin/study/timer/pause
POST /api/admin/study/timer/resume
POST /api/admin/study/timer/finish
POST /api/admin/study/timer/discard
POST /api/admin/study/timer/break
```

Each route calls `reconcile_timer` before returning. `finish` requires `{"save": true|false}`; `discard` removes the active row and records only a bounded audit event.

- [ ] **Step 4: Add focus history, correction and export routes**

```text
GET    /api/admin/study/focus?from=&to=&subject=&cursor=
POST   /api/admin/study/focus
PATCH  /api/admin/study/focus/{session_id}
DELETE /api/admin/study/focus/{session_id}
GET    /api/admin/study/export.json
GET    /api/admin/study/focus.csv
GET    /api/admin/study/tasks.csv
```

Use `StreamingResponse` with `io.StringIO` and Python `csv.DictWriter`. JSON export includes schedule entries, days, tasks, focus sessions and exam events; it excludes admins, sessions and audit rows.

- [ ] **Step 5: Run focused tests and commit**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_study_timer.py server/tests/test_study_admin_api.py -q
git add server/src/ninesense_guestbook/web/study_admin.py server/src/ninesense_guestbook/web/study_schemas.py server/tests/test_study_admin_api.py
git commit -m "feat: manage focus timing and exports"
```

## Task 9: Build the Public Study Record Experience

**Files:**

- Modify: `site/records/study/index.html`
- Modify: `site/records/study/study.css`
- Modify: `site/records/study/study.js`
- Modify: `tests/test-static-release.ps1`

- [ ] **Step 1: Extend the static contract for the approved visual structure**

Require these markers in `test-static-release.ps1`:

```powershell
foreach ($contract in @(
  'STUDY RECORD / 2026', '备考这件事', 'id="countdown-value"',
  'id="current-study-status"', 'id="today-task-list"',
  'id="focus-trend"', 'id="subject-breakdown"',
  'id="recent-heatmap"', 'id="exam-timeline"'
)) {
  if ($study -notmatch [regex]::Escape($contract)) {
    throw "Study visual contract missing: $contract"
  }
}
```

Run the contract and expect failure.

- [ ] **Step 2: Implement the editorial HTML bands**

Use this top-level order:

```html
<header class="study-topbar"><a href="../../">NineSense</a><span>MORE RECORDS / 备考记录</span></header>
<section class="study-hero"><p>STUDY RECORD / 2026</p><h1>备考这件事，一天一天记录。</h1><strong id="countdown-value">—</strong></section>
<div class="study-status-rail"><span id="current-study-status" aria-live="polite">当前没有进行中的专注</span><span id="next-exam-event">最近节点待更新</span><time id="study-updated-at">—</time></div>
<nav class="study-nav" aria-label="备考记录视图"><a href="#study-today">今日计划</a><a href="#study-overview">专注总览</a><a href="#study-recent">最近 30 天</a><a href="#study-exams">考研时间表</a></nav>
<main>
  <section id="study-today"><h2>今天学什么</h2><div id="today-task-list"></div><blockquote id="today-reflection"></blockquote></section>
  <section id="study-overview"><h2>这个月真正学了多久</h2><div id="focus-trend"></div><div id="subject-breakdown"></div></section>
  <section id="study-recent"><h2>最近不是只看今天</h2><div id="recent-heatmap"></div><ol id="recent-day-list"></ol></section>
  <section id="study-exams"><h2>今年还有哪些时间点</h2><ol id="exam-timeline"></ol></section>
</main>
<footer><a href="../../">返回更多记录</a><span>PUBLIC VIEW · READ ONLY</span></footer>
```

Do not create nested card containers. Use full-width dark/light bands, a vertical task rail, one trend chart, one subject distribution and one exam timeline.

- [ ] **Step 3: Implement safe API rendering**

```js
const SUBJECT_LABELS = { math: "高数", "408": "408", english: "英语", politics: "政治" };

function setText(node, value, fallback = "—") {
  node.textContent = value ?? fallback;
}

function createTask(task) {
  const article = document.createElement("article");
  article.className = `study-task is-${task.status}`;
  const time = document.createElement("time");
  setText(time, task.start_time);
  const subject = document.createElement("span");
  setText(subject, task.kind === "rest" ? "REST" : SUBJECT_LABELS[task.subject]);
  const title = document.createElement("h3");
  setText(title, task.title);
  const description = document.createElement("p");
  setText(description, task.description, "");
  const status = document.createElement("span");
  setText(status, statusLabel(task));
  article.append(time, subject, title, description, status);
  return article;
}

async function loadStudyPage() {
  const [today, recent, exams] = await Promise.all([
    fetchJson("/api/study/today"),
    fetchJson("/api/study/recent?days=30"),
    fetchJson("/api/study/exams"),
  ]);
  const month = await fetchJson(`/api/study/months/${today.date.slice(0, 7)}`);
  renderToday(today);
  renderOverview(month);
  renderRecent(recent);
  renderExams(exams);
}
```

Use only `textContent`, `createElement`, `append` and safe attribute assignment. Show a per-section retry button on failure; never substitute fabricated data.

- [ ] **Step 4: Implement the approved responsive styling**

Use the existing site variables and exact palette:

```css
:root {
  --paper: #ebe5dc;
  --paper-soft: #f3eee6;
  --ink: #12110f;
  --muted: #716b62;
  --line: rgba(24, 22, 19, .16);
  --amber: #c9914d;
  --cool: #65717a;
  --dark: #12100e;
  --cream: #efe7db;
}
```

At `max-width: 900px`, stack hero, status rail, daily plan and overview. At `max-width: 560px`, keep a minimum 320-pixel layout, use horizontal scrolling only inside the view navigation, and prevent document-level overflow. Add reduced-motion rules for chart reveal and status transitions.

- [ ] **Step 5: Pass contracts and visually inspect four widths**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
```

Inspect 1440x1000, 768x1024, 390x844 and 320x800. Confirm the title, countdown, task rail, charts and exam timeline do not clip or overlap.

- [ ] **Step 6: Commit**

```powershell
git add site/records/study tests/test-static-release.ps1
git commit -m "feat: build public study record"
```

## Task 10: Build the Mobile-First Today and Timer Administration Flow

**Files:**

- Create: `admin-app/src/pages/study/StudyLayout.jsx`
- Create: `admin-app/src/pages/study/StudyTodayPage.jsx`
- Create: `admin-app/src/pages/study/StudyTimerPanel.jsx`
- Create: `admin-app/src/pages/study/StudyTaskEditor.jsx`
- Create: `admin-app/src/pages/study/studyApi.js`
- Create: `admin-app/src/styles/study.css`
- Modify: `admin-app/src/App.jsx`
- Modify: `admin-app/src/layout/AdminShell.jsx`
- Modify: `admin-app/src/main.jsx`

- [ ] **Step 1: Add the route and build the failing application contract**

Add `/study` to `AdminShell` navigation and nested routes to `App.jsx`, then run:

```powershell
npm --prefix admin-app run build
```

Expected before creating the page modules: FAIL with unresolved study imports.

- [ ] **Step 2: Add study API helpers**

```js
import { api } from "../../api/client.js";

export const getToday = (date) => api(`/api/admin/study/days/${date}`);
export const getTimer = () => api("/api/admin/study/timer");
export const startTimer = (payload) => api("/api/admin/study/timer/start", { method: "POST", body: JSON.stringify(payload) });
export const pauseTimer = () => api("/api/admin/study/timer/pause", { method: "POST" });
export const resumeTimer = () => api("/api/admin/study/timer/resume", { method: "POST" });
export const finishTimer = (save) => api("/api/admin/study/timer/finish", { method: "POST", body: JSON.stringify({ save }) });
export const updateTask = (id, payload) => api(`/api/admin/study/tasks/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
export const updateReflection = (date, reflection) => api(`/api/admin/study/days/${date}/reflection`, { method: "PATCH", body: JSON.stringify({ reflection }) });
```

- [ ] **Step 3: Build the timer panel**

`StudyTimerPanel` must:

- render fixed subject controls for high math, 408, English and politics;
- render a segmented preset control for 25/5, 50/10 and custom;
- derive remaining seconds from the server timestamps;
- poll `/timer` every 15 seconds and on `visibilitychange`;
- request notifications only after a user clicks “enable reminders”;
- show `保存本次` and `放弃本次` when ending early;
- never store session or CSRF data in local/session storage.

Use this countdown calculation:

```js
function remainingSeconds(timer, now = Date.now()) {
  if (!timer || timer.state === "paused") return timer?.remaining_seconds ?? 0;
  return Math.max(0, Math.ceil((Date.parse(timer.planned_end_at) - now) / 1000));
}
```

- [ ] **Step 4: Build today task and reflection editing**

`StudyTaskEditor` uses native `input`, `select`, `textarea` and buttons. Status options are `planned`, `in_progress`, `completed`, `incomplete`, `cancelled`; rest rows omit subject selection. Save only changed fields and show inline errors without discarding input.

`StudyTodayPage` composes:

```jsx
<main className="admin-page study-admin-page">
  <header className="page-heading"><div><p>STUDY MANAGEMENT</p><h1>今天</h1></div><span>{date}</span></header>
  <StudyTimerPanel timer={timer} onChange={reload} />
  <section className="study-today-grid">
    <StudyTaskEditor day={day} onChange={reload} />
    <ReflectionEditor date={date} value={day.reflection} onSaved={reload} />
  </section>
</main>
```

- [ ] **Step 5: Add routes and responsive styles**

```jsx
<Route path="study" element={<StudyLayout />}>
  <Route index element={<StudyTodayPage />} />
</Route>
```

At 720 pixels and below, timer controls stack, subject buttons remain a stable 2x2 grid, and task fields use one column. Import `./styles/study.css` from `main.jsx`.

- [ ] **Step 6: Build and commit**

```powershell
npm --prefix admin-app run build
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-admin-build.ps1
git add admin-app site/admin tests/test-admin-build.ps1
git commit -m "feat: add study timer workspace"
```

## Task 11: Build Schedule, History, Focus and Exam Administration Pages

**Files:**

- Create: `admin-app/src/pages/study/StudySchedulePage.jsx`
- Create: `admin-app/src/pages/study/StudyHistoryPage.jsx`
- Create: `admin-app/src/pages/study/StudyFocusPage.jsx`
- Create: `admin-app/src/pages/study/StudyExamPage.jsx`
- Modify: `admin-app/src/pages/study/StudyLayout.jsx`
- Modify: `admin-app/src/pages/study/studyApi.js`
- Modify: `admin-app/src/App.jsx`
- Modify: `admin-app/src/styles/study.css`

- [ ] **Step 1: Add nested navigation and unresolved routes**

```jsx
const tabs = [
  ["今天", "/study"],
  ["周计划", "/study/schedule"],
  ["历史记录", "/study/history"],
  ["专注记录", "/study/focus"],
  ["考研时间表", "/study/exams"],
];
```

Add routes in `App.jsx`; run the build and expect unresolved page modules.

- [ ] **Step 2: Implement the effective-date schedule editor**

`StudySchedulePage` groups entries by weekday, uses native time/date inputs, supports adding study or rest rows, and validates end time after start time before API submission. Updating a template displays the explicit note `只影响尚未生成的日期`.

The save payload is exactly:

```js
{
  weekday: Number(form.weekday),
  kind: form.kind,
  subject: form.kind === "rest" ? null : form.subject,
  start_time: form.start_time,
  end_time: form.end_time,
  title: form.title.trim(),
  description: form.description.trim(),
  effective_from: form.effective_from,
  effective_until: form.effective_until || null,
  position: Number(form.position),
  active: form.active,
}
```

- [ ] **Step 3: Implement unlimited history browsing**

`StudyHistoryPage` provides from/to date inputs, defaults to the current month, permits any valid historical range, and displays full tasks, reflection and focus records for each returned date. Do not impose a 30-day client limit.

Use stable pagination or bounded ranges; reject a range larger than 366 days per request and let the user move the window rather than loading all history at once.

- [ ] **Step 4: Implement focus corrections and exports**

`StudyFocusPage` supports subject/date filters, manual record creation, correction with required reason, explicit delete confirmation, and links to JSON/CSV export endpoints. Deleting must name the subject, date and effective duration in the confirmation dialog.

- [ ] **Step 5: Implement exam timeline management**

`StudyExamPage` supports common node types plus custom events, estimated/confirmed status, optional date ranges, official source URL, active status, ordering and one countdown target. Selecting a new target clearly states that the previous target will be replaced.

- [ ] **Step 6: Build, inspect and commit**

```powershell
npm --prefix admin-app run build
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-admin-build.ps1
git add admin-app site/admin
git commit -m "feat: complete study administration"
```

## Task 12: Add E2E, Nginx and Release Integration

**Files:**

- Create: `tests/study-record-e2e.spec.js`
- Modify: `tests/e2e_server.py`
- Modify: `playwright.config.js`
- Modify: `deploy/ninesense-nginx.conf`
- Modify: `deploy/deploy-guestbook.sh`
- Modify: `tests/test-deploy-config.ps1`
- Modify: `README.md`

- [ ] **Step 1: Write the failing browser flow**

Add `study-record-e2e.spec.js` covering:

```js
test("owner records study progress and public page stays read only", async ({ page, request }) => {
  await loginOwner(page, request);
  await page.getByRole("link", { name: "学习管理", exact: true }).click();
  await page.getByRole("button", { name: "408", exact: true }).click();
  await page.getByRole("button", { name: "25 / 5", exact: true }).click();
  await page.getByRole("button", { name: "开始专注" }).click();
  await expect(page.getByText("正在专注 408")).toBeVisible();

  await page.goto("/records/study/");
  await expect(page.getByRole("heading", { name: "备考这件事，一天一天记录。" })).toBeVisible();
  await expect(page.getByText("正在专注 408")).toBeVisible();
  await expect(page.getByRole("button", { name: /新增|修改|删除|开始专注/ })).toHaveCount(0);
});
```

Add a second test for 1440, 768, 390 and 320 widths, checking document overflow on both `/records/study/` and `/admin/study`.

- [ ] **Step 2: Include study metadata and suite configuration**

In `tests/e2e_server.py`, import `study_models` before `Base.metadata.create_all`. Add `study-record-e2e.spec.js` to `playwright.config.js` `testMatch`.

Run:

```powershell
npx playwright test tests/study-record-e2e.spec.js
```

Expected before final selectors and routes are complete: focused failure that identifies the missing contract.

- [ ] **Step 3: Add records Nginx policy**

Add before the generic `/api/` location:

```nginx
location ^~ /records/ {
    try_files $uri $uri/ =404;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'" always;
    add_header X-Robots-Tag "noindex, nofollow" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Cache-Control "no-cache" always;
}
```

The public API remains under the current `/api/` reverse proxy and does not open a new listener or port.

- [ ] **Step 4: Extend deployment and configuration contracts**

Require `location ^~ /records/`, `X-Robots-Tag`, and `form-action 'none'` in `test-deploy-config.ps1`. Add release smoke checks:

```bash
[[ $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8811/records/) == 200 ]]
[[ $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8811/records/study/) == 200 ]]
[[ $(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8811/api/study/today) == 200 ]]
```

Do not deploy during this task.

- [ ] **Step 5: Document local and retention behavior**

Add to `README.md`:

- study API and public routes;
- all detailed history is retained in SQLite until explicitly deleted;
- public detail is limited to 30 days;
- migration and backup include the study tables;
- production deployment waits for explicit authorization.

- [ ] **Step 6: Pass integrated browser and release tests**

```powershell
npm --prefix admin-app run build
npx playwright test tests/study-record-e2e.spec.js
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-deploy-config.ps1
```

- [ ] **Step 7: Commit**

```powershell
git add tests playwright.config.js deploy README.md
git commit -m "test: cover study record workflow"
```

## Task 13: Run the Full Gate and Prepare the Local Release

**Files:**

- Modify only files required by failures found in this task.
- Do not change production state.

- [ ] **Step 1: Run backend formatting and all tests**

```powershell
server/.venv/Scripts/python -m ruff check server/src server/tests server/alembic
server/.venv/Scripts/python -W 'error::ResourceWarning' -m pytest server/tests
```

Expected: no lint failures, no pytest failures and no warnings promoted to errors.

- [ ] **Step 2: Build administration and run all release contracts**

```powershell
npm --prefix admin-app run build
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-admin-build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-deploy-config.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-public-repo.ps1
```

Expected: every PowerShell contract prints `PASS`.

- [ ] **Step 3: Run all browser tests**

```powershell
npm run test:e2e
```

Expected: guestbook, administration foundation and study-record suites all pass.

- [ ] **Step 4: Verify migration safety on an isolated copy**

```powershell
server/.venv/Scripts/python -m pytest server/tests/test_migrations.py::test_legacy_business_data_survives_backup_upgrade_and_rollback server/tests/test_migrations.py::test_study_record_migration_round_trip -q
```

Expected: both isolated-database tests pass; old row counts remain unchanged, study tables appear only at revision 0003, and no production database is touched.

- [ ] **Step 5: Perform visual QA with screenshots**

At 1440x1000, 768x1024, 390x844 and 320x800 verify:

- public hero, countdown and status rail;
- today task rail and reflection;
- monthly chart, subject distribution and recent heatmap;
- exam timeline;
- mobile timer, task status and reflection editing;
- desktop schedule, history, focus and exam management;
- zero document-level horizontal overflow.

Also test `prefers-reduced-motion`, notification denied, API unavailable and empty-data states.

- [ ] **Step 6: Review the final diff and security boundaries**

```powershell
git diff --check
git status --short
git diff --stat HEAD~12..HEAD
```

Confirm no credentials, databases, backups, personal contact data, browser tokens or server logs are present. Confirm public APIs contain only the documented whitelist and no public write route exists.

- [ ] **Step 7: Commit any verification fixes and stop before deployment**

```powershell
git add --update
git commit -m "fix: close study record verification gaps"
```

If no fixes were required, do not create an empty commit. Report the final test counts, commit list and local URLs. Wait for explicit production-deployment authorization.
