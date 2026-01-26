from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable
import xml.etree.ElementTree as ET

import requests

ECB_HIST_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
ECB_NS = {
    "gesmes": "http://www.gesmes.org/xml/2002-08-01",
    "def": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
}


def fetch_ecb_rates(lookback_days: int | None = None) -> list[dict]:
    response = requests.get(ECB_HIST_URL, timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    cutoff = None
    if lookback_days:
        cutoff = date.today() - timedelta(days=lookback_days)
    entries: list[dict] = []
    for cube_time in root.findall(".//def:Cube[@time]", ECB_NS):
        day = date.fromisoformat(cube_time.attrib["time"])
        if cutoff and day < cutoff:
            continue
        day_entries = []
        for cube in cube_time.findall("def:Cube", ECB_NS):
            currency = cube.attrib["currency"]
            rate = float(cube.attrib["rate"])
            day_entries.append(
                {
                    "id": f"{day.isoformat()}_{currency}",
                    "date": day,
                    "base_currency": "EUR",
                    "currency": currency,
                    "rate": rate,
                }
            )
        day_entries.append(
            {
                "id": f"{day.isoformat()}_EUR",
                "date": day,
                "base_currency": "EUR",
                "currency": "EUR",
                "rate": 1.0,
            }
        )
        entries.extend(day_entries)
    return entries
