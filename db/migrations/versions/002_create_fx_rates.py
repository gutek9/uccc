"""create fx rates

Revision ID: 002
Revises: 001
Create Date: 2025-01-22 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("base_currency", sa.String(), nullable=False, server_default=sa.text("'EUR'")),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("date", "currency", name="uq_fx_rate_date_currency"),
    )
    op.create_index("ix_fx_rates_date", "fx_rates", ["date"])
    op.create_index("ix_fx_rates_currency", "fx_rates", ["currency"])
    op.create_index("idx_fx_rates_date_currency", "fx_rates", ["date", "currency"])


def downgrade() -> None:
    op.drop_index("idx_fx_rates_date_currency", table_name="fx_rates")
    op.drop_index("ix_fx_rates_currency", table_name="fx_rates")
    op.drop_index("ix_fx_rates_date", table_name="fx_rates")
    op.drop_table("fx_rates")
