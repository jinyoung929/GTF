# Postgres Adapter Checklist

This file tracks the remaining work needed to switch the app from SQLite to Neon/Postgres.

## Current State

- SQLite is still the active runtime backend.
- `postgres/schema.sql` is ready for Neon.
- `supabase/seed_reference_data.sql` can seed the reference DB.
- `/healthz` reports `database_config`.
- `DATABASE_BACKEND=postgres` now routes through the initial psycopg connection adapter.
- The app expects `postgres/schema.sql` and `supabase/seed_reference_data.sql` to be run before startup.

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

Do not set `DATABASE_BACKEND=postgres` in Render until `postgres/schema.sql` and seed data have been applied and `/healthz` returns:

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
