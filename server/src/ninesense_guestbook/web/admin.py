from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..domain.messages import MessageKind, MessageStatus, require_transition
from ..models import Message, Outbox
from ..services.audit import record_audit
from ..services.crypto import EncryptedContact
from ..services.sessions import (
    as_utc,
    require_csrf,
    require_recent_reauthentication,
    require_session,
)
from .public import decode_cursor, encode_cursor
from .schemas import clean_text


router = APIRouter(prefix="/api/admin/messages", tags=["admin-messages"])
outbox_router = APIRouter(prefix="/api/admin/outbox", tags=["admin-outbox"])


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pending", "published", "handled", "archived", "rejected"]
    reply: str | None = None

    @field_validator("reply")
    @classmethod
    def validate_reply(cls, value: str | None) -> str | None:
        return clean_text(value, 2, 500, True) if value is not None else None


class ReplyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str

    @field_validator("reply")
    @classmethod
    def validate_reply(cls, value: str) -> str:
        return clean_text(value, 2, 500, True)


def get_message(db: Session, message_id: str) -> Message:
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="留言不存在。")
    return message


def reveal_contact(request: Request, message: Message) -> str | None:
    if message.contact_ciphertext is None:
        return None
    if message.contact_nonce is None or message.contact_key_version is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="联系方式数据不完整。",
        )
    return request.app.state.contact_cipher.decrypt(
        EncryptedContact(
            nonce=message.contact_nonce,
            ciphertext=message.contact_ciphertext,
            key_version=message.contact_key_version,
        )
    )


def summary(message: Message) -> dict[str, object]:
    return {
        "id": message.id,
        "kind": message.kind,
        "status": message.status,
        "nickname": message.nickname,
        "content_preview": message.content[:160],
        "submitted_at": as_utc(message.submitted_at).isoformat(),
        "has_contact": message.contact_ciphertext is not None,
        "has_reply": message.reply is not None,
    }


def detail(request: Request, db: Session, message: Message) -> dict[str, object]:
    notification = db.scalar(select(Outbox).where(Outbox.message_id == message.id))
    notification_status = None
    if notification is not None:
        notification_status = {
            "attempts": notification.attempts,
            "next_attempt_at": as_utc(notification.next_attempt_at).isoformat(),
            "sent_at": (
                as_utc(notification.sent_at).isoformat() if notification.sent_at else None
            ),
            "last_error": notification.last_error,
        }
    return {
        **summary(message),
        "content": message.content,
        "contact_type": message.contact_type,
        "reviewed_at": (
            as_utc(message.reviewed_at).isoformat() if message.reviewed_at else None
        ),
        "published_at": (
            as_utc(message.published_at).isoformat() if message.published_at else None
        ),
        "handled_at": (
            as_utc(message.handled_at).isoformat() if message.handled_at else None
        ),
        "archived_at": (
            as_utc(message.archived_at).isoformat() if message.archived_at else None
        ),
        "reply": message.reply,
        "reply_at": as_utc(message.reply_at).isoformat() if message.reply_at else None,
        "updated_at": as_utc(message.updated_at).isoformat(),
        "notification": notification_status,
    }


@router.get("")
def list_messages(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    kind: Literal["public", "private"] | None = None,
    q: str | None = Query(default=None, max_length=100),
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        criteria = []
        if status_filter is not None:
            try:
                MessageStatus(status_filter)
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="未知的留言状态。",
                ) from error
            criteria.append(Message.status == status_filter)
        if kind is not None:
            criteria.append(Message.kind == kind)
        if q is not None and q.strip():
            escaped = (
                q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            criteria.append(
                or_(
                    Message.nickname.ilike(pattern, escape="\\"),
                    Message.content.ilike(pattern, escape="\\"),
                )
            )
        if cursor is not None:
            cursor_time, cursor_id = decode_cursor(cursor)
            criteria.append(
                or_(
                    Message.submitted_at < cursor_time,
                    and_(Message.submitted_at == cursor_time, Message.id < cursor_id),
                )
            )
        statement = (
            select(Message)
            .where(*criteria)
            .order_by(Message.submitted_at.desc(), Message.id.desc())
            .limit(limit + 1)
        )
        records = list(db.scalars(statement))
        has_more = len(records) > limit
        visible = records[:limit]
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = encode_cursor(last.submitted_at, last.id)
        return {
            "items": [summary(message) for message in visible],
            "next_cursor": next_cursor,
        }


@router.get("/{message_id}")
def get_message_detail(message_id: str, request: Request) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        require_session(request, db)
        return detail(request, db, get_message(db, message_id))


@router.post("/{message_id}/contact")
def get_message_contact(message_id: str, request: Request) -> dict[str, str | None]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        require_recent_reauthentication(current)
        message = get_message(db, message_id)
        contact = reveal_contact(request, message)
        record_audit(
            db,
            action="message.contact_viewed",
            outcome="success",
            admin_id=current.admin.id,
            target_type="message",
            target_id=message.id,
        )
        db.commit()
        return {
            "contact_type": message.contact_type,
            "contact": contact,
        }


@router.patch("/{message_id}/status")
def change_status(
    message_id: str,
    payload: StatusUpdate,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        message = get_message(db, message_id)
        try:
            require_transition(
                MessageKind(message.kind),
                MessageStatus(message.status),
                MessageStatus(payload.status),
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前状态不能执行这个操作。",
            ) from error

        now = datetime.now(timezone.utc)
        message.status = payload.status
        message.reviewed_at = now
        if payload.status == "published":
            message.published_at = now
            if payload.reply is not None:
                message.reply = payload.reply
                message.reply_at = now
        elif payload.status == "handled":
            message.handled_at = now
        elif payload.status == "archived":
            message.archived_at = now
        db.commit()
        db.refresh(message)
        return detail(request, db, message)


@router.put("/{message_id}/reply")
def update_reply(
    message_id: str,
    payload: ReplyUpdate,
    request: Request,
) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        message = get_message(db, message_id)
        if message.kind != "public" or message.status != "published":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="只有已公开留言可以添加公开回复。",
            )
        message.reply = payload.reply
        message.reply_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(message)
        return detail(request, db, message)


@router.delete("/{message_id}/reply")
def remove_reply(message_id: str, request: Request) -> dict[str, object]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        message = get_message(db, message_id)
        if message.kind != "public" or message.status != "published":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="只有已公开留言可以修改公开回复。",
            )
        message.reply = None
        message.reply_at = None
        db.commit()
        db.refresh(message)
        return detail(request, db, message)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(message_id: str, request: Request, response: Response) -> None:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        message = get_message(db, message_id)
        db.delete(message)
        db.commit()


@outbox_router.post("/{message_id}/retry")
def retry_notification(message_id: str, request: Request) -> dict[str, str]:
    with request.app.state.session_factory() as db:
        current = require_session(request, db)
        require_csrf(request, current)
        item = db.scalar(select(Outbox).where(Outbox.message_id == message_id))
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有找到对应的邮件提醒。",
            )
        if item.sent_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="这封提醒已经发送成功。",
            )
        item.attempts = 0
        item.last_error = None
        item.next_attempt_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "scheduled"}
