# AGENT.md

## Project Overview
Unified Cost Center (UCC) aggregates AWS + Azure costs into a single schema, API, and UI. It is an operational cost dashboard (not a system of record).

## Stack
- API: FastAPI + SQLAlchemy
- DB: PostgreSQL (SQLite optional for local dev)
- UI: static HTML/CSS/JS (Gravitee-inspired theme)
- Collectors: AWS Cost Explorer + Azure Cost Management
- Worker: daily scheduled collectors + Slack alerting

## Repo Structure
- `api/` FastAPI app, routers, services
- `collectors/` cloud collectors
- `core/` normalization + anomaly helpers
- `db/` Alembic migrations
- `ui/` static dashboard
- `worker/` scheduler container

## Key Services (Docker)
- `db`: Postgres
- `api`: FastAPI + migrations
- `worker`: scheduled collectors
- `ui`: nginx static

## Environment (important)
Common:
- `LOOKBACK_DAYS` applies to all collectors
- `API_KEY` optional; if set, API requires `X-API-Key`

Azure:
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_SUBSCRIPTION_IDS`
- `AZURE_DEFAULT_CURRENCY`

AWS:
- Uses `~/.aws` mounted into containers
- `AWS_PROFILE`, `AWS_REGION`, `AWS_ROLE_ARN`
- Optional: `AWS_EXTERNAL_ID`, `AWS_COST_METRIC`

Backfill controls:
- `BACKFILL_FROM`, `BACKFILL_TO` (YYYY-MM-DD)

Per-provider tag requirements:
- `REQUIRED_TAGS_AWS`, `REQUIRED_TAGS_AZURE`

## Running
- Start: `docker-compose up -d --build`
- Load now: `docker-compose exec -T api python -m collectors.run_all`

## API Entry Points
- Core: `/costs/total`, `/costs/provider-totals`, `/costs/breakdowns`
- Trends: `/costs/deltas`, `/costs/deltas/by-service`, `/costs/deltas/by-account`
- Ops: `/costs/freshness`, `/costs/snapshot`, `/export/costs`
- Tags (still available): `/costs/tag-hygiene*`

## UI Notes
- Global filter bar drives provider + search.
- Cost Trend is global (spans full width).
- Provider-specific panels respond to provider tab selection.

## Recent Refactor
- `api/main.py` is now just app wiring.
- Routes are in `api/routers/`.
- Domain logic in `api/services/`.

## Git
- `.env` is ignored. Do not commit secrets.
