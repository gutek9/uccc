from datetime import date, datetime, timedelta
import csv
import io
import os
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
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
    DeltaGroupResponse,
    ProviderTotalResponse,
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

API_KEY = os.getenv("API_KEY")


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    if not API_KEY or request.url.path == "/health":
        return await call_next(request)
    if request.headers.get("x-api-key") != API_KEY:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


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


@app.get("/costs/provider-totals", response_model=List[ProviderTotalResponse])
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


@app.get("/export/costs")
def export_costs(
    group: str = "provider",
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    provider: Optional[str] = None,
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    group_map = {
        "provider": CostEntry.provider,
        "service": CostEntry.service,
        "account": CostEntry.account_id,
    }
    group_by = group_map.get(group, CostEntry.provider)
    rows = crud.get_grouped_cost(session, start, end, group_by, provider=provider)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([group, "total_cost"])
    for key, total in rows:
        writer.writerow([key, f"{total:.2f}"])
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv")


@app.get("/costs/snapshot")
def snapshot(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    total = crud.get_total_cost(session, start, end)
    provider_totals = [
        ProviderTotalResponse(provider=row[0], total_cost=row[2], currency=row[1] or "USD")
        for row in crud.get_provider_totals_with_currency(session, start, end)
    ]
    tag_coverage = tag_hygiene_by_provider(from_date=from_date, to_date=to_date, session=session)
    freshness_rows = freshness(session=session)
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "total": total,
        "provider_totals": provider_totals,
        "tag_coverage": tag_coverage,
        "freshness": freshness_rows,
    }


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


def _grouped_delta(
    session: Session,
    group_by,
    start: date,
    end: date,
    prev_start: date,
    prev_end: date,
    provider: Optional[str],
    limit: int,
):
    current = crud.get_grouped_cost(session, start, end, group_by, provider=provider)
    previous = crud.get_grouped_cost(session, prev_start, prev_end, group_by, provider=provider)
    current_map = {row[0]: row[1] for row in current}
    previous_map = {row[0]: row[1] for row in previous}
    keys = set(current_map) | set(previous_map)
    deltas: list[DeltaGroupResponse] = []
    for key in keys:
        curr = current_map.get(key, 0.0)
        prev = previous_map.get(key, 0.0)
        delta = curr - prev
        ratio = None if prev == 0 else delta / prev
        deltas.append(
            DeltaGroupResponse(
                key=key,
                current_cost=curr,
                previous_cost=prev,
                delta=delta,
                delta_ratio=ratio,
            )
        )
    deltas.sort(key=lambda item: item.delta, reverse=True)
    return deltas[:limit]


@app.get("/costs/deltas/by-service", response_model=List[DeltaGroupResponse])
def deltas_by_service(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    compare_from: date = Query(alias="compare_from"),
    compare_to: date = Query(alias="compare_to"),
    provider: Optional[str] = None,
    limit: int = 5,
    session: Session = Depends(get_session),
):
    return _grouped_delta(session, CostEntry.service, from_date, to_date, compare_from, compare_to, provider, limit)


@app.get("/costs/deltas/by-account", response_model=List[DeltaGroupResponse])
def deltas_by_account(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    compare_from: date = Query(alias="compare_from"),
    compare_to: date = Query(alias="compare_to"),
    provider: Optional[str] = None,
    limit: int = 5,
    session: Session = Depends(get_session),
):
    return _grouped_delta(session, CostEntry.account_id, from_date, to_date, compare_from, compare_to, provider, limit)


@app.get("/costs/tag-hygiene", response_model=TagHygieneResponse)
def tag_hygiene(
    required: Optional[str] = None,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    provider: Optional[str] = None,
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    required_tags = _required_tags_for_provider(provider, required)
    entries = crud.get_entries_in_range(session, start, end)
    if provider:
        entries = [entry for entry in entries if entry.provider == provider]

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
    entries = crud.get_entries_in_range(session, start, end)

    coverage_by_provider: dict[str, TagCoverageResponse] = {}
    for entry in entries:
        provider = entry.provider
        tags = entry.tags or {}
        required_tags = _required_tags_for_provider(provider, required)
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


@app.get("/costs/tag-hygiene/untagged", response_model=List[GroupedCostResponse])
def untagged_breakdown(
    group: str = "service",
    required: Optional[str] = None,
    provider: Optional[str] = None,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    required_tags = _required_tags_for_provider(provider, required)
    entries = crud.get_entries_in_range(session, start, end)
    if provider:
        entries = [entry for entry in entries if entry.provider == provider]

    totals: dict[str, float] = {}
    for entry in entries:
        tags = entry.tags or {}
        has_all, missing = evaluate_tags(tags, required_tags)
        if has_all:
            continue
        key = entry.service if group == "service" else entry.account_id
        totals[key] = totals.get(key, 0.0) + entry.cost

    rows = [GroupedCostResponse(key=key, total_cost=total) for key, total in totals.items()]
    rows.sort(key=lambda item: item.total_cost, reverse=True)
    return rows


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


def _required_tags_for_provider(provider: Optional[str], required: Optional[str]) -> list[str]:
    if required:
        return [tag.strip() for tag in required.split(",") if tag.strip()]
    if provider:
        override = os.getenv(f"REQUIRED_TAGS_{provider.upper()}")
        if override:
            return [tag.strip() for tag in override.split(",") if tag.strip()]
    return DEFAULT_REQUIRED_TAGS
