from datetime import date

from sqlalchemy.orm import Session

from api import crud
from api.schemas import DataFreshnessResponse, ProviderTotalResponse
from api.services.tag_hygiene import build_tag_hygiene_by_provider


def build_snapshot(session: Session, start: date, end: date):
    total = crud.get_total_cost(session, start, end)
    provider_totals = [
        ProviderTotalResponse(provider=row[0], total_cost=row[2], currency=row[1] or "USD")
        for row in crud.get_provider_totals_with_currency(session, start, end)
    ]
    tag_coverage = build_tag_hygiene_by_provider(crud.get_entries_in_range(session, start, end), None)
    freshness_rows = crud.get_freshness(session)
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "total": total,
        "provider_totals": provider_totals,
        "tag_coverage": tag_coverage,
        "freshness": [
            DataFreshnessResponse(
                provider=row[0],
                last_entry_date=row[1],
                last_ingested_at=row[2].isoformat() if row[2] else None,
                lookback_days=None,
            )
            for row in freshness_rows
        ],
    }
