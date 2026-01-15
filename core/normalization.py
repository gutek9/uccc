import hashlib
from datetime import date
from typing import Any, Dict, List, Optional


def build_cost_id(
    entry_date: date,
    provider: str,
    account_id: str,
    service: str,
    region: Optional[str],
    currency: str,
) -> str:
    raw = f"{entry_date}|{provider}|{account_id}|{service}|{region or ''}|{currency}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_entry(
    entry_date: date,
    provider: str,
    account_id: str,
    account_name: Optional[str],
    service: str,
    region: Optional[str],
    cost: float,
    currency: str,
    tags: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "id": build_cost_id(entry_date, provider, account_id, service, region, currency),
        "date": entry_date,
        "provider": provider,
        "account_id": account_id,
        "account_name": account_name,
        "service": service,
        "region": region,
        "cost": float(cost),
        "currency": currency,
        "tags": tags or {},
    }


def normalize_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for entry in entries:
        normalized.append(
            normalize_entry(
                entry["date"],
                entry["provider"],
                entry["account_id"],
                entry.get("account_name"),
                entry["service"],
                entry.get("region"),
                entry["cost"],
                entry["currency"],
                entry.get("tags"),
            )
        )
    return normalized
