import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_sample_data(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_date_range(lookback_days: int) -> Tuple[date, date]:
    backfill_from = _get_env("BACKFILL_FROM")
    backfill_to = _get_env("BACKFILL_TO")
    if backfill_from:
        start = datetime.fromisoformat(backfill_from).date()
        end = datetime.fromisoformat(backfill_to).date() if backfill_to else date.today()
        return start, end
    end = date.today()
    start = end - timedelta(days=lookback_days)
    return start, end


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    return value.strip() if value else value
