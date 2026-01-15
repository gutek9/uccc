import json
from pathlib import Path
from typing import Any, Dict, List


def load_sample_data(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
