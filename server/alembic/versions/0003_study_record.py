"""Add study planning, focus timing, history, and exam events."""

from alembic import op
import sqlalchemy as sa


revision = "0003_study_record"
down_revision = "0002_admin_foundation"
branch_labels = None
depends_on = None


SUBJECT_CHECK = (
    "subject IS NOT NULL AND subject IN ('math', '408', 'english', 'politics')"
)


def upgrade() -> None:
    op.create_table(
        "study_schedule_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("task_kind", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(16)),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6",
            name="ck_study_schedule_weekday",
        ),
        sa.CheckConstraint(
            "task_kind IN ('study', 'rest')",
            name="ck_study_schedule_task_kind",
        ),
        sa.CheckConstraint(
            f"((task_kind = 'study' AND {SUBJECT_CHECK}) OR "
            "(task_kind = 'rest' AND subject IS NULL))",
            name="ck_study_schedule_subject",
        ),
        sa.CheckConstraint(
            "end_time > start_time",
            name="ck_study_schedule_time_order",
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="ck_study_schedule_effective_range",
        ),
        sa.CheckConstraint(
            "position BETWEEN 0 AND 10000",
            name="ck_study_schedule_position",
        ),
    )
    op.create_index(
        "ix_study_schedule_entries_weekday",
        "study_schedule_entries",
        ["weekday"],
    )
    op.create_index(
        "ix_study_schedule_entries_effective_from",
        "study_schedule_entries",
        ["effective_from"],
    )
    op.create_index(
        "ix_study_schedule_entries_active",
        "study_schedule_entries",
        ["active"],
    )

    op.create_table(
        "study_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("study_date", sa.Date(), nullable=False),
        sa.Column("reflection", sa.Text(), nullable=False),
        sa.Column("generated_from", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_study_days_study_date",
        "study_days",
        ["study_date"],
        unique=True,
    )

    op.create_table(
        "study_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "day_id",
            sa.Integer(),
            sa.ForeignKey("study_days.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_kind", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(16)),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "task_kind IN ('study', 'rest')",
            name="ck_study_task_kind",
        ),
        sa.CheckConstraint(
            f"((task_kind = 'study' AND {SUBJECT_CHECK}) OR "
            "(task_kind = 'rest' AND subject IS NULL))",
            name="ck_study_task_subject",
        ),
        sa.CheckConstraint(
            "end_time > start_time",
            name="ck_study_task_time_order",
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', "
            "'incomplete', 'cancelled')",
            name="ck_study_task_status",
        ),
        sa.CheckConstraint(
            "position BETWEEN 0 AND 10000",
            name="ck_study_task_position",
        ),
    )
    op.create_index("ix_study_tasks_day_id", "study_tasks", ["day_id"])
    op.create_index("ix_study_tasks_status", "study_tasks", ["status"])

    op.create_table(
        "focus_timers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(16)),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("preset_kind", sa.String(16), nullable=False),
        sa.Column("focus_seconds", sa.Integer(), nullable=False),
        sa.Column("break_seconds", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.Column(
            "accumulated_pause_seconds",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("admin_id", name="uq_focus_timers_admin_id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_focus_timers_idempotency_key",
        ),
        sa.CheckConstraint(
            "phase IN ('focus', 'break')",
            name="ck_focus_timer_phase",
        ),
        sa.CheckConstraint(
            "preset_kind IN ('25_5', '50_10', 'custom', 'break')",
            name="ck_focus_timer_preset_kind",
        ),
        sa.CheckConstraint(
            f"((phase = 'focus' AND {SUBJECT_CHECK}) OR "
            "(phase = 'break' AND subject IS NULL))",
            name="ck_focus_timer_subject",
        ),
        sa.CheckConstraint(
            "((phase = 'focus' AND focus_seconds BETWEEN 60 AND 14400 "
            "AND break_seconds BETWEEN 0 AND 3600) OR "
            "(phase = 'break' AND focus_seconds = 0 "
            "AND break_seconds BETWEEN 60 AND 3600))",
            name="ck_focus_timer_seconds",
        ),
        sa.CheckConstraint(
            "state IN ('running', 'paused')",
            name="ck_focus_timer_state",
        ),
        sa.CheckConstraint(
            "accumulated_pause_seconds >= 0",
            name="ck_focus_timer_pause_seconds",
        ),
        sqlite_autoincrement=True,
    )

    op.create_table(
        "focus_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_timer_id", sa.Integer(), unique=True),
        sa.Column("subject", sa.String(16), nullable=False),
        sa.Column("planned_seconds", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_seconds", sa.Integer(), nullable=False),
        sa.Column("completion_kind", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("correction_reason", sa.String(160)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            SUBJECT_CHECK,
            name="ck_focus_session_subject",
        ),
        sa.CheckConstraint(
            "planned_seconds BETWEEN 60 AND 43200",
            name="ck_focus_session_planned_seconds",
        ),
        sa.CheckConstraint(
            "effective_seconds BETWEEN 0 AND 43200",
            name="ck_focus_session_effective_seconds",
        ),
        sa.CheckConstraint(
            "ended_at >= started_at",
            name="ck_focus_session_time_order",
        ),
        sa.CheckConstraint(
            "completion_kind IN ('completed', 'early_saved', 'manual', "
            "'corrected')",
            name="ck_focus_session_completion_kind",
        ),
        sa.CheckConstraint(
            "source IN ('timer', 'manual')",
            name="ck_focus_session_source",
        ),
        sa.CheckConstraint(
            "source = 'timer' OR correction_reason IS NOT NULL",
            name="ck_focus_session_manual_reason",
        ),
    )
    op.create_index(
        "ix_focus_sessions_admin_id",
        "focus_sessions",
        ["admin_id"],
    )
    op.create_index(
        "ix_focus_sessions_subject",
        "focus_sessions",
        ["subject"],
    )
    op.create_index(
        "ix_focus_sessions_started_at",
        "focus_sessions",
        ["started_at"],
    )

    op.create_table(
        "exam_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("date_status", sa.String(16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("countdown_target", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "date_status IN ('estimated', 'confirmed')",
            name="ck_exam_event_date_status",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_exam_event_date_range",
        ),
        sa.CheckConstraint(
            "position BETWEEN 0 AND 10000",
            name="ck_exam_event_position",
        ),
    )
    op.create_index("ix_exam_events_kind", "exam_events", ["kind"])
    op.create_index(
        "ix_exam_events_start_date",
        "exam_events",
        ["start_date"],
    )
    op.create_index("ix_exam_events_active", "exam_events", ["active"])
    op.create_index(
        "uq_exam_events_active_countdown_target",
        "exam_events",
        ["countdown_target"],
        unique=True,
        sqlite_where=sa.text("countdown_target = 1 AND active = 1"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_exam_events_active_countdown_target",
        table_name="exam_events",
    )
    op.drop_index("ix_exam_events_active", table_name="exam_events")
    op.drop_index("ix_exam_events_start_date", table_name="exam_events")
    op.drop_index("ix_exam_events_kind", table_name="exam_events")
    op.drop_table("exam_events")

    op.drop_index("ix_focus_sessions_started_at", table_name="focus_sessions")
    op.drop_index("ix_focus_sessions_subject", table_name="focus_sessions")
    op.drop_index("ix_focus_sessions_admin_id", table_name="focus_sessions")
    op.drop_table("focus_sessions")

    op.drop_table("focus_timers")

    op.drop_index("ix_study_tasks_status", table_name="study_tasks")
    op.drop_index("ix_study_tasks_day_id", table_name="study_tasks")
    op.drop_table("study_tasks")

    op.drop_index("ix_study_days_study_date", table_name="study_days")
    op.drop_table("study_days")

    op.drop_index(
        "ix_study_schedule_entries_active",
        table_name="study_schedule_entries",
    )
    op.drop_index(
        "ix_study_schedule_entries_effective_from",
        table_name="study_schedule_entries",
    )
    op.drop_index(
        "ix_study_schedule_entries_weekday",
        table_name="study_schedule_entries",
    )
    op.drop_table("study_schedule_entries")
