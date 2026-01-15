from typing import List, Optional


def compute_day_over_day(daily_totals: List[float]) -> List[Optional[float]]:
    if not daily_totals:
        return []
    deltas: List[Optional[float]] = [None]
    for idx in range(1, len(daily_totals)):
        prev = daily_totals[idx - 1]
        curr = daily_totals[idx]
        if prev == 0:
            deltas.append(None)
        else:
            deltas.append((curr - prev) / prev)
    return deltas
