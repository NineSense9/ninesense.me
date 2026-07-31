from datetime import date, datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import select

from ninesense_guestbook.admin_models import AuditEvent
from ninesense_guestbook.study_models import ExamEvent, FocusTimer, StudyDay

from admin_test_helpers import create_totp_admin, login_with_totp


@pytest.fixture
def authenticated_client(client, app, db_session):
    _, secret = create_totp_admin(db_session, app)
    login = login_with_totp(client, secret)
    client.headers.update({"X-CSRF-Token": login.json()["csrf_token"]})
    return client


def schedule_payload(**overrides):
    data = {
        "weekday": 5,
        "kind": "study",
        "subject": "408",
        "start_time": "08:30",
        "end_time": "12:00",
        "title": "408",
        "description": "数据结构",
        "effective_from": "2026-08-01",
        "effective_until": None,
        "position": 10,
        "active": True,
    }
    data.update(overrides)
    return data


def exam_payload(**overrides):
    data = {
        "kind": "registration",
        "title": "网上报名",
        "date_status": "estimated",
        "start_date": "2026-10-01",
        "end_date": None,
        "description": "日期待确认",
        "source_url": None,
        "countdown_target": False,
        "position": 10,
        "active": True,
    }
    data.update(overrides)
    return data


def test_study_admin_requires_session_and_csrf(client, app, db_session):
    assert client.get("/api/admin/study/days/2026-08-01").status_code == 401

    _, secret = create_totp_admin(db_session, app)
    login_with_totp(client, secret)
    response = client.post(
        "/api/admin/study/schedule",
        json=schedule_payload(),
    )

    assert response.status_code == 403


def test_admin_creates_schedule_and_updates_today(authenticated_client):
    created = authenticated_client.post(
        "/api/admin/study/schedule",
        json=schedule_payload(),
    )

    assert created.status_code == 201
    day = authenticated_client.get("/api/admin/study/days/2026-08-01")
    assert day.status_code == 200
    task_id = day.json()["tasks"][0]["id"]
    updated = authenticated_client.patch(
        f"/api/admin/study/tasks/{task_id}",
        json={"status": "completed", "title": "图论复盘"},
    )

    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"
    assert updated.json()["title"] == "图论复盘"


def test_admin_history_is_not_limited_to_thirty_days(
    authenticated_client,
    db_session,
):
    db_session.add(StudyDay(study_date=date(2025, 1, 1), reflection="旧记录"))
    db_session.commit()

    response = authenticated_client.get(
        "/api/admin/study/history?from=2025-01-01&to=2026-01-01"
    )

    assert response.status_code == 200
    assert any(
        item["date"].startswith("2025-")
        for item in response.json()["items"]
    )


def test_history_rejects_more_than_one_year_per_request(authenticated_client):
    response = authenticated_client.get(
        "/api/admin/study/history?from=2024-01-01&to=2026-01-01"
    )

    assert response.status_code == 422


def test_schedule_payload_is_strict_and_validates_rest_subject(
    authenticated_client,
):
    extra = authenticated_client.post(
        "/api/admin/study/schedule",
        json=schedule_payload(unexpected="value"),
    )
    invalid_rest = authenticated_client.post(
        "/api/admin/study/schedule",
        json=schedule_payload(kind="rest", subject="408"),
    )

    assert extra.status_code == 422
    assert invalid_rest.status_code == 422


def test_task_and_reflection_audits_do_not_store_content(
    authenticated_client,
    db_session,
):
    authenticated_client.post(
        "/api/admin/study/schedule",
        json=schedule_payload(),
    )
    day = authenticated_client.get("/api/admin/study/days/2026-08-01").json()
    task_id = day["tasks"][0]["id"]
    secret_text = "这段复盘只应该存在学习记录里"

    authenticated_client.patch(
        f"/api/admin/study/tasks/{task_id}",
        json={"description": "完整任务正文"},
    )
    authenticated_client.patch(
        "/api/admin/study/days/2026-08-01/reflection",
        json={"reflection": secret_text},
    )

    events = list(db_session.scalars(select(AuditEvent)))
    audit_text = "\n".join(event.details_json for event in events)
    assert secret_text not in audit_text
    assert "完整任务正文" not in audit_text
    changed_fields = [
        json.loads(event.details_json).get("changed_fields", [])
        for event in events
    ]
    assert ["reflection"] in changed_fields
    assert ["description"] in changed_fields


def test_setting_countdown_target_replaces_the_previous_target(
    authenticated_client,
    db_session,
):
    first = authenticated_client.post(
        "/api/admin/study/exams",
        json=exam_payload(countdown_target=True),
    )
    second = authenticated_client.post(
        "/api/admin/study/exams",
        json=exam_payload(
            kind="exam",
            title="初试",
            start_date="2026-12-20",
            countdown_target=True,
            position=20,
        ),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    db_session.expire_all()
    targets = list(
        db_session.scalars(
            select(ExamEvent).where(
                ExamEvent.countdown_target.is_(True),
                ExamEvent.active.is_(True),
            )
        )
    )
    assert [row.id for row in targets] == [second.json()["id"]]


def test_admin_can_create_and_edit_a_past_blank_day(authenticated_client):
    created = authenticated_client.post(
        "/api/admin/study/days/2025-03-01",
        json={"generate_from_template": False},
    )
    task = authenticated_client.post(
        "/api/admin/study/days/2025-03-01/tasks",
        json={
            "kind": "study",
            "subject": "math",
            "start_time": "09:00",
            "end_time": "10:30",
            "title": "高数补录",
            "description": "极限",
            "status": "completed",
            "position": 10,
        },
    )

    assert created.status_code == 201
    assert task.status_code == 201
    assert task.json()["subject"] == "math"


def test_timer_lifecycle_and_public_state(authenticated_client):
    started = authenticated_client.post(
        "/api/admin/study/timer/start",
        json={
            "subject": "408",
            "preset": "25_5",
            "focus_seconds": 1500,
            "break_seconds": 300,
            "idempotency_key": "a" * 32,
        },
    )

    assert started.status_code == 201
    assert started.json()["timer"]["subject"] == "408"
    assert authenticated_client.get("/api/study/today").json()[
        "active_subject"
    ] == "408"
    assert authenticated_client.post(
        "/api/admin/study/timer/pause"
    ).json()["timer"]["state"] == "paused"
    assert authenticated_client.post(
        "/api/admin/study/timer/resume"
    ).json()["timer"]["state"] == "running"
    finished = authenticated_client.post(
        "/api/admin/study/timer/finish",
        json={"save": True},
    )

    assert finished.status_code == 200
    assert finished.json()["session"]["effective_seconds"] >= 0
    assert authenticated_client.get("/api/admin/study/timer").json()[
        "timer"
    ] is None


def test_finish_returns_session_if_server_already_reconciled_timer(
    authenticated_client,
    db_session,
):
    authenticated_client.post(
        "/api/admin/study/timer/start",
        json={
            "subject": "english",
            "preset": "25_5",
            "focus_seconds": 1500,
            "break_seconds": 300,
            "idempotency_key": "d" * 32,
        },
    )
    timer = db_session.scalar(select(FocusTimer))
    timer.started_at = datetime.now(timezone.utc) - timedelta(minutes=26)
    timer.planned_end_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    response = authenticated_client.post(
        "/api/admin/study/timer/finish",
        json={"save": True},
    )

    assert response.status_code == 200
    assert response.json()["session"]["completion_kind"] == "completed"


def test_break_timer_does_not_create_focus_history(authenticated_client):
    started = authenticated_client.post(
        "/api/admin/study/timer/break",
        json={
            "break_seconds": 300,
            "idempotency_key": "break" * 8,
        },
    )
    discarded = authenticated_client.post(
        "/api/admin/study/timer/discard"
    )
    history = authenticated_client.get(
        "/api/admin/study/focus?from=2026-01-01&to=2026-12-31"
    )

    assert started.status_code == 201
    assert started.json()["timer"]["phase"] == "break"
    assert discarded.status_code == 200
    assert history.json()["items"] == []


def test_manual_focus_correction_is_audited(
    authenticated_client,
    db_session,
):
    created = authenticated_client.post(
        "/api/admin/study/focus",
        json={
            "subject": "math",
            "started_at": "2026-08-01T06:00:00Z",
            "ended_at": "2026-08-01T07:00:00Z",
            "effective_seconds": 3600,
            "reason": "补录线下学习",
        },
    )
    session_id = created.json()["id"]
    updated = authenticated_client.patch(
        f"/api/admin/study/focus/{session_id}",
        json={
            "effective_seconds": 3300,
            "reason": "扣除中断时间",
        },
    )

    assert created.status_code == 201
    assert updated.status_code == 200
    assert updated.json()["effective_seconds"] == 3300
    db_session.expire_all()
    actions = [row.action for row in db_session.scalars(select(AuditEvent))]
    assert "study.focus.created" in actions
    assert "study.focus.updated" in actions
    audit_text = "\n".join(
        row.details_json for row in db_session.scalars(select(AuditEvent))
    )
    assert "补录线下学习" not in audit_text
    assert "扣除中断时间" not in audit_text


def test_focus_input_rejects_effective_time_longer_than_elapsed(
    authenticated_client,
):
    response = authenticated_client.post(
        "/api/admin/study/focus",
        json={
            "subject": "english",
            "started_at": "2026-08-01T06:00:00Z",
            "ended_at": "2026-08-01T06:30:00Z",
            "effective_seconds": 3600,
            "reason": "无效补录",
        },
    )

    assert response.status_code == 422


def test_json_and_csv_exports_include_complete_history(
    authenticated_client,
    db_session,
):
    db_session.add(StudyDay(study_date=date(2025, 1, 1), reflection="长期保留"))
    db_session.commit()
    authenticated_client.post(
        "/api/admin/study/focus",
        json={
            "subject": "politics",
            "started_at": "2025-01-01T06:00:00Z",
            "ended_at": "2025-01-01T06:30:00Z",
            "effective_seconds": 1800,
            "reason": "历史补录",
        },
    )

    json_response = authenticated_client.get("/api/admin/study/export.json")
    focus_csv = authenticated_client.get("/api/admin/study/focus.csv")
    task_csv = authenticated_client.get("/api/admin/study/tasks.csv")

    assert json_response.status_code == 200
    assert any(
        row["reflection"] == "长期保留"
        for row in json_response.json()["days"]
    )
    assert "admins" not in json_response.json()
    assert "sessions" not in json_response.json()
    assert "audit" not in json_response.json()
    assert focus_csv.headers["content-type"].startswith("text/csv")
    assert "politics" in focus_csv.text
    assert task_csv.headers["content-type"].startswith("text/csv")
