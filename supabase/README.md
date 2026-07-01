# Supabase Setup

Use Supabase for real service deployment. SQLite remains useful only for local MVP development.

## 1. Create Project

Create a Supabase project and copy:

- Project URL: `SUPABASE_URL`
- Service role key: `SUPABASE_SERVICE_ROLE_KEY`
- Database connection string: `SUPABASE_DB_URL`

Keep the service role key server-side only. Never expose it in browser JavaScript.

## 2. Create Tables

Open Supabase SQL Editor and run:

1. `supabase/schema.sql`
2. `supabase/seed_reference_data.sql`

This creates:

- workflow tables: projects, uploads, extractions, statements, conversions, reviews, audit_logs
- reference tables: standard_accounts, kgaap_accounts, ifrs_accounts, mapping_rules, checklist_items, standards_references

## 3. Storage

Create a private Storage bucket:

```text
gtf-uploads
```

Uploaded PDFs, Excel files, CSVs, and images should move from local `data/uploads` to this bucket in the production adapter.

## 4. Server Environment

Set these in Render/Railway/Fly:

```bash
DATABASE_BACKEND=supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_DB_URL=...
SUPABASE_STORAGE_BUCKET=gtf-uploads
GEMINI_API_KEY=...
OCR_PROVIDER=gemini
GEMINI_OCR_MODEL=gemini-3.5-flash
```

## 5. Next Implementation Step

The current Python server still runs on SQLite. The next code step is to add a storage adapter:

- `SQLiteRepository`: current local implementation
- `SupabaseRepository`: Postgres + Storage implementation

After that, `DATABASE_BACKEND=supabase` can switch the deployed app to Supabase without changing the UI.
