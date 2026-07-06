-- GTF Accounting Conversion - Supabase Postgres schema
-- Run this in Supabase SQL Editor before connecting the deployed app.

create extension if not exists pgcrypto;

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  company_name text not null,
  source_standard text not null default 'K-GAAP',
  target_standard text not null default 'IFRS',
  period text not null,
  status text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.uploads (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  original_name text not null,
  stored_name text not null,
  storage_bucket text not null default 'gtf-uploads',
  storage_path text,
  content_type text not null,
  size_bytes bigint not null,
  extraction_status text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.extractions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  upload_id uuid not null references public.uploads(id) on delete cascade,
  provider text not null,
  status text not null,
  rows_json jsonb not null default '[]'::jsonb,
  issues_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.statements (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  account_name text not null,
  normalized_account text not null,
  standard_code text not null,
  amount numeric not null,
  period text not null,
  mapping_type text not null,
  rule_summary text not null,
  checklist_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.conversions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  output_json jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists public.reviews (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  reviewer_name text not null,
  decision text not null check (decision in ('approved', 'changes_requested')),
  memo text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  event_type text not null,
  actor text not null default 'system',
  detail_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.standard_accounts (
  account_key text primary key,
  standard_code text not null unique,
  internal_label text not null,
  ifrs_account text not null,
  mapping_type text not null check (mapping_type in ('simple', 'judgment')),
  rule_summary text not null,
  active boolean not null default true,
  updated_at timestamptz not null default now()
);

create table if not exists public.kgaap_accounts (
  id text primary key,
  account_key text not null references public.standard_accounts(account_key) on delete cascade,
  kgaap_name text not null,
  normalized_name text not null,
  active boolean not null default true
);

create table if not exists public.ifrs_accounts (
  id text primary key,
  account_key text not null references public.standard_accounts(account_key) on delete cascade,
  ifrs_name text not null,
  standard_ref text not null,
  recognition_summary text not null,
  measurement_summary text not null,
  disclosure_summary text not null,
  active boolean not null default true
);

create table if not exists public.mapping_rules (
  id text primary key,
  account_key text not null references public.standard_accounts(account_key) on delete cascade,
  source_standard text not null,
  target_standard text not null,
  mapping_type text not null check (mapping_type in ('simple', 'judgment')),
  rule_summary text not null,
  checklist_json jsonb not null default '[]'::jsonb,
  active boolean not null default true,
  updated_at timestamptz not null default now()
);

create table if not exists public.checklist_items (
  id text primary key,
  account_key text not null references public.standard_accounts(account_key) on delete cascade,
  item_key text not null,
  label text not null,
  input_type text not null check (input_type in ('text', 'number', 'boolean')),
  required boolean not null default false,
  display_order integer not null
);

create table if not exists public.standards_references (
  id text primary key,
  standard_set text not null,
  reference_code text not null,
  title text not null,
  summary text not null
);

create index if not exists idx_uploads_project_id on public.uploads(project_id);
create index if not exists idx_extractions_project_id on public.extractions(project_id);
create index if not exists idx_statements_project_id on public.statements(project_id);
create index if not exists idx_conversions_project_id_created_at on public.conversions(project_id, created_at desc);
create index if not exists idx_reviews_project_id_created_at on public.reviews(project_id, created_at desc);
create index if not exists idx_audit_logs_project_id_created_at on public.audit_logs(project_id, created_at desc);
create index if not exists idx_kgaap_accounts_name on public.kgaap_accounts(kgaap_name);
create index if not exists idx_mapping_rules_pair on public.mapping_rules(source_standard, target_standard, account_key);

alter table public.projects enable row level security;
alter table public.uploads enable row level security;
alter table public.extractions enable row level security;
alter table public.statements enable row level security;
alter table public.conversions enable row level security;
alter table public.reviews enable row level security;
alter table public.audit_logs enable row level security;
alter table public.standard_accounts enable row level security;
alter table public.kgaap_accounts enable row level security;
alter table public.ifrs_accounts enable row level security;
alter table public.mapping_rules enable row level security;
alter table public.checklist_items enable row level security;
alter table public.standards_references enable row level security;

-- The current server should use the Supabase service role key from backend only.
-- Public client access policies should be added later when authentication is designed.

create table if not exists public.standards_paragraphs (
  id text primary key,
  standard_set text not null,
  reference_code text not null,
  paragraph_label text not null,
  account_key text not null,
  title text not null,
  content text not null,
  keywords text not null
);
alter table public.standards_paragraphs enable row level security;
