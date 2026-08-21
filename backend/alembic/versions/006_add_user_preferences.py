"""add user preferences columns

Revision ID: 006_user_prefs
Revises: 005
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa


revision = "006_user_prefs"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "first_launch_completed", sa.Boolean(),
        nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column(
        "preferred_provider", sa.String(length=20),
        nullable=False, server_default="cloud"))
    op.add_column("users", sa.Column(
        "telemetry_enabled", sa.Boolean(),
        nullable=False, server_default=sa.text("true")))
    op.add_column("users", sa.Column(
        "cloud_sync_enabled", sa.Boolean(),
        nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("users", "cloud_sync_enabled")
    op.drop_column("users", "telemetry_enabled")
    op.drop_column("users", "preferred_provider")
    op.drop_column("users", "first_launch_completed")
