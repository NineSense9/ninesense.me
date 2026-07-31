from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import utcnow


SUBJECT_CHECK = (
    "subject IS NOT NULL AND subject IN ('math', '408', 'english', 'politics')"
)


class StudyScheduleEntry(Base):
    __tablename__ = "study_schedule_entries"
    __table_args__ = (
        CheckConstraint(
            "weekday BETWEEN 0 AND 6",
            name="ck_study_schedule_weekday",
        ),
        CheckConstraint(
            "task_kind IN ('study', 'rest')",
            name="ck_study_schedule_task_kind",
        ),
        CheckConstraint(
            f"((task_kind = 'study' AND {SUBJECT_CHECK}) OR "
            "(task_kind = 'rest' AND subject IS NULL))",
            name="ck_study_schedule_subject",
        ),
        CheckConstraint(
            "end_time > start_time",
            name="ck_study_schedule_time_order",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="ck_study_schedule_effective_range",
        ),
        CheckConstraint(
            "position BETWEEN 0 AND 10000",
            name="ck_study_schedule_position",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, index=True)
    task_kind: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str | None] = mapped_column(String(16))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_until: Mapped[date | None] = mapped_column(Date)
    position: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class StudyDay(Base):
    __tablename__ = "study_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    study_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    reflection: Mapped[str] = mapped_column(Text, default="")
    generated_from: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class StudyTask(Base):
    __tablename__ = "study_tasks"
    __table_args__ = (
        CheckConstraint(
            "task_kind IN ('study', 'rest')",
            name="ck_study_task_kind",
        ),
        CheckConstraint(
            f"((task_kind = 'study' AND {SUBJECT_CHECK}) OR "
            "(task_kind = 'rest' AND subject IS NULL))",
            name="ck_study_task_subject",
        ),
        CheckConstraint(
            "end_time > start_time",
            name="ck_study_task_time_order",
        ),
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', "
            "'incomplete', 'cancelled')",
            name="ck_study_task_status",
        ),
        CheckConstraint(
            "position BETWEEN 0 AND 10000",
            name="ck_study_task_position",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_id: Mapped[int] = mapped_column(
        ForeignKey("study_days.id", ondelete="CASCADE"), index=True
    )
    task_kind: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str | None] = mapped_column(String(16))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="planned", index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class FocusTimer(Base):
    __tablename__ = "focus_timers"
    __table_args__ = (
        UniqueConstraint("admin_id", name="uq_focus_timers_admin_id"),
        UniqueConstraint(
            "idempotency_key",
            name="uq_focus_timers_idempotency_key",
        ),
        CheckConstraint(
            "phase IN ('focus', 'break')",
            name="ck_focus_timer_phase",
        ),
        CheckConstraint(
            "preset_kind IN ('25_5', '50_10', 'custom', 'break')",
            name="ck_focus_timer_preset_kind",
        ),
        CheckConstraint(
            f"((phase = 'focus' AND {SUBJECT_CHECK}) OR "
            "(phase = 'break' AND subject IS NULL))",
            name="ck_focus_timer_subject",
        ),
        CheckConstraint(
            "((phase = 'focus' AND focus_seconds BETWEEN 60 AND 14400 "
            "AND break_seconds BETWEEN 0 AND 3600) OR "
            "(phase = 'break' AND focus_seconds = 0 "
            "AND break_seconds BETWEEN 60 AND 3600))",
            name="ck_focus_timer_seconds",
        ),
        CheckConstraint(
            "state IN ('running', 'paused')",
            name="ck_focus_timer_state",
        ),
        CheckConstraint(
            "accumulated_pause_seconds >= 0",
            name="ck_focus_timer_pause_seconds",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE")
    )
    subject: Mapped[str | None] = mapped_column(String(16))
    phase: Mapped[str] = mapped_column(String(16))
    preset_kind: Mapped[str] = mapped_column(String(16))
    focus_seconds: Mapped[int] = mapped_column(Integer)
    break_seconds: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    planned_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accumulated_pause_seconds: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class FocusSession(Base):
    __tablename__ = "focus_sessions"
    __table_args__ = (
        CheckConstraint(
            SUBJECT_CHECK,
            name="ck_focus_session_subject",
        ),
        CheckConstraint(
            "planned_seconds BETWEEN 60 AND 43200",
            name="ck_focus_session_planned_seconds",
        ),
        CheckConstraint(
            "effective_seconds BETWEEN 0 AND 43200",
            name="ck_focus_session_effective_seconds",
        ),
        CheckConstraint(
            "ended_at >= started_at",
            name="ck_focus_session_time_order",
        ),
        CheckConstraint(
            "completion_kind IN ('completed', 'early_saved', 'manual', "
            "'corrected')",
            name="ck_focus_session_completion_kind",
        ),
        CheckConstraint(
            "source IN ('timer', 'manual')",
            name="ck_focus_session_source",
        ),
        CheckConstraint(
            "source = 'timer' OR correction_reason IS NOT NULL",
            name="ck_focus_session_manual_reason",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE"), index=True
    )
    source_timer_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    subject: Mapped[str] = mapped_column(String(16), index=True)
    planned_seconds: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_seconds: Mapped[int] = mapped_column(Integer)
    completion_kind: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    correction_reason: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ExamEvent(Base):
    __tablename__ = "exam_events"
    __table_args__ = (
        CheckConstraint(
            "date_status IN ('estimated', 'confirmed')",
            name="ck_exam_event_date_status",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_exam_event_date_range",
        ),
        CheckConstraint(
            "position BETWEEN 0 AND 10000",
            name="ck_exam_event_position",
        ),
        Index(
            "uq_exam_events_active_countdown_target",
            "countdown_target",
            unique=True,
            sqlite_where=text("countdown_target = 1 AND active = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(120))
    date_status: Mapped[str] = mapped_column(String(16))
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(String(500))
    countdown_target: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
