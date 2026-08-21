"""Record explicit digital-service purchase consent.

Revision ID: 012
Revises: 011
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_intent_id", sa.String(length=200), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=False),
        sa.Column("terms_version", sa.String(length=20), nullable=False),
        sa.Column("refund_policy_version", sa.String(length=20), nullable=False),
        sa.Column("terms_accepted", sa.Boolean(), nullable=False),
        sa.Column("digital_service_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_intent_id"),
    )
    op.create_index("ix_purchase_consents_user_id", "purchase_consents", ["user_id"])
    op.create_index("ix_purchase_consents_payment_intent_id", "purchase_consents", ["payment_intent_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_consents_payment_intent_id", table_name="purchase_consents")
    op.drop_index("ix_purchase_consents_user_id", table_name="purchase_consents")
    op.drop_table("purchase_consents")
