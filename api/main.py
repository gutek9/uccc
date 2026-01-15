from datetime import date, datetime, timedelta
import os
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api import crud
from api.db import SessionLocal
from api.models import CostEntry
from api.schemas import (
    AnomalyResponse,
    DataFreshnessResponse,
    GroupedCostResponse,
    ProviderBreakdownResponse,
    TagCoverageByProviderResponse,
    TagCoverageResponse,
    TagHygieneResponse,
    TotalCostResponse,
    UntaggedCostEntry,
)
from core.anomaly import compute_day_over_day
from core.tag_hygiene import DEFAULT_REQUIRED_TAGS, evaluate_tags

app = FastAPI(title="Unified Cloud Cost Center")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def parse_date_range(
    start: Optional[date],
    end: Optional[date],
) -> (date, date):
    if not end:
        end = date.today()
    if not start:
        start = end - timedelta(days=30)
    if start > end:
        raise HTTPException(status_code=400, detail="from date must be <= to date")
    return start, end


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/costs/total", response_model=TotalCostResponse)
def total_cost(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    total = crud.get_total_cost(session, start, end)
    return TotalCostResponse(total_cost=total)


@app.get("/costs/by-provider", response_model=List[GroupedCostResponse])
def by_provider(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    rows = crud.get_grouped_cost(session, start, end, CostEntry.provider)
    return [GroupedCostResponse(key=row[0], total_cost=row[1]) for row in rows]


@app.get("/costs/by-service", response_model=List[GroupedCostResponse])
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


@app.get("/costs/by-account", response_model=List[GroupedCostResponse])
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


@app.get("/costs/by-tag", response_model=List[GroupedCostResponse])
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


@app.get("/costs/top-services", response_model=List[GroupedCostResponse])
def top_services(
    n: int = 5,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    rows = crud.get_top_services(session, start, end, n)
    return [GroupedCostResponse(key=row[0], total_cost=row[1]) for row in rows]


@app.get("/costs/deltas", response_model=List[AnomalyResponse])
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


@app.get("/costs/anomalies", response_model=List[AnomalyResponse])
def anomalies(
    threshold: float = 0.3,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    deltas = day_over_day_deltas(from_date, to_date, session)
    flagged = [item for item in deltas if item.delta_ratio is not None and item.delta_ratio >= threshold]
    return flagged


@app.get("/costs/breakdowns", response_model=List[ProviderBreakdownResponse])
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

    response: List[ProviderBreakdownResponse] = []
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


@app.get("/costs/tag-hygiene", response_model=TagHygieneResponse)
def tag_hygiene(
    required: Optional[str] = None,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    required_tags = [tag.strip() for tag in (required or ",".join(DEFAULT_REQUIRED_TAGS)).split(",") if tag.strip()]
    entries = crud.get_entries_in_range(session, start, end)

    total_cost = 0.0
    fully_tagged = 0.0
    partially_tagged = 0.0
    untagged = 0.0
    untagged_entries: List[UntaggedCostEntry] = []

    for entry in entries:
        tags = entry.tags or {}
        total_cost += entry.cost
        has_all, missing = evaluate_tags(tags, required_tags)
        if has_all:
            fully_tagged += entry.cost
        elif len(tags) == 0:
            untagged += entry.cost
        else:
            partially_tagged += entry.cost
        if missing:
            untagged_entries.append(
                UntaggedCostEntry(
                    id=entry.id,
                    date=entry.date,
                    provider=entry.provider,
                    account_id=entry.account_id,
                    service=entry.service,
                    region=entry.region,
                    cost=entry.cost,
                    currency=entry.currency,
                    missing_tags=missing,
                )
            )

    coverage = TagCoverageResponse(
        required_tags=required_tags,
        total_cost=total_cost,
        fully_tagged_cost=fully_tagged,
        partially_tagged_cost=partially_tagged,
        untagged_cost=untagged,
    )

    return TagHygieneResponse(coverage=coverage, untagged_entries=untagged_entries)


@app.get("/costs/tag-hygiene/by-provider", response_model=List[TagCoverageByProviderResponse])
def tag_hygiene_by_provider(
    required: Optional[str] = None,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    required_tags = [tag.strip() for tag in (required or ",".join(DEFAULT_REQUIRED_TAGS)).split(",") if tag.strip()]
    entries = crud.get_entries_in_range(session, start, end)

    coverage_by_provider: dict[str, TagCoverageResponse] = {}
    for entry in entries:
        provider = entry.provider
        tags = entry.tags or {}
        coverage = coverage_by_provider.get(
            provider,
            TagCoverageResponse(
                required_tags=required_tags,
                total_cost=0.0,
                fully_tagged_cost=0.0,
                partially_tagged_cost=0.0,
                untagged_cost=0.0,
            ),
        )

        coverage.total_cost += entry.cost
        has_all, missing = evaluate_tags(tags, required_tags)
        if has_all:
            coverage.fully_tagged_cost += entry.cost
        elif len(tags) == 0:
            coverage.untagged_cost += entry.cost
        else:
            coverage.partially_tagged_cost += entry.cost
        coverage_by_provider[provider] = coverage

    return [
        TagCoverageByProviderResponse(provider=provider, coverage=coverage)
        for provider, coverage in sorted(coverage_by_provider.items())
    ]


@app.get("/costs/freshness", response_model=List[DataFreshnessResponse])
def freshness(session: Session = Depends(get_session)):
    rows = crud.get_freshness(session)
    response: List[DataFreshnessResponse] = []
    lookback_days = int(os.getenv("LOOKBACK_DAYS", "7"))
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
