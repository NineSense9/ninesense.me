from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..admin_models import AdminNotification
from .sessions import as_utc


ALLOWED_SEVERITIES = frozenset({"info", "warning", "critical"})


def create_notification(
    db: Session,
    *,
    severity: str,
    category: str,
    title: str,
    message: str,
    now: datetime | None = None,
) -> AdminNotification:
    if severity not in ALLOWED_SEVERITIES:
        raise ValueError("notification severity is invalid")
    normalized_category = category.strip()
    normalized_title = title.strip()
    normalized_message = message.strip()
    if not normalized_category or len(normalized_category) > 32:
        raise ValueError("notification category is invalid")
    if not normalized_title or len(normalized_title) > 120:
        raise ValueError("notification title is invalid")
    if not normalized_message or len(normalized_message) > 500:
        raise ValueError("notification message is invalid")
    row = AdminNotification(
        severity=severity,
        category=normalized_category,
        title=normalized_title,
        message=normalized_message,
        created_at=as_utc(now or datetime.now(timezone.utc)),
    )
    db.add(row)
    return row


def create_notification_once(
    db: Session,
    *,
    severity: str,
    category: str,
    title: str,
    message: str,
    now: datetime | None = None,
    window: timedelta = timedelta(minutes=15),
) -> AdminNotification:
    current_time = as_utc(now or datetime.now(timezone.utc))
    existing = db.scalar(
        select(AdminNotification)
        .where(
            AdminNotification.category == category.strip(),
            AdminNotification.title == title.strip(),
            AdminNotification.created_at >= current_time - window,
        )
        .order_by(AdminNotification.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        return existing
    return create_notification(
        db,
        severity=severity,
        category=category,
        title=title,
        message=message,
        now=current_time,
    )
