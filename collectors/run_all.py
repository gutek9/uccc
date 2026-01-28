from api.crud import upsert_cost_entries
from api.db import SessionLocal
from collectors.aws.collector import collect as collect_aws
from collectors.azure.collector import collect as collect_azure
from collectors.gcp.collector import collect as collect_gcp
from core.normalization import normalize_entries


def run_collectors(selected_providers=None, status=None):
    providers = set(selected_providers or ["aws", "gcp", "azure"])
    session = SessionLocal()
    try:
        entries = []
        for name, collector in (
            ("aws", collect_aws),
            ("gcp", collect_gcp),
            ("azure", collect_azure),
        ):
            if name not in providers:
                continue
            if status is not None:
                status["sources"][name] = {"state": "running", "entries": 0, "error": None}
            try:
                collected = collector()
                entries.extend(collected)
                if status is not None:
                    status["sources"][name] = {
                        "state": "success",
                        "entries": len(collected),
                        "error": None,
                    }
            except Exception as exc:
                if status is not None:
                    status["sources"][name] = {
                        "state": "error",
                        "entries": 0,
                        "error": str(exc),
                    }
                print(f"[collector:{name}] failed: {exc}")
        normalized = normalize_entries(entries)
        upsert_cost_entries(session, normalized)
    finally:
        session.close()


if __name__ == "__main__":
    run_collectors()
