"""Persist individual strengthening-plan checkboxes."""
from alembic import op
import sqlalchemy as sa

revision = "0004_study_plan"
down_revision = "0003_study_record"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "study_plan_checks",
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admins.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("task_id", sa.String(80), primary_key=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("study_plan_checks")
