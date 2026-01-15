import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from collectors.common import load_sample_data

SAMPLE_PATH = Path(__file__).with_name("sample.json")


def collect() -> List[Dict[str, Any]]:
    """Return GCP cost entries in unified schema."""
    if os.getenv("GCP_USE_SAMPLE", "0") != "1":
        return []

    entries = load_sample_data(SAMPLE_PATH)
    for entry in entries:
        entry.setdefault("provider", "gcp")
        entry["date"] = datetime.fromisoformat(entry["date"]).date()
    return entries
