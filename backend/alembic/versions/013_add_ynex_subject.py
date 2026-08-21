"""Add a stable Y·NEX subject for shared-account Story records.

Revision ID: 013
Revises: 012
"""
from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("external_subject", sa.String(length=128), nullable=True))
    op.create_index("ix_users_external_subject", "users", ["external_subject"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_external_subject", table_name="users")
    op.drop_column("users", "external_subject")
