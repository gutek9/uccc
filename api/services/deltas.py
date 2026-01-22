from datetime import date
from typing import Optional, List

from sqlalchemy.orm import Session

from api import crud
from api.models import CostEntry
from api.schemas import DeltaGroupResponse


def grouped_delta(
    session: Session,
    group_by,
    start: date,
    end: date,
    prev_start: date,
    prev_end: date,
    provider: Optional[str],
    limit: int,
    search_term: Optional[str] = None,
) -> List[DeltaGroupResponse]:
    current = crud.get_grouped_cost(session, start, end, group_by, provider=provider, search_term=search_term)
    previous = crud.get_grouped_cost(session, prev_start, prev_end, group_by, provider=provider, search_term=search_term)
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
