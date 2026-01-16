import csv
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api import crud
from api.deps import get_session, parse_date_range
from api.models import CostEntry

router = APIRouter()


@router.get("/export/costs")
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
