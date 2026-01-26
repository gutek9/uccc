from sqlalchemy import Column, Date, DateTime, Float, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class CostEntry(Base):
    __tablename__ = "cost_entries"

    id = Column(String, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    account_id = Column(String, nullable=False, index=True)
    account_name = Column(String, nullable=True)
    service = Column(String, nullable=False, index=True)
    region = Column(String, nullable=True)
    cost = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    tags = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "date",
            "provider",
            "account_id",
            "service",
            "region",
            "currency",
            name="uq_cost_entry_identity",
        ),
        Index("idx_cost_entries_date_provider", "date", "provider"),
    )


class FxRate(Base):
    __tablename__ = "fx_rates"

    id = Column(String, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    base_currency = Column(String, nullable=False, default="EUR")
    currency = Column(String, nullable=False, index=True)
    rate = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("date", "currency", name="uq_fx_rate_date_currency"),
        Index("idx_fx_rates_date_currency", "date", "currency"),
    )
