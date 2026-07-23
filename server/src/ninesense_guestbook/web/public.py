import base64
import binascii
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from ..models import Message, Outbox
from .schemas import MessageCreate, PublicFeed, PublicMessage, classify_contact


router = APIRouter(prefix="/api/guestbook", tags=["guestbook"])


def encode_cursor(published_at: datetime, message_id: str) -> str:
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    timestamp = published_at.astimezone(timezone.utc).isoformat()
    raw = f"{timestamp}|{message_id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(
            (cursor + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        ).decode("utf-8")
        timestamp_text, message_id = raw.rsplit("|", 1)
        timestamp = datetime.fromisoformat(timestamp_text)
        if timestamp.tzinfo is None or len(message_id) != 32:
            raise ValueError
        return timestamp.astimezone(timezone.utc), message_id
    except (ValueError, UnicodeError, binascii.Error) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的分页位置。",
        ) from error


@router.get("/messages", response_model=PublicFeed)
def list_public_messages(
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=10, ge=1, le=10),
) -> PublicFeed:
    criteria = [
        Message.kind == "public",
        Message.status == "published",
        Message.published_at.is_not(None),
    ]
    if cursor is not None:
        cursor_time, cursor_id = decode_cursor(cursor)
        criteria.append(
            or_(
                Message.published_at < cursor_time,
                and_(
                    Message.published_at == cursor_time,
                    Message.id < cursor_id,
                ),
            )
        )

    statement = (
        select(Message)
        .where(*criteria)
        .order_by(Message.published_at.desc(), Message.id.desc())
        .limit(limit + 1)
    )
    with request.app.state.session_factory() as session:
        records = list(session.scalars(statement))

    has_more = len(records) > limit
    visible = records[:limit]
    next_cursor = None
    if has_more and visible:
        last = visible[-1]
        next_cursor = encode_cursor(last.published_at, last.id)

    items = [
        PublicMessage(
            id=message.id,
            nickname=message.nickname,
            date=message.published_at.date().isoformat(),
            content=message.content,
            reply=message.reply,
            reply_date=(message.reply_at.date().isoformat() if message.reply_at else None),
        )
        for message in visible
    ]
    return PublicFeed(items=items, next_cursor=next_cursor)


@router.post("/messages", status_code=status.HTTP_202_ACCEPTED)
def submit_message(payload: MessageCreate, request: Request) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    elapsed = now.timestamp() - payload.form_started_at
    if payload.website or elapsed < 2:
        return {"status": "received"}

    session_factory = request.app.state.session_factory
    with session_factory() as session:
        existing = session.scalar(
            select(Message.id).where(Message.idempotency_key == payload.idempotency_key)
        )
        if existing is not None:
            return {"status": "received"}

    client_ip = request.client.host if request.client is not None else "unknown"
    if not request.app.state.submission_limiter.allow(client_ip, now):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="提交得有点频繁，请稍后再试。",
        )

    contact_type = classify_contact(payload.contact)
    contact_nonce = None
    contact_ciphertext = None
    contact_key_version = None
    if payload.contact is not None:
        encrypted = request.app.state.contact_cipher.encrypt(payload.contact)
        contact_nonce = encrypted.nonce
        contact_ciphertext = encrypted.ciphertext
        contact_key_version = encrypted.key_version

    message = Message(
        kind=payload.kind,
        nickname=payload.nickname,
        contact_type=contact_type,
        contact_nonce=contact_nonce,
        contact_ciphertext=contact_ciphertext,
        contact_key_version=contact_key_version,
        content=payload.content,
        idempotency_key=payload.idempotency_key,
    )

    with session_factory() as session:
        try:
            session.add(message)
            session.flush()
            session.add(Outbox(message_id=message.id))
            session.commit()
        except IntegrityError:
            session.rollback()
            duplicate = session.scalar(
                select(Message.id).where(
                    Message.idempotency_key == payload.idempotency_key
                )
            )
            if duplicate is None:
                raise

    return {"status": "received"}
