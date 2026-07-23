from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ninesense_guestbook.admin_models import AdminNotification, AuditEvent
from ninesense_guestbook.models import Admin, AdminSession


def test_admin_foundation_rows_persist(db_session):
    now = datetime.now(timezone.utc)
    admin = Admin(username="owner", password_hash="hash", active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add_all(
        [
            AdminSession(
                id_hash="a" * 64,
                public_id="b" * 32,
                admin_id=admin.id,
                csrf_hash="c" * 64,
                client_label="Chrome / Windows",
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(hours=8),
            ),
            AuditEvent(
                admin_id=admin.id,
                action="session.login",
                outcome="success",
            ),
            AdminNotification(
                severity="info",
                category="security",
                title="新会话",
                message="Chrome / Windows",
            ),
        ]
    )
    db_session.commit()

    assert db_session.scalar(select(AdminSession.public_id)) == "b" * 32
    assert db_session.scalar(select(AuditEvent.action)) == "session.login"
    assert db_session.scalar(select(AdminNotification.title)) == "新会话"
