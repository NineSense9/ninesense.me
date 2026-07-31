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
    now = datetime.now(timezone.utc)
    admin = Admin(username="owner", password_hash="hash", active=True)
    day = StudyDay(study_date=date(2026, 8, 1), reflection="今天复盘")
    db_session.add_all([admin, day])
    db_session.flush()

    db_session.add_all(
        [
            StudyScheduleEntry(
                weekday=5,
                task_kind="study",
                subject="408",
                start_time=time(8, 30),
                end_time=time(12),
                title="408",
                description="上午学习",
                effective_from=date(2026, 8, 1),
                position=10,
                active=True,
            ),
            StudyTask(
                day_id=day.id,
                task_kind="study",
                subject="408",
                start_time=time(8, 30),
                end_time=time(12),
                title="数据结构",
                description="图论复盘",
                status="planned",
                position=10,
            ),
            FocusTimer(
                admin_id=admin.id,
                subject="408",
                phase="focus",
                preset_kind="50_10",
                focus_seconds=3000,
                break_seconds=600,
                state="running",
                started_at=now,
                planned_end_at=now,
                idempotency_key="a" * 32,
            ),
            FocusSession(
                admin_id=admin.id,
                subject="408",
                planned_seconds=3000,
                started_at=now,
                ended_at=now,
                effective_seconds=1800,
                completion_kind="early_saved",
                source="manual",
                correction_reason="补录线下学习",
            ),
            ExamEvent(
                kind="registration",
                title="网上报名",
                date_status="estimated",
                start_date=date(2026, 10, 1),
                description="日期待确认",
                countdown_target=False,
                position=10,
                active=True,
            ),
        ]
    )
    db_session.commit()


def test_only_one_active_timer_per_admin(db_session):
    admin = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(admin)
    db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            FocusTimer(
                admin_id=admin.id,
                subject="408",
                phase="focus",
                preset_kind="25_5",
                focus_seconds=1500,
                break_seconds=300,
                state="running",
                started_at=now,
                planned_end_at=now,
                idempotency_key="a" * 32,
            ),
            FocusTimer(
                admin_id=admin.id,
                subject="math",
                phase="focus",
                preset_kind="25_5",
                focus_seconds=1500,
                break_seconds=300,
                state="running",
                started_at=now,
                planned_end_at=now,
                idempotency_key="b" * 32,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize(
    ("task_kind", "subject"),
    [("study", None), ("rest", "english"), ("invalid", None)],
)
def test_schedule_kind_and_subject_constraints(db_session, task_kind, subject):
    db_session.add(
        StudyScheduleEntry(
            weekday=0,
            task_kind=task_kind,
            subject=subject,
            start_time=time(8),
            end_time=time(9),
            title="invalid",
            description="",
            effective_from=date(2026, 8, 1),
            position=10,
            active=True,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_only_one_active_countdown_target(db_session):
    db_session.add_all(
        [
            ExamEvent(
                kind="registration",
                title="报名",
                date_status="estimated",
                start_date=date(2026, 10, 1),
                description="",
                countdown_target=True,
                position=10,
                active=True,
            ),
            ExamEvent(
                kind="exam",
                title="初试",
                date_status="estimated",
                start_date=date(2026, 12, 20),
                description="",
                countdown_target=True,
                position=20,
                active=True,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
