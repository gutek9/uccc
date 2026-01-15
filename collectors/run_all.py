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
        entries.extend(collect_aws())
        entries.extend(collect_gcp())
        entries.extend(collect_azure())
        normalized = normalize_entries(entries)
        upsert_cost_entries(session, normalized)
    finally:
        session.close()


if __name__ == "__main__":
    run_collectors()
