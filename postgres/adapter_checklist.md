# Postgres Adapter Checklist

This file tracks the remaining work needed to switch the app from SQLite to Neon/Postgres.

## Current State

- SQLite is still the active runtime backend.
- The schema is created from the SQLAlchemy ORM models (`gtf_app/models.py`) at startup.
- Reference data is seeded from `seeds/*.sql` by the app on startup.
- `/healthz` reports `database_config`.
- `DATABASE_BACKEND=postgres` now routes through the initial psycopg connection adapter.
- The app creates its own schema and seeds reference data on startup; no manual SQL step is required.

## Implementation Tasks

1. Test the psycopg adapter against a real Neon database.
2. Move uploaded file bytes from local `data/uploads` to object storage.
3. Add explicit migrations or startup schema checks for Postgres.
4. Add smoke tests for:
   - project creation
   - statement mapping
   - validation
   - conversion draft creation
   - review
   - audit log
   - export endpoints

## Environment

```bash
DATABASE_BACKEND=postgres
DATABASE_URL=postgresql://...
```

## Cutover Rule

After setting `DATABASE_BACKEND=postgres` in Render, confirm `/healthz` returns:

```json
{
  "database_config": {
    "backend": "postgres",
    "database_url_ready": true,
    "postgres_driver_ready": true,
    "postgres_ready": true
  }
}
```
