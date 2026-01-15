from api.crud import upsert_cost_entries
from api.db import SessionLocal
from collectors.aws.collector import collect as collect_aws
from collectors.azure.collector import collect as collect_azure
from collectors.gcp.collector import collect as collect_gcp
from core.normalization import normalize_entries


def run_collectors():
    session = SessionLocal()
    try:
        entries = []
        for name, collector in (
            ("aws", collect_aws),
            ("gcp", collect_gcp),
            ("azure", collect_azure),
        ):
            try:
                entries.extend(collector())
            except Exception as exc:
                print(f"[collector:{name}] failed: {exc}")
        normalized = normalize_entries(entries)
        upsert_cost_entries(session, normalized)
    finally:
        session.close()


if __name__ == "__main__":
    run_collectors()
