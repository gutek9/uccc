import os
import time
from datetime import date, timedelta
from typing import List

import requests
from sqlalchemy.orm import Session

from api.crud import get_daily_totals
from api.db import SessionLocal
from collectors.run_all import run_collectors
from core.anomaly import compute_day_over_day


def send_slack_notification(webhook_url: str, anomalies: List[dict]):
    if not anomalies:
        return
    lines = [
        ":warning: Cloud cost anomaly detected:",
    ]
    for item in anomalies:
        ratio_pct = f"{item['delta_ratio'] * 100:.1f}%"
        lines.append(f"- {item['date']}: {item['total_cost']:.2f} ({ratio_pct} vs prior day)")
    payload = {"text": "\n".join(lines)}
    requests.post(webhook_url, json=payload, timeout=10)


def check_anomalies(session: Session, threshold: float):
    end = date.today()
    start = end - timedelta(days=7)
    rows = get_daily_totals(session, start, end)
    totals = [row[1] for row in rows]
    deltas = compute_day_over_day(totals)
    anomalies = []
    for idx, row in enumerate(rows):
        ratio = deltas[idx]
        if ratio is not None and ratio >= threshold:
            anomalies.append(
                {
                    "date": row[0].isoformat(),
                    "total_cost": row[1],
                    "delta_ratio": ratio,
                }
            )
    return anomalies


def run_once():
    run_collectors()
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    threshold = float(os.getenv("ANOMALY_THRESHOLD", "0.3"))
    if webhook:
        session = SessionLocal()
        try:
            anomalies = check_anomalies(session, threshold)
            send_slack_notification(webhook, anomalies)
        finally:
            session.close()


def main():
    interval = int(os.getenv("COLLECTOR_INTERVAL_SECONDS", "86400"))
    while True:
        run_once()
        time.sleep(interval)


if __name__ == "__main__":
    main()
