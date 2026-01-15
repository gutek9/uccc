# Unified Cloud Cost Center (UCCC)

Unified Cloud Cost Center (UCCC) is a lightweight operational cost intelligence dashboard that aggregates cloud costs across AWS, GCP, and Azure into a single schema, API, and UI.

It is **not** a financial system of record. The goal is fast visibility, anomaly detection, and tag hygiene.

## Features

- Daily cost collection (AWS, Azure; GCP skipped for now)
- Unified schema in PostgreSQL
- REST API for totals, breakdowns, anomalies, tag hygiene, and data freshness
- Gravitee-themed UI dashboard
- Slack anomaly alerts (worker)

## Architecture

```
/collectors
  /aws
  /gcp
  /azure
/core
  normalization
  models
/db
  migrations
/api
/ui
/worker
/docker-compose.yml
```

## Quick start (Docker)

```bash
docker-compose up -d --build
```

UI: http://localhost:8080
API: http://localhost:8000

## Environment

Create a `.env` file (ignored by git) with your credentials and settings.

### Common

```
LOOKBACK_DAYS=90
API_KEY=optional-shared-secret
```

`LOOKBACK_DAYS` applies to all collectors (AWS/Azure).

If `API_KEY` is set, all API requests (except `/health`) require `X-API-Key`.

### Azure (Cost Management API)

```
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_SUBSCRIPTION_IDS=sub-id-1,sub-id-2
AZURE_DEFAULT_CURRENCY=USD
```

### AWS (Cost Explorer)

UCCC uses your local AWS CLI credentials by mounting `~/.aws` into the containers.

```
AWS_PROFILE=default
AWS_REGION=us-east-1
AWS_ROLE_ARN=arn:aws:iam::<account-id>:role/UCCC-CostExplorer-Role
AWS_EXTERNAL_ID=optional-if-required
AWS_COST_METRIC=UnblendedCost
```

If you don’t want to mount `~/.aws`, you can provide access keys instead:

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...   # optional
```

### Slack Alerts (optional)

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ANOMALY_THRESHOLD=0.3
```

## Collection

Collectors are stateless and idempotent. Each cost entry is hashed from:
`date + provider + account_id + service + region + currency`.

### Run collection manually

```bash
docker-compose exec -T api python -m collectors.run_all
```

### Scheduled collection

The `worker` container runs collectors once per day by default.

```
COLLECTOR_INTERVAL_SECONDS=86400
```

## API Endpoints

- `GET /costs/total?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `GET /costs/by-provider`
- `GET /costs/provider-totals`
- `GET /costs/breakdowns?provider=aws&limit=10&offset=0&account_offset=0`
- `GET /costs/by-service?provider=aws&limit=10&offset=0`
- `GET /costs/by-account?provider=azure`
- `GET /costs/by-tag?tag=owner`
- `GET /costs/deltas`
- `GET /costs/deltas/by-service`
- `GET /costs/deltas/by-account`
- `GET /costs/anomalies`
- `GET /costs/tag-hygiene`
- `GET /costs/tag-hygiene/by-provider`
- `GET /costs/tag-hygiene/untagged?group=service|account`
- `GET /costs/freshness`
- `GET /costs/snapshot`
- `GET /export/costs?group=provider|service|account`

## Database

PostgreSQL is used by default (SQLite supported for local dev).

Migrations are managed with Alembic:

```bash
alembic upgrade head
```

## Troubleshooting

- **No data in UI**: make sure collectors ran and your time range includes ingested dates.
- **AWS errors**: verify `AWS_PROFILE` exists in `~/.aws` and has permission to assume the role.
- **Azure errors**: verify Cost Management Reader role on subscriptions and correct tenant/app/secret.

## Security Notes

- Never commit `.env` or credentials.
- Prefer AssumeRole for AWS instead of static keys.

---

If you want GCP integration next, open an issue or ask in chat.
