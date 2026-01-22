from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import CostEntry
from api.schemas import SignalResponse, SignalTimeframe
from api.services.deltas import grouped_delta


@dataclass(frozen=True)
class SignalSpec:
    entity_type: str
    group_by: CostEntry
    root_cause_hint: str


SIGNAL_SPECS: list[SignalSpec] = [
    SignalSpec(entity_type="service", group_by=CostEntry.service, root_cause_hint="Service cost spike vs previous period"),
    SignalSpec(entity_type="account", group_by=CostEntry.account_id, root_cause_hint="Account cost spike vs previous period"),
]


def build_timeframe(start: date, end: date) -> SignalTimeframe:
    delta = end - start
    compare_end = start - timedelta(days=1)
    compare_start = compare_end - delta
    return SignalTimeframe(start=start, end=end, compare_start=compare_start, compare_end=compare_end)


def get_providers(session: Session, start: date, end: date) -> Iterable[str]:
    stmt = (
        select(CostEntry.provider)
        .where(CostEntry.date.between(start, end))
        .distinct()
        .order_by(CostEntry.provider)
    )
    return [row[0] for row in session.execute(stmt).all() if row[0]]


def classify_severity(impact_cost: float, impact_pct: float, threshold: float) -> str:
    if impact_cost >= 500 and impact_pct >= threshold * 2:
        return "high"
    if impact_cost >= 200 and impact_pct >= threshold:
        return "medium"
    return "low"


def build_signals(
    session: Session,
    start: date,
    end: date,
    threshold: float,
    limit: int,
    provider: Optional[str] = None,
) -> list[SignalResponse]:
    timeframe = build_timeframe(start, end)
    providers = [provider] if provider else list(get_providers(session, start, end))
    if not providers:
        return []
    signals: list[SignalResponse] = []
    sample_limit = max(limit * 5, 20)
    for provider_name in providers:
        for spec in SIGNAL_SPECS:
            deltas = grouped_delta(
                session,
                spec.group_by,
                start,
                end,
                timeframe.compare_start,
                timeframe.compare_end,
                provider_name,
                sample_limit,
            )
            for item in deltas:
                if not item.key:
                    continue
                if item.delta_ratio is None or item.delta_ratio < threshold:
                    continue
                if item.delta <= 0:
                    continue
                severity = classify_severity(item.delta, item.delta_ratio, threshold)
                signals.append(
                    SignalResponse(
                        severity=severity,
                        provider=provider_name,
                        scope="provider",
                        entity_type=spec.entity_type,
                        entity_id=item.key,
                        impact_cost=item.delta,
                        impact_pct=item.delta_ratio,
                        timeframe=timeframe,
                        root_cause_hint=spec.root_cause_hint,
                    )
                )
    signals.sort(key=lambda sig: abs(sig.impact_cost), reverse=True)
    return signals[:limit]
