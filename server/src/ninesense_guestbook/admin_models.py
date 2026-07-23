from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import utcnow


class AdminLoginChallenge(Base):
    __tablename__ = "admin_login_challenges"

    id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE")
    )
    purpose: Mapped[str] = mapped_column(String(16))
    secret_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    secret_key_version: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )


class AdminRecoveryCode(Base):
    __tablename__ = "admin_recovery_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    outcome: Mapped[str] = mapped_column(String(16))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
