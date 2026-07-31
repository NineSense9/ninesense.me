from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from ninesense_guestbook.models import Admin
from ninesense_guestbook.services.study_timer import (
    as_utc,
    discard_timer,
    finish_timer,
    pause_timer,
    reconcile_timer,
    resume_timer,
    start_break_timer,
    start_timer,
)
from ninesense_guestbook.study_models import FocusSession, FocusTimer


NOW = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def admin(db_session):
    row = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(row)
    db_session.commit()
    return row


def test_timer_continues_without_browser_and_completes_once(db_session, admin):
    start_timer(
        db_session,
        admin.id,
        "408",
        "25_5",
        1500,
        300,
        "a" * 32,
        NOW,
    )
    db_session.commit()

    reconcile_timer(db_session, admin.id, NOW + timedelta(minutes=26))
    db_session.commit()
    reconcile_timer(db_session, admin.id, NOW + timedelta(minutes=27))
    db_session.commit()

    assert db_session.scalar(select(FocusTimer)) is None
    assert len(list(db_session.scalars(select(FocusSession)))) == 1


def test_pause_extends_planned_end_and_excludes_paused_time(db_session, admin):
    timer = start_timer(
        db_session,
        admin.id,
        "math",
        "50_10",
        3000,
        600,
        "b" * 32,
        NOW,
    )
    pause_timer(db_session, timer, NOW + timedelta(minutes=10))
    resume_timer(db_session, timer, NOW + timedelta(minutes=15))

    assert timer.accumulated_pause_seconds == 300
    assert timer.planned_end_at == NOW + timedelta(minutes=55)

    session = finish_timer(
        db_session,
        timer,
        save=True,
        now=NOW + timedelta(minutes=25),
    )
    assert session.effective_seconds == 1200


def test_paused_timer_does_not_complete_while_browser_is_closed(db_session, admin):
    timer = start_timer(
        db_session,
        admin.id,
        "408",
        "25_5",
        1500,
        300,
        "pause" * 8,
        NOW,
    )
    pause_timer(db_session, timer, NOW + timedelta(minutes=5))
    db_session.commit()

    result = reconcile_timer(db_session, admin.id, NOW + timedelta(hours=3))

    assert isinstance(result, FocusTimer)
    assert result.state == "paused"
    assert db_session.scalar(select(FocusSession)) is None


def test_early_finish_can_save_or_discard(db_session, admin):
    saved = start_timer(
        db_session,
        admin.id,
        "english",
        "custom",
        2400,
        0,
        "c" * 32,
        NOW,
    )
    session = finish_timer(
        db_session,
        saved,
        save=True,
        now=NOW + timedelta(minutes=12),
    )
    assert session.effective_seconds == 720

    discarded = start_timer(
        db_session,
        admin.id,
        "politics",
        "custom",
        1200,
        0,
        "d" * 32,
        NOW,
    )
    assert discard_timer(db_session, discarded) is None
    assert db_session.scalar(select(FocusTimer)) is None


def test_second_active_timer_is_rejected(db_session, admin):
    start_timer(
        db_session,
        admin.id,
        "408",
        "25_5",
        1500,
        300,
        "e" * 32,
        NOW,
    )

    with pytest.raises(HTTPException) as error:
        start_timer(
            db_session,
            admin.id,
            "math",
            "25_5",
            1500,
            300,
            "f" * 32,
            NOW,
        )

    assert error.value.status_code == 409


def test_duplicate_idempotency_key_returns_the_existing_timer(db_session, admin):
    key = "same-key-value-000000000000000"
    first = start_timer(
        db_session,
        admin.id,
        "408",
        "25_5",
        1500,
        300,
        key,
        NOW,
    )
    duplicate = start_timer(
        db_session,
        admin.id,
        "408",
        "25_5",
        1500,
        300,
        key,
        NOW + timedelta(seconds=1),
    )

    assert duplicate.id == first.id


def test_break_timer_finishes_without_creating_focus_history(db_session, admin):
    break_timer = start_break_timer(
        db_session,
        admin.id,
        300,
        "break-key-value-00000000000000",
        NOW,
    )

    assert reconcile_timer(
        db_session,
        admin.id,
        NOW + timedelta(minutes=6),
    ) is None
    assert db_session.get(FocusTimer, break_timer.id) is None
    assert db_session.scalar(select(FocusSession)) is None


def test_sqlite_naive_datetimes_are_normalized_to_utc(db_session, admin):
    timer = start_timer(
        db_session,
        admin.id,
        "408",
        "25_5",
        1500,
        300,
        "naive-time-value-00000000000000",
        NOW,
    )
    db_session.commit()
    db_session.expire_all()

    stored = db_session.get(FocusTimer, timer.id)
    assert as_utc(stored.started_at).tzinfo is not None
    assert reconcile_timer(
        db_session,
        admin.id,
        NOW + timedelta(minutes=26),
    ) is not None


def test_completed_timer_ids_are_not_reused(db_session, admin):
    first = start_timer(
        db_session,
        admin.id,
        "408",
        "25_5",
        1500,
        300,
        "first-timer-value-0000000000000",
        NOW,
    )
    first_id = first.id
    finish_timer(
        db_session,
        first,
        save=True,
        now=NOW + timedelta(minutes=25),
    )
    second = start_timer(
        db_session,
        admin.id,
        "math",
        "25_5",
        1500,
        300,
        "second-timer-value-000000000000",
        NOW + timedelta(minutes=30),
    )

    assert second.id > first_id
