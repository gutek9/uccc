import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3

from collectors.common import load_sample_data

SAMPLE_PATH = Path(__file__).with_name("sample.json")


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    return value.strip() if value else value


def _build_session() -> boto3.Session:
    region = _get_env("AWS_REGION", "us-east-1")
    access_key = _get_env("AWS_ACCESS_KEY_ID")
    secret_key = _get_env("AWS_SECRET_ACCESS_KEY")
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )

    role_arn = _get_env("AWS_ROLE_ARN")
    if role_arn:
        sts = session.client("sts", region_name=region)
        assume_args = {"RoleArn": role_arn, "RoleSessionName": "uccc-cost-explorer"}
        external_id = _get_env("AWS_EXTERNAL_ID")
        if external_id:
            assume_args["ExternalId"] = external_id
        creds = sts.assume_role(**assume_args)["Credentials"]
        session = boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=region,
        )
    return session


def _collect_from_api() -> List[Dict[str, Any]]:
    region = _get_env("AWS_REGION", "us-east-1")
    lookback_days = int(_get_env("LOOKBACK_DAYS", "7"))
    metric = _get_env("AWS_COST_METRIC", "UnblendedCost")

    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)
    end_exclusive = end_date + timedelta(days=1)

    session = _build_session()
    client = session.client("ce", region_name=region)

    entries: List[Dict[str, Any]] = []
    token = None
    while True:
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date.isoformat(), "End": end_exclusive.isoformat()},
            Granularity="DAILY",
            Metrics=[metric],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
            ],
            **({"NextPageToken": token} if token else {}),
        )

        for day in response.get("ResultsByTime", []):
            usage_date = datetime.fromisoformat(day["TimePeriod"]["Start"]).date()
            for group in day.get("Groups", []):
                service, account_id = group.get("Keys", ["Unknown", ""])
                amount = group.get("Metrics", {}).get(metric, {}).get("Amount", "0")
                unit = group.get("Metrics", {}).get(metric, {}).get("Unit", "USD")
                entries.append(
                    {
                        "date": usage_date,
                        "provider": "aws",
                        "account_id": account_id or "unknown",
                        "account_name": None,
                        "service": service or "Unknown",
                        "region": "global",
                        "cost": float(amount or 0),
                        "currency": unit or "USD",
                        "tags": {},
                    }
                )

        token = response.get("NextPageToken")
        if not token:
            break
    return entries


def collect() -> List[Dict[str, Any]]:
    """Return AWS cost entries in unified schema."""
    if _get_env("AWS_USE_SAMPLE", "0") == "1":
        entries = load_sample_data(SAMPLE_PATH)
        for entry in entries:
            entry.setdefault("provider", "aws")
            entry["date"] = datetime.fromisoformat(entry["date"]).date()
        return entries

    if not _get_env("AWS_ROLE_ARN") and not _get_env("AWS_ACCESS_KEY_ID"):
        return []

    return _collect_from_api()
