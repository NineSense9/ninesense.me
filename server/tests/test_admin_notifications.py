from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from ninesense_guestbook.admin_models import AdminNotification
from ninesense_guestbook.models import Admin, Message
from ninesense_guestbook.services.admin_notifications import (
    create_notification,
    create_notification_once,
)
from ninesense_guestbook.services.audit import record_audit

from admin_test_helpers import PASSWORD, create_totp_admin, login_with_totp


def authenticate(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    response = login_with_totp(client, secret)
    return response.json()["csrf_token"]


def test_notification_service_validates_bounded_fields(db_session):
    notification = create_notification(
        db_session,
        severity="warning",
        category="security",
        title="登录提醒",
        message="发现新的后台会话。",
    )
    db_session.commit()

    assert db_session.get(AdminNotification, notification.id).title == "登录提醒"
    with pytest.raises(ValueError, match="notification severity"):
        create_notification(
            db_session,
            severity="unknown",
            category="security",
            title="错误",
            message="错误",
        )


def test_notification_dedupe_window_reuses_the_existing_row(db_session):
    now = datetime.now(timezone.utc)
    first = create_notification_once(
        db_session,
        severity="warning",
        category="security",
        title="后台登录已临时锁定",
        message="连续验证失败。",
        now=now,
    )
    second = create_notification_once(
        db_session,
        severity="warning",
        category="security",
        title="后台登录已临时锁定",
        message="连续验证失败。",
        now=now + timedelta(minutes=5),
    )
    db_session.commit()

    assert first.id == second.id
    assert len(db_session.scalars(select(AdminNotification)).all()) == 1


def test_dashboard_reports_foundation_counts(client, db_session, app):
    authenticate(client, db_session, app)
    db_session.add(
        Message(
            kind="private",
            status="pending",
            nickname="访客",
            content="等待处理的内容",
            idempotency_key="n" * 32,
        )
    )
    create_notification(
        db_session,
        severity="info",
        category="interaction",
        title="新留言",
        message="收到一条待处理内容。",
    )
    db_session.commit()

    response = client.get("/api/admin/dashboard")

    assert response.status_code == 200
    assert set(response.json()) == {
        "pending_interactions",
        "unread_notifications",
        "active_sessions",
        "recent_security_events",
    }
    assert response.json()["pending_interactions"] == 1
    assert response.json()["unread_notifications"] >= 1
    assert response.json()["active_sessions"] == 1


def test_notification_list_filters_unread_and_paginates(
    client, db_session, app
):
    authenticate(client, db_session, app)
    now = datetime.now(timezone.utc)
    for index in range(3):
        row = create_notification(
            db_session,
            severity="info",
            category="test",
            title=f"通知 {index}",
            message="用于分页测试。",
        )
        row.created_at = now + timedelta(seconds=index)
    db_session.commit()

    first = client.get("/api/admin/notifications?unread=true&limit=2")
    second = client.get(
        "/api/admin/notifications",
        params={"unread": "true", "limit": 2, "cursor": first.json()["next_cursor"]},
    )

    assert first.status_code == second.status_code == 200
    assert len(first.json()["items"]) == 2
    assert first.json()["next_cursor"]
    assert len(second.json()["items"]) >= 1
    assert {
        "id",
        "severity",
        "category",
        "title",
        "message",
        "created_at",
        "read_at",
    } == set(first.json()["items"][0])


def test_mark_notification_read_and_read_all_require_csrf(
    client, db_session, app
):
    csrf = authenticate(client, db_session, app)
    row = create_notification(
        db_session,
        severity="info",
        category="test",
        title="待读通知",
        message="读取状态测试。",
    )
    db_session.commit()

    denied = client.patch(f"/api/admin/notifications/{row.id}/read")
    marked = client.patch(
        f"/api/admin/notifications/{row.id}/read",
        headers={"X-CSRF-Token": csrf},
    )
    all_read = client.post(
        "/api/admin/notifications/read-all",
        headers={"X-CSRF-Token": csrf},
    )

    assert denied.status_code == 403
    assert marked.status_code == all_read.status_code == 204
    db_session.expire_all()
    assert all(
        item.read_at is not None
        for item in db_session.scalars(select(AdminNotification)).all()
    )


def test_audit_list_has_a_strict_public_admin_allowlist(
    client, db_session, app
):
    authenticate(client, db_session, app)
    record_audit(
        db_session,
        action="settings.updated",
        outcome="success",
        details={"changed_fields": ["title"]},
    )
    db_session.commit()

    response = client.get("/api/admin/audit?action=settings.updated")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item) == {
        "action",
        "outcome",
        "target_type",
        "target_id",
        "details",
        "created_at",
    }
    assert item["details"] == {"changed_fields": ["title"]}
    assert "admin_id" not in response.text


def test_successful_login_creates_a_redacted_security_notification(
    client, db_session, app
):
    authenticate(client, db_session, app)
    db_session.expire_all()

    notifications = db_session.scalars(
        select(AdminNotification).where(AdminNotification.category == "security")
    ).all()

    assert len(notifications) == 1
    assert "192." not in notifications[0].message
    assert "ninesense" not in notifications[0].message.casefold()


def test_repeated_locked_login_attempts_create_one_redacted_notification(
    client, db_session
):
    from argon2 import PasswordHasher

    db_session.add(
        Admin(
            username="ninesense",
            password_hash=PasswordHasher().hash(PASSWORD),
            active=True,
        )
    )
    db_session.commit()
    for _ in range(5):
        client.post(
            "/api/admin/session",
            json={"username": "ninesense", "password": "wrong-password"},
        )

    for _ in range(2):
        response = client.post(
            "/api/admin/session",
            json={"username": "ninesense", "password": PASSWORD},
        )
        assert response.status_code == 429

    notifications = db_session.scalars(
        select(AdminNotification).where(
            AdminNotification.title == "后台登录已临时锁定"
        )
    ).all()
    assert len(notifications) == 1
    assert "ninesense" not in notifications[0].message.casefold()
    assert "192." not in notifications[0].message
