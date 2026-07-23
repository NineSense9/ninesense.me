from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3

from sqlalchemy import select

from ninesense_guestbook.models import Admin, AdminSession, Message, Outbox
from ninesense_guestbook.services.outbox import (
    backup_database,
    cleanup_records,
    process_outbox_once,
)

from admin_test_helpers import create_totp_admin, login_with_totp


def add_pending_message(db_session, app, key="a"):
    encrypted = app.state.contact_cipher.encrypt("private-contact@example.com")
    message = Message(
        kind="private",
        status="pending",
        nickname="访客",
        contact_type="email",
        contact_nonce=encrypted.nonce,
        contact_ciphertext=encrypted.ciphertext,
        contact_key_version=encrypted.key_version,
        content="这是一条需要邮件提醒的私信，正文不应该完整进入日志。",
        idempotency_key=key * 32,
    )
    db_session.add(message)
    db_session.flush()
    outbox = Outbox(message_id=message.id)
    db_session.add(outbox)
    db_session.commit()
    return message, outbox


def authenticate(client, db_session, app):
    _admin, secret = create_totp_admin(db_session, app)
    response = login_with_totp(client, secret)
    return response.json()["csrf_token"]


def test_successful_delivery_marks_outbox_sent_without_contact(app, db_session):
    message, outbox = add_pending_message(db_session, app)
    delivered = []
    now = datetime.now(timezone.utc)
    outbox.next_attempt_at = now
    db_session.commit()

    def sender(settings, subject, body):
        delivered.append((subject, body))

    count = process_outbox_once(
        app.state.session_factory,
        app.state.settings,
        sender=sender,
        now=now,
    )

    assert count == 1
    db_session.expire_all()
    stored = db_session.get(Outbox, outbox.id)
    assert stored.sent_at is not None
    subject, body = delivered[0]
    assert "访客" in body
    assert "private" in body
    assert app.state.settings.public_admin_url in body
    assert "private-contact@example.com" not in subject + body
    assert message.content[:20] in body


def test_failed_delivery_schedules_sanitized_exponential_retry(app, db_session):
    _, outbox = add_pending_message(db_session, app, "b")
    now = datetime.now(timezone.utc)
    outbox.next_attempt_at = now
    db_session.commit()

    def failing_sender(settings, subject, body):
        raise RuntimeError("secret SMTP detail")

    process_outbox_once(
        app.state.session_factory,
        app.state.settings,
        sender=failing_sender,
        now=now,
    )

    db_session.expire_all()
    stored = db_session.get(Outbox, outbox.id)
    assert stored.attempts == 1
    assert stored.next_attempt_at == now.replace(tzinfo=None) + timedelta(minutes=1)
    assert stored.last_error == "RuntimeError"
    assert "secret" not in stored.last_error


def test_cleanup_removes_old_rejected_items_expired_sessions_and_sent_jobs(
    app, db_session
):
    now = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)
    message, outbox = add_pending_message(db_session, app, "c")
    message_id = message.id
    message.status = "rejected"
    message.reviewed_at = now - timedelta(days=31)
    outbox.sent_at = now - timedelta(days=31)
    admin = Admin(username="cleanup", password_hash="unused", active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add(
        AdminSession(
            id_hash="f" * 64,
            admin_id=admin.id,
            csrf_hash="e" * 64,
            expires_at=now - timedelta(minutes=1),
        )
    )
    db_session.commit()

    result = cleanup_records(app.state.session_factory, now=now)

    assert result == {"messages": 1, "sessions": 1, "outbox": 0}
    db_session.expire_all()
    assert db_session.get(Message, message_id) is None
    assert db_session.scalars(select(AdminSession)).all() == []


def test_online_backup_is_openable_and_integrity_checked(app, db_session, tmp_path):
    message, _ = add_pending_message(db_session, app, "d")
    output = tmp_path / "backup.sqlite3"

    backup_database(app.state.settings.database_url, output)

    with closing(sqlite3.connect(output)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
        ciphertext = connection.execute(
            "SELECT contact_ciphertext FROM messages WHERE id = ?", (message.id,)
        ).fetchone()[0]
        assert ciphertext != b"private-contact@example.com"


def test_admin_can_retry_notification_but_csrf_is_required(client, app, db_session):
    csrf = authenticate(client, db_session, app)
    message, outbox = add_pending_message(db_session, app, "e")
    outbox.attempts = 4
    outbox.last_error = "RuntimeError"
    outbox.next_attempt_at = datetime.now(timezone.utc) + timedelta(hours=2)
    db_session.commit()

    rejected = client.post(f"/api/admin/outbox/{message.id}/retry")
    accepted = client.post(
        f"/api/admin/outbox/{message.id}/retry",
        headers={"X-CSRF-Token": csrf},
    )

    assert rejected.status_code == 403
    assert accepted.status_code == 200
    db_session.expire_all()
    stored = db_session.get(Outbox, outbox.id)
    assert stored.attempts == 0
    assert stored.last_error is None
    assert stored.next_attempt_at <= datetime.now(timezone.utc).replace(tzinfo=None)


def test_admin_detail_exposes_notification_status_without_email_secrets(
    client, app, db_session
):
    authenticate(client, db_session, app)
    message, outbox = add_pending_message(db_session, app, "f")
    outbox.attempts = 2
    outbox.last_error = "RuntimeError"
    db_session.commit()

    response = client.get(f"/api/admin/messages/{message.id}")

    assert response.status_code == 200
    notification = response.json()["notification"]
    assert notification["attempts"] == 2
    assert notification["last_error"] == "RuntimeError"
    assert "smtp_password" not in response.text
