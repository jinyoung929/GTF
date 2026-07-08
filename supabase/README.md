# Supabase Setup

Supabase is one option for the deployed Postgres database. Neon is the documented default
(see `postgres/README.md`); both are plain Postgres, so the app treats them identically.
SQLite remains the local development default.

## 1. Create Project

Create a Supabase project and copy:

- Database connection string: `SUPABASE_DB_URL`
- Project URL: `SUPABASE_URL` (only needed for Storage)
- Service role key: `SUPABASE_SERVICE_ROLE_KEY` (only needed for Storage)

Keep the service role key server-side only. Never expose it in browser JavaScript.

## 2. Tables

No SQL has to be run by hand. The schema's single source of truth is the SQLAlchemy ORM
models in `gtf_app/models.py`; on startup the app runs `Base.metadata.create_all(engine)`
and then seeds the reference tables from `seeds/*.sql` with idempotent upserts.

## 3. Storage

Create a private Storage bucket:

```text
gtf-uploads
```

Uploaded PDFs, Excel files, CSVs, and images currently live in the `uploads.file_bytes`
column and in local `data/uploads`. Moving them to this bucket is a future step.

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
