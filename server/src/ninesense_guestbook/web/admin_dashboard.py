import base64
import binascii
from datetime import datetime, timezone
import json

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import and_, func, or_, select, update

from ..admin_models import AdminNotification, AuditEvent
from ..models import AdminSession, Message
from ..services.sessions import as_utc, require_csrf, require_session


router = APIRouter(prefix="/api/admin", tags=["admin-dashboard"])


def encode_cursor(created_at: datetime, row_id: int) -> str:
    raw = f"{as_utc(created_at).isoformat()}|{row_id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(
            (cursor + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        ).decode("utf-8")
        timestamp_text, row_id_text = raw.rsplit("|", 1)
        timestamp = datetime.fromisoformat(timestamp_text)
        row_id = int(row_id_text)
        if timestamp.tzinfo is None or row_id < 1:
            raise ValueError
        return timestamp.astimezone(timezone.utc), row_id
    except (ValueError, UnicodeError, binascii.Error) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的分页位置。",
        ) from error


@router.get("/dashboard")
def dashboard(request: Request) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        require_session(request, db)
        pending = db.scalar(
            select(func.count()).select_from(Message).where(Message.status == "pending")
        )
        unread = db.scalar(
            select(func.count())
            .select_from(AdminNotification)
            .where(AdminNotification.read_at.is_(None))
        )
        active_sessions = db.scalar(
            select(func.count())
            .select_from(AdminSession)
            .where(AdminSession.expires_at > now)
        )
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(
                    or_(
                        AuditEvent.action.like("session.%"),
                        AuditEvent.action.like("mfa.%"),
                    )
                )
                .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                .limit(5)
            )
        )
        return {
            "pending_interactions": pending or 0,
            "unread_notifications": unread or 0,
            "active_sessions": active_sessions or 0,
            "recent_security_events": [
                {
                    "action": event.action,
                    "outcome": event.outcome,
                    "created_at": as_utc(event.created_at).isoformat(),
                }
                for event in events
            ],
        }


def notification_payload(row: AdminNotification) -> dict[str, object]:
    return {
        "id": row.id,
        "severity": row.severity,
        "category": row.category,
        "title": row.title,
        "message": row.message,
        "created_at": as_utc(row.created_at).isoformat(),
        "read_at": as_utc(row.read_at).isoformat() if row.read_at else None,
    }


@router.get("/notifications")
def list_notifications(
    request: Request,
    unread: bool | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        criteria = []
        if unread is True:
            criteria.append(AdminNotification.read_at.is_(None))
        elif unread is False:
            criteria.append(AdminNotification.read_at.is_not(None))
        if cursor:
            cursor_time, cursor_id = decode_cursor(cursor)
            criteria.append(
                or_(
                    AdminNotification.created_at < cursor_time,
                    and_(
                        AdminNotification.created_at == cursor_time,
                        AdminNotification.id < cursor_id,
                    ),
                )
            )
        rows = list(
            db.scalars(
                select(AdminNotification)
                .where(*criteria)
                .order_by(
                    AdminNotification.created_at.desc(),
                    AdminNotification.id.desc(),
                )
                .limit(limit + 1)
            )
        )
        visible = rows[:limit]
        next_cursor = None
        if len(rows) > limit and visible:
            next_cursor = encode_cursor(visible[-1].created_at, visible[-1].id)
        return {
            "items": [notification_payload(row) for row in visible],
            "next_cursor": next_cursor,
        }


@router.patch(
    "/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
)
def mark_notification_read(notification_id: int, request: Request) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        row = db.get(AdminNotification, notification_id)
        if row is None:
            raise HTTPException(status_code=404, detail="通知不存在。")
        row.read_at = datetime.now(timezone.utc)
        db.commit()


@router.post(
    "/notifications/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
)
def mark_all_notifications_read(request: Request) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        db.execute(
            update(AdminNotification)
            .where(AdminNotification.read_at.is_(None))
            .values(read_at=datetime.now(timezone.utc))
        )
        db.commit()


def audit_payload(row: AuditEvent) -> dict[str, object]:
    return {
        "action": row.action,
        "outcome": row.outcome,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "details": json.loads(row.details_json),
        "created_at": as_utc(row.created_at).isoformat(),
    }


@router.get("/audit")
def list_audit(
    request: Request,
    action: str | None = Query(default=None, max_length=64),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        criteria = []
        if action:
            criteria.append(AuditEvent.action == action)
        if cursor:
            cursor_time, cursor_id = decode_cursor(cursor)
            criteria.append(
                or_(
                    AuditEvent.created_at < cursor_time,
                    and_(
                        AuditEvent.created_at == cursor_time,
                        AuditEvent.id < cursor_id,
                    ),
                )
            )
        rows = list(
            db.scalars(
                select(AuditEvent)
                .where(*criteria)
                .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                .limit(limit + 1)
            )
        )
        visible = rows[:limit]
        next_cursor = None
        if len(rows) > limit and visible:
            next_cursor = encode_cursor(visible[-1].created_at, visible[-1].id)
        return {
            "items": [audit_payload(row) for row in visible],
            "next_cursor": next_cursor,
        }
