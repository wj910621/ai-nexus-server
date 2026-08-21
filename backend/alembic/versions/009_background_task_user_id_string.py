"""Store background task user IDs without collapsing UUID users.

Revision ID: 009
Revises: 008_add_training_dataset
"""
from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008_add_training_dataset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "background_tasks",
            "user_id",
            existing_type=sa.Integer(),
            type_=sa.String(length=36),
            existing_nullable=False,
            postgresql_using="user_id::text",
        )
    else:
        with op.batch_alter_table("background_tasks") as batch_op:
            batch_op.alter_column(
                "user_id",
                existing_type=sa.Integer(),
                type_=sa.String(length=36),
                existing_nullable=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "background_tasks",
            "user_id",
            existing_type=sa.String(length=36),
            type_=sa.Integer(),
            existing_nullable=False,
            postgresql_using="user_id::integer",
        )
    else:
        with op.batch_alter_table("background_tasks") as batch_op:
            batch_op.alter_column(
                "user_id",
                existing_type=sa.String(length=36),
                type_=sa.Integer(),
                existing_nullable=False,
            )
