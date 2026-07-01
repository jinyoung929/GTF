# Postgres Setup

Use this path when Supabase is unavailable. Neon is the recommended default because it is Postgres-compatible and works well with a small Render-hosted backend.

## Recommended Provider

1. Create a Neon project.
2. Create a database, for example `gtf`.
3. Copy the pooled connection string.
4. Set it as:

```bash
DATABASE_BACKEND=postgres
DATABASE_URL=postgresql://...
```

`NEON_DATABASE_URL` can also be used as an explicit name, but the app should prefer `DATABASE_URL` when the Postgres adapter is added.

## Schema

The existing SQL files under `supabase/` are standard Postgres-compatible table definitions with only ordinary SQL tables, indexes, JSONB, and RLS statements.

For Neon, run these files in the SQL editor:

1. `supabase/schema.sql`
2. `supabase/seed_reference_data.sql`

If the provider does not support Supabase-style RLS commands, remove the `alter table ... enable row level security;` lines before running the schema.

## File Storage

Neon is database-only. Use one of these for uploaded PDFs, Excel files, CSVs, and images:

- S3-compatible storage such as Cloudflare R2
- AWS S3
- Render persistent disk for MVP/demo only

Recommended production split:

- Postgres: projects, statements, conversions, reviews, audit logs, reference DB
- Object storage: original uploaded files

## Next Code Step

Add a `PostgresRepository` that reads:

```bash
DATABASE_URL
```

Then keep SQLite as the local fallback:

```bash
DATABASE_BACKEND=sqlite
```
