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

The schema's single source of truth is the SQLAlchemy ORM models in `gtf_app/models.py`.
On startup the app runs `Base.metadata.create_all(engine)`, which creates any missing
tables on both SQLite and Postgres. No schema file needs to be applied by hand.

Reference data (standard accounts, aliases, checklists, standards paragraphs, statement
templates) is seeded from `seeds/*.sql` at startup with `insert ... on conflict do update`,
so the seeds are idempotent and run on both backends.

## File Storage

Neon is database-only. Use one of these for uploaded PDFs, Excel files, CSVs, and images:

- S3-compatible storage such as Cloudflare R2
- AWS S3
- Render persistent disk for MVP/demo only

Recommended production split:

- Postgres: projects, statements, conversions, reviews, audit logs, reference DB
- Object storage: original uploaded files

## App Runtime

The app uses one SQLAlchemy engine for both backends (`gtf_app/db.py`). Set:

```bash
DATABASE_BACKEND=postgres
DATABASE_URL
```

Keep SQLite as the local fallback:

```bash
DATABASE_BACKEND=sqlite
```

Nothing has to be applied by hand before switching: the first startup creates the schema
and seeds the reference tables, then fails fast if the seeds and the calculators disagree.
