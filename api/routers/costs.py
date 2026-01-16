from datetime import date, datetime
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api import crud
from api.deps import get_session, parse_date_range
from api.models import CostEntry
from api.schemas import (
    AnomalyResponse,
    DataFreshnessResponse,
    DeltaGroupResponse,
    GroupedCostResponse,
    ProviderBreakdownResponse,
    ProviderTotalResponse,
    TotalCostResponse,
)
from api.services.deltas import grouped_delta
from api.services.snapshot import build_snapshot
from core.anomaly import compute_day_over_day

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/costs/total", response_model=TotalCostResponse)
def total_cost(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    total = crud.get_total_cost(session, start, end)
    return TotalCostResponse(total_cost=total)


@router.get("/costs/by-provider", response_model=List[GroupedCostResponse])
def by_provider(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    rows = crud.get_grouped_cost(session, start, end, CostEntry.provider)
    return [GroupedCostResponse(key=row[0], total_cost=row[1]) for row in rows]


@router.get("/costs/provider-totals", response_model=List[ProviderTotalResponse])
def provider_totals(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    rows = crud.get_provider_totals_with_currency(session, start, end)
    totals: list[ProviderTotalResponse] = []
    seen = set()
    for provider, currency, total in rows:
        if provider in seen:
            continue
        totals.append(
            ProviderTotalResponse(
                provider=provider,
                total_cost=total or 0.0,
                currency=currency or "USD",
            )
        )
        seen.add(provider)
    return totals


@router.get("/costs/snapshot")
def snapshot(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    return build_snapshot(session, start, end)


@router.get("/costs/by-service", response_model=List[GroupedCostResponse])
def by_service(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    provider: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    rows = crud.get_grouped_cost(
        session,
        start,
        end,
        CostEntry.service,
        provider=provider,
        limit=limit,
        offset=offset,
    )
    return [GroupedCostResponse(key=row[0], total_cost=row[1]) for row in rows]


@router.get("/costs/by-account", response_model=List[GroupedCostResponse])
def by_account(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    provider: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    rows = crud.get_grouped_cost(
        session,
        start,
        end,
        CostEntry.account_id,
        provider=provider,
        limit=limit,
        offset=offset,
    )
    return [GroupedCostResponse(key=row[0], total_cost=row[1]) for row in rows]


def build_tag_expr(session: Session, tag: str):
    dialect = session.bind.dialect.name
    if dialect == "sqlite":
        return func.json_extract(CostEntry.tags, f"$.{tag}")
    return CostEntry.tags[tag].as_string()


@router.get("/costs/by-tag", response_model=List[GroupedCostResponse])
def by_tag(
    tag: str,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    tag_expr = build_tag_expr(session, tag)
    stmt = (
        select(tag_expr, func.sum(CostEntry.cost))
        .where(CostEntry.date.between(start, end))
        .group_by(tag_expr)
        .order_by(func.sum(CostEntry.cost).desc())
    )
    rows = session.execute(stmt).all()
    return [GroupedCostResponse(key=row[0] or "(missing)", total_cost=row[1]) for row in rows]


@router.get("/costs/top-services", response_model=List[GroupedCostResponse])
def top_services(
    n: int = 5,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    rows = crud.get_top_services(session, start, end, n)
    return [GroupedCostResponse(key=row[0], total_cost=row[1]) for row in rows]


@router.get("/costs/deltas", response_model=List[AnomalyResponse])
def day_over_day_deltas(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    rows = crud.get_daily_totals_by_provider(session, start, end)
    grouped: dict[str, list[tuple[date, float]]] = {}
    for provider, usage_date, total in rows:
        grouped.setdefault(provider, []).append((usage_date, total))
    response: list[AnomalyResponse] = []
    for provider, series in grouped.items():
        totals = [row[1] for row in series]
        deltas = compute_day_over_day(totals)
        for idx, (usage_date, total) in enumerate(series):
            prev = totals[idx - 1] if idx > 0 else None
            response.append(
                AnomalyResponse(
                    provider=provider,
                    date=usage_date,
                    total_cost=total,
                    previous_day_cost=prev,
                    delta_ratio=deltas[idx],
                )
            )
    return response


@router.get("/costs/anomalies", response_model=List[AnomalyResponse])
def anomalies(
    threshold: float = 0.3,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    provider: Optional[str] = None,
    session: Session = Depends(get_session),
):
    deltas = day_over_day_deltas(from_date, to_date, session)
    if provider:
        deltas = [item for item in deltas if item.provider == provider]
    flagged = [item for item in deltas if item.delta_ratio is not None and item.delta_ratio >= threshold]
    return flagged


@router.get("/costs/breakdowns", response_model=List[ProviderBreakdownResponse])
def breakdowns(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    provider: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    account_offset: int = 0,
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    providers = [provider] if provider else ["aws", "azure"]
    totals = {row[0]: row[1] for row in crud.get_grouped_cost(session, start, end, CostEntry.provider)}

    response: list[ProviderBreakdownResponse] = []
    for item in providers:
        services = crud.get_grouped_cost(
            session,
            start,
            end,
            CostEntry.service,
            provider=item,
            limit=limit,
            offset=offset,
        )
        accounts = crud.get_grouped_cost(
            session,
            start,
            end,
            CostEntry.account_id,
            provider=item,
            limit=limit,
            offset=account_offset,
        )
        response.append(
            ProviderBreakdownResponse(
                provider=item,
                total_cost=totals.get(item, 0.0),
                services=[GroupedCostResponse(key=row[0], total_cost=row[1]) for row in services],
                accounts=[GroupedCostResponse(key=row[0], total_cost=row[1]) for row in accounts],
            )
        )
    return response


@router.get("/costs/deltas/by-service", response_model=List[DeltaGroupResponse])
def deltas_by_service(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    compare_from: date = Query(alias="compare_from"),
    compare_to: date = Query(alias="compare_to"),
    provider: Optional[str] = None,
    limit: int = 5,
    session: Session = Depends(get_session),
):
    return grouped_delta(
        session,
        CostEntry.service,
        from_date,
        to_date,
        compare_from,
        compare_to,
        provider,
        limit,
    )


@router.get("/costs/deltas/by-account", response_model=List[DeltaGroupResponse])
def deltas_by_account(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    compare_from: date = Query(alias="compare_from"),
    compare_to: date = Query(alias="compare_to"),
    provider: Optional[str] = None,
    limit: int = 5,
    session: Session = Depends(get_session),
):
    return grouped_delta(
        session,
        CostEntry.account_id,
        from_date,
        to_date,
        compare_from,
        compare_to,
        provider,
        limit,
    )


@router.get("/costs/freshness", response_model=List[DataFreshnessResponse])
def freshness(session: Session = Depends(get_session)):
    rows = crud.get_freshness(session)
    lookback_days = int(os.getenv("LOOKBACK_DAYS", "7"))
    response: list[DataFreshnessResponse] = []
    for provider, last_date, last_ingested in rows:
        response.append(
            DataFreshnessResponse(
                provider=provider,
                last_entry_date=last_date,
                last_ingested_at=last_ingested.isoformat() if last_ingested else None,
                lookback_days=lookback_days,
            )
        )
    return response
