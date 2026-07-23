import asyncio
from contextlib import closing
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import logging
import os
from pathlib import Path
import smtplib
import sqlite3
import ssl
from typing import Callable

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url

from ..config import Settings
from ..models import AdminSession, Message, Outbox
from .sessions import as_utc


LOGGER = logging.getLogger(__name__)
RETRY_DELAYS = (1, 5, 30, 120, 720)
EmailSender = Callable[[Settings, str, str], None]


def render_notification(settings: Settings, message: Message) -> tuple[str, str]:
    kind = "public" if message.kind == "public" else "private"
    subject = f"[NineSense] New {kind} message"
    summary = message.content.replace("\r", " ").replace("\n", " ")[:160]
    body = "\n".join(
        [
            f"Type: {kind}",
            f"Nickname: {message.nickname}",
            f"Submitted: {as_utc(message.submitted_at).isoformat()}",
            f"Summary: {summary}",
            f"Admin: {settings.public_admin_url}",
        ]
    )
    return subject, body


def send_smtp(settings: Settings, subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.notification_to:
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_username
    message["To"] = settings.notification_to
    message.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        settings.smtp_host,
        settings.smtp_port,
        timeout=15,
        context=context,
    ) as smtp:
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def process_outbox_once(
    session_factory,
    settings: Settings,
    *,
    sender: EmailSender = send_smtp,
    now: datetime | None = None,
) -> int:
    now = as_utc(now or datetime.now(timezone.utc))
    with session_factory() as db:
        due = list(
            db.scalars(
                select(Outbox)
                .where(
                    Outbox.sent_at.is_(None),
                    Outbox.attempts < len(RETRY_DELAYS),
                    Outbox.next_attempt_at <= now,
                )
                .order_by(Outbox.next_attempt_at, Outbox.id)
                .limit(20)
            )
        )

        for item in due:
            message = db.get(Message, item.message_id)
            if message is None:
                db.delete(item)
                db.commit()
                continue
            subject, body = render_notification(settings, message)
            try:
                sender(settings, subject, body)
            except Exception as error:
                item.attempts += 1
                item.last_error = type(error).__name__[:200]
                delay_index = min(item.attempts - 1, len(RETRY_DELAYS) - 1)
                item.next_attempt_at = now + timedelta(minutes=RETRY_DELAYS[delay_index])
            else:
                item.sent_at = now
                item.last_error = None
            db.commit()
        return len(due)


def cleanup_records(
    session_factory,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    now = as_utc(now or datetime.now(timezone.utc))
    rejected_cutoff = now - timedelta(days=30)
    sent_cutoff = now - timedelta(days=30)
    with session_factory() as db:
        sessions = db.execute(
            delete(AdminSession).where(AdminSession.expires_at < now)
        ).rowcount
        messages = db.execute(
            delete(Message).where(
                Message.status == "rejected",
                Message.reviewed_at.is_not(None),
                Message.reviewed_at < rejected_cutoff,
            )
        ).rowcount
        outbox = db.execute(
            delete(Outbox).where(
                Outbox.sent_at.is_not(None),
                Outbox.sent_at < sent_cutoff,
            )
        ).rowcount
        db.commit()
    return {
        "messages": messages or 0,
        "sessions": sessions or 0,
        "outbox": outbox or 0,
    }


def backup_database(database_url: str, output: str | Path) -> Path:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise ValueError("backup-db supports file-backed SQLite databases only")

    source_path = Path(url.database).resolve()
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    temporary_path.unlink(missing_ok=True)

    try:
        with closing(sqlite3.connect(source_path)) as source_connection:
            with closing(sqlite3.connect(temporary_path)) as backup_connection:
                source_connection.backup(backup_connection)
                integrity = backup_connection.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise RuntimeError("backup integrity check failed")
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return output_path


async def outbox_worker(app) -> None:
    while True:
        await asyncio.sleep(15)
        try:
            await asyncio.to_thread(
                process_outbox_once,
                app.state.session_factory,
                app.state.settings,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            LOGGER.warning("outbox worker failed: %s", type(error).__name__)
