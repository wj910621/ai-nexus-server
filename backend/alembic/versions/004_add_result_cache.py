"""Add result_cache table for AI result caching (Task 9).

Revision ID: 004
Revises: 003
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "result_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("engine_type", sa.String(length=32), nullable=False),
        sa.Column("result_payload", sa.Text(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cache_key"),
    )
    # Hot lookup indexes
    op.create_index(
        "ix_result_cache_cache_key",
        "result_cache",
        ["cache_key"],
    )
    op.create_index(
        "ix_result_cache_user_id",
        "result_cache",
        ["user_id"],
    )
    op.create_index(
        "ix_result_cache_engine_type",
        "result_cache",
        ["engine_type"],
    )
    op.create_index(
        "ix_result_cache_expires_at",
        "result_cache",
        ["expires_at"],
    )
    # Composite: lookup by (cache_key, user_id) for per-user cache isolation
    op.create_index(
        "ix_result_cache_key_user",
        "result_cache",
        ["cache_key", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_result_cache_key_user", table_name="result_cache")
    op.drop_index("ix_result_cache_expires_at", table_name="result_cache")
    op.drop_index("ix_result_cache_engine_type", table_name="result_cache")
    op.drop_index("ix_result_cache_user_id", table_name="result_cache")
    op.drop_index("ix_result_cache_cache_key", table_name="result_cache")
    op.drop_table("result_cache")
