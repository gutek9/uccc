from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_REQUIRED_TAGS = ["owner", "cost_center", "environment"]


def evaluate_tags(tags: Dict[str, Any], required_tags: Iterable[str]) -> Tuple[bool, List[str]]:
    missing = [tag for tag in required_tags if not tags.get(tag)]
    return len(missing) == 0, missing
