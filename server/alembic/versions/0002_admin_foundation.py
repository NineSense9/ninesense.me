"""Add the administration platform foundation schema."""

from alembic import op
import sqlalchemy as sa


revision = "0002_admin_foundation"
down_revision = "0001_guestbook"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM admin_sessions"))

    with op.batch_alter_table("admins") as batch:
        batch.add_column(sa.Column("totp_secret_nonce", sa.LargeBinary()))
        batch.add_column(sa.Column("totp_secret_ciphertext", sa.LargeBinary()))
        batch.add_column(sa.Column("totp_secret_key_version", sa.Integer()))
        batch.add_column(sa.Column("totp_enabled_at", sa.DateTime(timezone=True)))

    with op.batch_alter_table("admin_sessions", recreate="always") as batch:
        batch.add_column(
            sa.Column("public_id", sa.String(32), nullable=False)
        )
        batch.add_column(
            sa.Column("client_label", sa.String(80), nullable=False)
        )
        batch.add_column(
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)
        )
        batch.add_column(
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False)
        )
        batch.add_column(
            sa.Column("last_reauthenticated_at", sa.DateTime(timezone=True))
        )
        batch.create_index(
            "ix_admin_sessions_public_id", ["public_id"], unique=True
        )

    op.create_table(
        "admin_login_challenges",
        sa.Column("id_hash", sa.String(64), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("secret_nonce", sa.LargeBinary()),
        sa.Column("secret_ciphertext", sa.LargeBinary()),
        sa.Column("secret_key_version", sa.Integer()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_admin_login_challenges_expires_at",
        "admin_login_challenges",
        ["expires_at"],
    )

    op.create_table(
        "admin_recovery_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_admin_recovery_codes_admin_id",
        "admin_recovery_codes",
        ["admin_id"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("target_type", sa.String(32)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_admin_id", "audit_events", ["admin_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index(
        "ix_audit_events_created_at", "audit_events", ["created_at"]
    )

    op.create_table(
        "admin_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_admin_notifications_severity", "admin_notifications", ["severity"]
    )
    op.create_index(
        "ix_admin_notifications_category", "admin_notifications", ["category"]
    )
    op.create_index(
        "ix_admin_notifications_created_at",
        "admin_notifications",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_notifications_created_at", table_name="admin_notifications"
    )
    op.drop_index(
        "ix_admin_notifications_category", table_name="admin_notifications"
    )
    op.drop_index(
        "ix_admin_notifications_severity", table_name="admin_notifications"
    )
    op.drop_table("admin_notifications")

    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_admin_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index(
        "ix_admin_recovery_codes_admin_id", table_name="admin_recovery_codes"
    )
    op.drop_table("admin_recovery_codes")

    op.drop_index(
        "ix_admin_login_challenges_expires_at",
        table_name="admin_login_challenges",
    )
    op.drop_table("admin_login_challenges")

    with op.batch_alter_table("admin_sessions", recreate="always") as batch:
        batch.drop_index("ix_admin_sessions_public_id")
        batch.drop_column("last_reauthenticated_at")
        batch.drop_column("last_seen_at")
        batch.drop_column("created_at")
        batch.drop_column("client_label")
        batch.drop_column("public_id")

    with op.batch_alter_table("admins") as batch:
        batch.drop_column("totp_enabled_at")
        batch.drop_column("totp_secret_key_version")
        batch.drop_column("totp_secret_ciphertext")
        batch.drop_column("totp_secret_nonce")
