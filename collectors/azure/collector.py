import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from collectors.common import load_sample_data, resolve_date_range

SAMPLE_PATH = Path(__file__).with_name("sample.json")


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    return value.strip() if value else value


def _build_http_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def _get_token(session: requests.Session, tenant_id: str, client_id: str, client_secret: str) -> str:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "resource": "https://management.azure.com/",
    }
    response = session.post(url, data=data, timeout=20)
    response.raise_for_status()
    payload = response.json()
    return payload["access_token"]


def _iter_rows(
    session: requests.Session,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    body: Dict[str, Any],
) -> Iterable[tuple[list[str], List[Any]]]:
    properties = payload.get("properties", {})
    columns = [col["name"] for col in properties.get("columns", [])]
    rows = properties.get("rows", [])
    for row in rows:
        yield columns, row
    next_link = properties.get("nextLink")
    while next_link:
        response = session.post(next_link, headers=headers, json=body, timeout=20)
        response.raise_for_status()
        payload = response.json()
        properties = payload.get("properties", {})
        rows = properties.get("rows", [])
        for row in rows:
            yield columns, row
        next_link = properties.get("nextLink")


def _build_query(start_date: date, end_date: date) -> Dict[str, Any]:
    return {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
        },
        "dataset": {
            "granularity": "Daily",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [
                {"type": "Dimension", "name": "ServiceName"},
                {"type": "Dimension", "name": "ResourceLocation"},
            ],
        },
    }


def _parse_rows(
    rows: Iterable[tuple[list[str], List[Any]]],
    subscription_id: str,
    account_name: Optional[str],
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for columns, row in rows:
        row_map = dict(zip(columns, row))
        cost_value = row_map.get("Cost", row_map.get("PreTaxCost", 0))
        usage_value = row_map.get("UsageDate")
        if not usage_value:
            continue
        cost = float(cost_value or 0)
        usage_date = datetime.strptime(str(usage_value), "%Y%m%d").date()
        service = row_map.get("ServiceName") or "Unknown"
        region = row_map.get("ResourceLocation") or "global"
        currency = row_map.get("Currency") or row_map.get("BillingCurrency") or _get_env(
            "AZURE_DEFAULT_CURRENCY", "USD"
        )
        entries.append(
            {
                "date": usage_date,
                "provider": "azure",
                "account_id": subscription_id,
                "account_name": account_name,
                "service": service,
                "region": region,
                "cost": cost,
                "currency": currency,
                "tags": {},
            }
        )
    return entries


def _collect_from_api() -> List[Dict[str, Any]]:
    tenant_id = _get_env("AZURE_TENANT_ID")
    client_id = _get_env("AZURE_CLIENT_ID")
    client_secret = _get_env("AZURE_CLIENT_SECRET")
    subscription_ids = _get_env("AZURE_SUBSCRIPTION_IDS")
    if not (tenant_id and client_id and client_secret and subscription_ids):
        raise ValueError("Azure credentials are not configured")

    account_name = _get_env("AZURE_ACCOUNT_NAME")
    lookback_days = int(_get_env("LOOKBACK_DAYS", "7"))
    start_date, end_date = resolve_date_range(lookback_days)

    session = _build_http_session()
    token = _get_token(session, tenant_id, client_id, client_secret)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    all_entries: List[Dict[str, Any]] = []
    for subscription_id in [item.strip() for item in subscription_ids.split(",") if item.strip()]:
        url = (
            f"https://management.azure.com/subscriptions/{subscription_id}"
            "/providers/Microsoft.CostManagement/query?api-version=2023-03-01"
        )
        body = _build_query(start_date, end_date)
        response = session.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        payload = response.json()
        rows = _iter_rows(session, payload, headers, body)
        all_entries.extend(_parse_rows(rows, subscription_id, account_name))
    return all_entries


def collect() -> List[Dict[str, Any]]:
    """Return Azure cost entries in unified schema."""
    if _get_env("AZURE_USE_SAMPLE", "0") == "1":
        entries = load_sample_data(SAMPLE_PATH)
        for entry in entries:
            entry.setdefault("provider", "azure")
            entry["date"] = datetime.fromisoformat(entry["date"]).date()
        return entries

    return _collect_from_api()
