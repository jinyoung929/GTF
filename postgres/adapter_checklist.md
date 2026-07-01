# Postgres Adapter Checklist

This file tracks the remaining work needed to switch the app from SQLite to Neon/Postgres.

## Current State

- SQLite is still the active runtime backend.
- `postgres/schema.sql` is ready for Neon.
- `supabase/seed_reference_data.sql` can seed the reference DB.
- `/healthz` reports `database_config`.
- `DATABASE_BACKEND=postgres` intentionally fails until this adapter is implemented, so the deployment cannot silently use the wrong storage.

## Implementation Tasks

1. Add a `PostgresRepository` using `psycopg`.
2. Convert SQLite `?` placeholders to Postgres `%s` placeholders inside the repository layer.
3. Convert JSON text columns to native JSONB payloads.
4. Replace local `data/uploads` storage with object storage metadata.
5. Keep `SQLiteRepository` as the local fallback.
6. Add smoke tests for:
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

Do not set `DATABASE_BACKEND=postgres` in Render until the repository adapter is complete and `/healthz` returns:

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
