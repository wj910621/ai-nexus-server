"""Persist inline workflow executions and storage cleanup outbox.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("workflow_executions") as batch_op:
            batch_op.alter_column(
                "workflow_id",
                existing_type=postgresql.UUID(as_uuid=True),
                nullable=True,
            )
    else:
        op.alter_column(
            "workflow_executions",
            "workflow_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=True,
        )
    op.create_table(
        "pending_storage_deletions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pending_storage_deletions_id", "pending_storage_deletions", ["id"]
    )
    op.create_index(
        "ix_pending_storage_deletions_path", "pending_storage_deletions", ["path"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pending_storage_deletions_path", table_name="pending_storage_deletions"
    )
    op.drop_index(
        "ix_pending_storage_deletions_id", table_name="pending_storage_deletions"
    )
    op.drop_table("pending_storage_deletions")
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("workflow_executions") as batch_op:
            batch_op.alter_column(
                "workflow_id",
                existing_type=postgresql.UUID(as_uuid=True),
                nullable=False,
            )
    else:
        op.alter_column(
            "workflow_executions",
            "workflow_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
        )
