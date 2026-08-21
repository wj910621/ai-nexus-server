"""Add local_models table for local AI model registry (Task 15).

Revision ID: 005
Revises: 004
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "local_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=32), nullable=False),
        sa.Column("repo_id", sa.String(length=256), nullable=False),
        sa.Column("local_path", sa.String(length=512), nullable=True),
        sa.Column("size_mb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_downloaded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_local_models_name",
        "local_models",
        ["name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_local_models_name", table_name="local_models")
    op.drop_table("local_models")
