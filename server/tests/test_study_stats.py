from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace

from ninesense_guestbook.models import Admin
from ninesense_guestbook.services.study_stats import (
    admin_history,
    completion_summary,
    month_summary,
    public_recent_days,
)
from ninesense_guestbook.study_models import FocusSession, StudyDay, StudyTask


def focus_session(admin_id, subject, started_at, seconds):
    return FocusSession(
        admin_id=admin_id,
        subject=subject,
        planned_seconds=seconds,
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=seconds),
        effective_seconds=seconds,
        completion_kind="manual",
        source="manual",
        correction_reason="补录",
    )


def study_task(day_id, status, *, task_kind="study", subject="408"):
    return StudyTask(
        day_id=day_id,
        task_kind=task_kind,
        subject=subject if task_kind == "study" else None,
        start_time=time(8),
        end_time=time(9),
        title=status,
        description="",
        status=status,
        position=10,
    )


def test_completion_excludes_rest_cancelled_and_open_tasks():
    tasks = [
        SimpleNamespace(task_kind="study", status="completed"),
        SimpleNamespace(task_kind="study", status="incomplete"),
        SimpleNamespace(task_kind="study", status="planned"),
        SimpleNamespace(task_kind="study", status="cancelled"),
        SimpleNamespace(task_kind="rest", status="planned"),
    ]

    assert completion_summary(tasks) == {
        "completed": 1,
        "closed": 2,
        "rate": 0.5,
    }


def test_completion_without_closed_tasks_has_no_rate():
    tasks = [SimpleNamespace(task_kind="study", status="planned")]

    assert completion_summary(tasks) == {
        "completed": 0,
        "closed": 0,
        "rate": None,
    }


def test_month_summary_uses_effective_seconds_and_all_subjects(db_session):
    admin = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add_all(
        [
            focus_session(
                admin.id,
                "408",
                datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
                3600,
            ),
            focus_session(
                admin.id,
                "math",
                datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc),
                3600,
            ),
        ]
    )
    db_session.commit()

    result = month_summary(db_session, "2026-08")

    assert result["total_seconds"] == 7200
    assert result["subjects"] == {
        "math": 3600,
        "408": 3600,
        "english": 0,
        "politics": 0,
    }


def test_month_summary_uses_shanghai_natural_day_boundaries(db_session):
    admin = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add(
        focus_session(
            admin.id,
            "english",
            datetime(2026, 7, 31, 16, 30, tzinfo=timezone.utc),
            1800,
        )
    )
    db_session.commit()

    result = month_summary(db_session, "2026-08")

    assert result["subjects"]["english"] == 1800
    assert result["daily"] == [{"date": "2026-08-01", "seconds": 1800}]


def test_month_completion_uses_only_closed_study_tasks(db_session):
    day = StudyDay(study_date=date(2026, 8, 1), reflection="")
    db_session.add(day)
    db_session.flush()
    db_session.add_all(
        [
            study_task(day.id, "completed"),
            study_task(day.id, "incomplete"),
            study_task(day.id, "planned"),
            study_task(day.id, "cancelled"),
            study_task(day.id, "planned", task_kind="rest", subject=None),
        ]
    )
    db_session.commit()

    result = month_summary(db_session, "2026-08")

    assert result["completion"] == {
        "completed": 1,
        "closed": 2,
        "rate": 0.5,
    }


def test_public_recent_is_capped_at_thirty_days(db_session):
    db_session.add_all(
        [
            StudyDay(
                study_date=date(2026, 8, 1) - timedelta(days=offset),
                reflection=str(offset),
            )
            for offset in range(45)
        ]
    )
    db_session.commit()

    rows = public_recent_days(
        db_session,
        date(2026, 8, 1),
        requested_days=90,
    )

    assert len(rows) <= 30
    assert min(row.study_date for row in rows) >= date(2026, 7, 3)


def test_admin_history_has_no_thirty_day_cap(db_session):
    db_session.add_all(
        [
            StudyDay(study_date=date(2025, 1, 1), reflection="旧记录"),
            StudyDay(study_date=date(2026, 8, 1), reflection="新记录"),
        ]
    )
    db_session.commit()

    rows = admin_history(
        db_session,
        date(2025, 1, 1),
        date(2026, 8, 1),
    )

    assert any(row.study_date.year == 2025 for row in rows)
