"""Add training_dataset and dataset_item tables (P3).

Revision ID: 008_add_training_dataset
Revises: 007
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa


revision = "008_add_training_dataset"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("character_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="drafting"),
        sa.Column("caption_mode", sa.String(10), nullable=False, server_default="auto"),
        sa.Column("trigger_word", sa.String(50), nullable=False, server_default=""),
        sa.Column("image_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
    )
    op.create_table(
        "dataset_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("training_datasets.id"), nullable=False, index=True),
        sa.Column("image_path", sa.String(500), nullable=False),
        sa.Column("caption", sa.Text, nullable=False, server_default=""),
        sa.Column("caption_source", sa.String(10), nullable=False, server_default="manual"),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    # Character 表新增 lora_training_status / lora_model_path 已在 P1/P2 模型层加好，
    # 这里仅保证列存在（幂等）
    op.execute(
        "ALTER TABLE characters ADD COLUMN IF NOT EXISTS lora_training_status "
        "VARCHAR(20) DEFAULT 'none'"
    )
    op.execute(
        "ALTER TABLE characters ADD COLUMN IF NOT EXISTS lora_model_path VARCHAR(500) DEFAULT ''"
    )


def downgrade() -> None:
    op.drop_table("dataset_items")
    op.drop_table("training_datasets")
