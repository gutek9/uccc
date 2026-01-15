"""create cost entries

Revision ID: 001
Revises: 
Create Date: 2024-09-02 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("account_name", sa.String(), nullable=True),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("cost", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "date",
            "provider",
            "account_id",
            "service",
            "region",
            "currency",
            name="uq_cost_entry_identity",
        ),
    )
    op.create_index("ix_cost_entries_date", "cost_entries", ["date"])
    op.create_index("ix_cost_entries_provider", "cost_entries", ["provider"])
    op.create_index("ix_cost_entries_account_id", "cost_entries", ["account_id"])
    op.create_index("ix_cost_entries_service", "cost_entries", ["service"])
    op.create_index("idx_cost_entries_date_provider", "cost_entries", ["date", "provider"])


def downgrade() -> None:
    op.drop_index("idx_cost_entries_date_provider", table_name="cost_entries")
    op.drop_index("ix_cost_entries_service", table_name="cost_entries")
    op.drop_index("ix_cost_entries_account_id", table_name="cost_entries")
    op.drop_index("ix_cost_entries_provider", table_name="cost_entries")
    op.drop_index("ix_cost_entries_date", table_name="cost_entries")
    op.drop_table("cost_entries")
