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

`NEON_DATABASE_URL` can also be used as an explicit name, but `DATABASE_URL` is the preferred deployment variable.

## Schema

The generic Postgres schema is in `postgres/schema.sql`.

For Neon, run these files in the SQL editor:

1. `postgres/schema.sql`
2. `supabase/seed_reference_data.sql`

The seed file is shared with the Supabase path because it uses ordinary Postgres `insert ... on conflict` statements.

## File Storage

Neon is database-only. Use one of these for uploaded PDFs, Excel files, CSVs, and images:

- S3-compatible storage such as Cloudflare R2
- AWS S3
- Render persistent disk for MVP/demo only

Recommended production split:

- Postgres: projects, statements, conversions, reviews, audit logs, reference DB
- Object storage: original uploaded files

## App Runtime

The app includes an initial psycopg adapter. Set:

```bash
DATABASE_BACKEND=postgres
DATABASE_URL
```

Keep SQLite as the local fallback:

```bash
DATABASE_BACKEND=sqlite
```

Before enabling `DATABASE_BACKEND=postgres`, run `postgres/schema.sql` and `supabase/seed_reference_data.sql` in the Postgres provider.
