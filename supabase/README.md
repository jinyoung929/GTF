# Supabase Setup

Supabase is one option for the deployed Postgres database. Neon is the documented default
(see `postgres/README.md`); both are plain Postgres, so the app treats them identically.
SQLite remains the local development default.

## 1. Create Project

Create a Supabase project and copy its Postgres connection string. The app reads it from
`DATABASE_URL` — there are no Supabase-specific environment variables, because the app
talks to Supabase as plain Postgres.

## 2. Tables

No SQL has to be run by hand. The schema's single source of truth is the SQLAlchemy ORM
models in `gtf_app/models.py`; on startup the app runs `Base.metadata.create_all(engine)`
and then seeds the reference tables from `seeds/*.sql` with idempotent upserts.

## 3. Storage (not implemented)

Uploaded PDFs, Excel files, CSVs, and images are stored in the `uploads.file_bytes` column
and in local `data/uploads`. Moving them to a Supabase Storage bucket is a future step; the
app does not read any Supabase Storage credentials today.

## 4. Server Environment

There is no `DATABASE_BACKEND=supabase` mode — Supabase is reached over the standard
Postgres backend. Set these in Render/Railway/Fly:

```bash
DATABASE_BACKEND=postgres
DATABASE_URL=<the Supabase connection string>
GEMINI_API_KEY=...
OCR_PROVIDER=gemini
GEMINI_OCR_MODEL=gemini-3.5-flash
```

The first startup creates the schema, seeds reference data, and fails fast if the seeds
and the conversion calculators disagree.
