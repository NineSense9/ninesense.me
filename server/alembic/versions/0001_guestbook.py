"""Create the guestbook schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001_guestbook"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("nickname", sa.String(24), nullable=False),
        sa.Column("contact_type", sa.String(16)),
        sa.Column("contact_nonce", sa.LargeBinary()),
        sa.Column("contact_ciphertext", sa.LargeBinary()),
        sa.Column("contact_key_version", sa.Integer()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("handled_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("reply", sa.Text()),
        sa.Column("reply_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_kind", "messages", ["kind"])
    op.create_index("ix_messages_status", "messages", ["status"])
    op.create_index("ix_messages_published_at", "messages", ["published_at"])
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "admin_sessions",
        sa.Column("id_hash", sa.String(64), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"]
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "message_id",
            sa.String(32),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(200)),
    )
    op.create_index("ix_outbox_next_attempt_at", "outbox", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_next_attempt_at", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_table("admins")
    op.drop_index("ix_messages_published_at", table_name="messages")
    op.drop_index("ix_messages_status", table_name="messages")
    op.drop_index("ix_messages_kind", table_name="messages")
    op.drop_table("messages")

