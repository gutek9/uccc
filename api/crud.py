from datetime import date
from typing import Dict, List, Tuple

from sqlalchemy import and_, case, func, select
from sqlalchemy.engine import Result
from sqlalchemy.orm import Session

from api.models import CostEntry, FxRate


def upsert_cost_entries(session: Session, entries: List[Dict]):
    for entry in entries:
        stmt = select(CostEntry).where(
            CostEntry.id == entry["id"],
        )
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            for key, value in entry.items():
                setattr(existing, key, value)
        else:
            session.add(CostEntry(**entry))
    session.commit()


def upsert_fx_rates(session: Session, entries: List[Dict]):
    for entry in entries:
        stmt = select(FxRate).where(
            FxRate.date == entry["date"],
            FxRate.currency == entry["currency"],
        )
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            for key, value in entry.items():
                setattr(existing, key, value)
        else:
            session.add(FxRate(**entry))
    session.commit()


def usd_cost_expr():
    rate_currency = (
        select(FxRate.rate)
        .where(
            FxRate.currency == CostEntry.currency,
            FxRate.date <= CostEntry.date,
        )
        .order_by(FxRate.date.desc())
        .limit(1)
        .scalar_subquery()
    )
    rate_usd = (
        select(FxRate.rate)
        .where(
            FxRate.currency == "USD",
            FxRate.date <= CostEntry.date,
        )
        .order_by(FxRate.date.desc())
        .limit(1)
        .scalar_subquery()
    )
    return case(
        (CostEntry.currency == "USD", CostEntry.cost),
        (and_(rate_currency.isnot(None), rate_usd.isnot(None)), CostEntry.cost / rate_currency * rate_usd),
        else_=CostEntry.cost,
    )


def get_total_cost(session: Session, start: date, end: date):
    stmt = select(func.sum(usd_cost_expr())).where(CostEntry.date.between(start, end))
    return session.execute(stmt).scalar() or 0.0


def get_grouped_cost(
    session: Session,
    start: date,
    end: date,
    group_by: CostEntry,
    provider: str | None = None,
    search_term: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> List[Tuple[str, float]]:
    stmt = select(group_by, func.sum(usd_cost_expr())).where(CostEntry.date.between(start, end))
    if provider:
        stmt = stmt.where(CostEntry.provider == provider)
    if search_term:
        pattern = f"%{search_term.strip().lower()}%"
        stmt = stmt.where(func.lower(group_by).like(pattern))
    stmt = stmt.group_by(group_by).order_by(func.sum(usd_cost_expr()).desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    result: Result = session.execute(stmt)
    return result.all()


def get_daily_totals(session: Session, start: date, end: date):
    stmt = (
        select(CostEntry.date, func.sum(usd_cost_expr()))
        .where(CostEntry.date.between(start, end))
        .group_by(CostEntry.date)
        .order_by(CostEntry.date)
    )
    return session.execute(stmt).all()


def get_daily_totals_by_provider(session: Session, start: date, end: date):
    stmt = (
        select(CostEntry.provider, CostEntry.date, func.sum(usd_cost_expr()))
        .where(CostEntry.date.between(start, end))
        .group_by(CostEntry.provider, CostEntry.date)
        .order_by(CostEntry.provider, CostEntry.date)
    )
    return session.execute(stmt).all()


def get_top_services(session: Session, start: date, end: date, limit: int):
    stmt = (
        select(CostEntry.service, func.sum(usd_cost_expr()))
        .where(CostEntry.date.between(start, end))
        .group_by(CostEntry.service)
        .order_by(func.sum(usd_cost_expr()).desc())
        .limit(limit)
    )
    return session.execute(stmt).all()


def get_entries_in_range(session: Session, start: date, end: date):
    stmt = select(CostEntry).where(CostEntry.date.between(start, end))
    return session.execute(stmt).scalars().all()


def get_freshness(session: Session):
    stmt = (
        select(
            CostEntry.provider,
            func.max(CostEntry.date),
            func.max(CostEntry.created_at),
        )
        .group_by(CostEntry.provider)
        .order_by(CostEntry.provider)
    )
    return session.execute(stmt).all()


def get_fx_last_updated(session: Session):
    stmt = select(func.max(FxRate.date))
    return session.execute(stmt).scalar()


def get_provider_totals_with_currency(session: Session, start: date, end: date):
    stmt = (
        select(CostEntry.provider, func.sum(usd_cost_expr()))
        .where(CostEntry.date.between(start, end))
        .group_by(CostEntry.provider)
        .order_by(CostEntry.provider, func.sum(usd_cost_expr()).desc())
    )
    return session.execute(stmt).all()
