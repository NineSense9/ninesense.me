from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ninesense_guestbook.models import Admin
from ninesense_guestbook.study_models import (
    ExamEvent,
    FocusTimer,
    StudyDay,
    StudyScheduleEntry,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


def test_public_today_generates_only_today_and_whitelists_timer(
    client,
    db_session,
):
    today = datetime.now(SHANGHAI).date()
    admin = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add(
        StudyScheduleEntry(
            weekday=today.weekday(),
            task_kind="study",
            subject="408",
            start_time=time(8, 30),
            end_time=time(12),
            title="408",
            description="数据结构",
            effective_from=today,
            position=10,
            active=True,
        )
    )
    now = datetime.now(timezone.utc)
    db_session.add(
        FocusTimer(
            admin_id=admin.id,
            subject="408",
            phase="focus",
            preset_kind="25_5",
            focus_seconds=1500,
            break_seconds=300,
            state="running",
            started_at=now,
            planned_end_at=now + timedelta(minutes=25),
            idempotency_key="a" * 32,
        )
    )
    db_session.commit()

    response = client.get("/api/study/today")

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == today.isoformat()
    assert payload["active_subject"] == "408"
    assert "started_at" not in payload
    assert "planned_end_at" not in payload
    assert set(payload["tasks"][0]) == {
        "id",
        "kind",
        "subject",
        "start_time",
        "end_time",
        "title",
        "description",
        "status",
    }
    assert response.headers["cache-control"].startswith("public, max-age=30")


def test_public_today_without_an_admin_has_no_active_subject(client):
    response = client.get("/api/study/today")

    assert response.status_code == 200
    assert response.json()["active_subject"] is None


def test_public_recent_rejects_more_than_thirty_days(client):
    response = client.get("/api/study/recent?days=31")

    assert response.status_code == 422


def test_public_recent_excludes_days_older_than_thirty_days(client, db_session):
    today = datetime.now(SHANGHAI).date()
    recent = StudyDay(study_date=today - timedelta(days=29), reflection="保留")
    old = StudyDay(study_date=today - timedelta(days=30), reflection="隐藏")
    db_session.add_all([recent, old])
    db_session.commit()

    payload = client.get("/api/study/recent?days=30").json()

    assert [item["date"] for item in payload["items"]] == [
        recent.study_date.isoformat()
    ]
    assert "隐藏" not in str(payload)


def test_public_routes_have_no_write_methods(client):
    assert client.post("/api/study/today", json={}).status_code == 405
    assert client.patch("/api/study/today", json={}).status_code == 405
    assert client.delete("/api/study/today").status_code == 405


def test_public_month_does_not_return_reflection_or_task_body(client, db_session):
    db_session.add(StudyDay(study_date=date(2025, 1, 1), reflection="完整旧复盘"))
    db_session.commit()

    response = client.get("/api/study/months/2025-01")

    assert response.status_code == 200
    payload = response.json()
    assert "reflection" not in payload
    assert "tasks" not in payload
    assert "完整旧复盘" not in response.text


def test_public_exams_returns_only_active_events(client, db_session):
    db_session.add_all(
        [
            ExamEvent(
                kind="exam",
                title="初试",
                date_status="estimated",
                start_date=date(2026, 12, 20),
                description="预计时间",
                countdown_target=True,
                position=10,
                active=True,
            ),
            ExamEvent(
                kind="custom",
                title="隐藏节点",
                date_status="confirmed",
                start_date=date(2026, 9, 1),
                description="",
                countdown_target=False,
                position=20,
                active=False,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/study/exams")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["初试"]
    assert "隐藏节点" not in response.text
