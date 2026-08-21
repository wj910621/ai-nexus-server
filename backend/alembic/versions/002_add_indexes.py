"""Add performance indexes for hot query paths.

Revision ID: 002
Revises: 001
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Credit transactions: speed up user balance queries
    op.create_index(
        "ix_credit_transactions_user_id_created_at",
        "credit_transactions",
        ["user_id", "created_at"],
    )

    # Background tasks: speed up user task listing (already has user_id index,
    # add composite for status filter + ordering)
    op.create_index(
        "ix_background_tasks_user_id_status_created",
        "background_tasks",
        ["user_id", "status", "created_at"],
    )

    # Audit logs: speed up actor/action queries
    op.create_index(
        "ix_audit_logs_actor_id_created_at",
        "audit_logs",
        ["actor_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_action_created_at",
        "audit_logs",
        ["action", "created_at"],
    )

    # Users: speed up email verification code lookup
    op.create_index(
        "ix_users_email_verification_code",
        "users",
        ["email_verification_code"],
        postgresql_where=text("email_verification_code IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_email_verification_code", table_name="users")
    op.drop_index("ix_audit_logs_action_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id_created_at", table_name="audit_logs")
    op.drop_index("ix_background_tasks_user_id_status_created", table_name="background_tasks")
    op.drop_index("ix_credit_transactions_user_id_created_at", table_name="credit_transactions")
