CREATE TABLE IF NOT EXISTS app_users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_read_only INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES app_users(id)
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT,
    is_test INTEGER NOT NULL DEFAULT 0,
    company_name TEXT NOT NULL,
    source_standard TEXT NOT NULL,
    target_standard TEXT NOT NULL,
    period TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS statements (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    normalized_account TEXT NOT NULL,
    standard_code TEXT NOT NULL,
    amount REAL NOT NULL,
    period TEXT NOT NULL,
    mapping_type TEXT NOT NULL,
    rule_summary TEXT NOT NULL,
    checklist_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    file_bytes BLOB,
    extraction_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS extractions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    upload_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    rows_json TEXT NOT NULL,
    issues_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(upload_id) REFERENCES uploads(id)
);

CREATE TABLE IF NOT EXISTS conversions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    output_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    reviewer_name TEXT NOT NULL,
    decision TEXT NOT NULL,
    memo TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS standard_accounts (
    account_key TEXT PRIMARY KEY,
    standard_code TEXT NOT NULL UNIQUE,
    internal_label TEXT NOT NULL,
    ifrs_account TEXT NOT NULL,
    mapping_type TEXT NOT NULL,
    rule_summary TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kgaap_accounts (
    id TEXT PRIMARY KEY,
    account_key TEXT NOT NULL,
    kgaap_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
);

CREATE TABLE IF NOT EXISTS ifrs_accounts (
    id TEXT PRIMARY KEY,
    account_key TEXT NOT NULL,
    ifrs_name TEXT NOT NULL,
    standard_ref TEXT NOT NULL,
    recognition_summary TEXT NOT NULL,
    measurement_summary TEXT NOT NULL,
    disclosure_summary TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
);

CREATE TABLE IF NOT EXISTS mapping_rules (
    id TEXT PRIMARY KEY,
    account_key TEXT NOT NULL,
    source_standard TEXT NOT NULL,
    target_standard TEXT NOT NULL,
    mapping_type TEXT NOT NULL,
    rule_summary TEXT NOT NULL,
    checklist_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
);

CREATE TABLE IF NOT EXISTS checklist_items (
    id TEXT PRIMARY KEY,
    account_key TEXT NOT NULL,
    item_key TEXT NOT NULL,
    label TEXT NOT NULL,
    input_type TEXT NOT NULL,
    required INTEGER NOT NULL,
    display_order INTEGER NOT NULL,
    FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
);

CREATE TABLE IF NOT EXISTS standards_references (
    id TEXT PRIMARY KEY,
    standard_set TEXT NOT NULL,
    reference_code TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS financial_statement_templates (
    id TEXT PRIMARY KEY,
    standard_set TEXT NOT NULL,
    statement_type TEXT NOT NULL,
    section TEXT NOT NULL,
    line_item TEXT NOT NULL,
    account_key TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    basis TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(account_key) REFERENCES standard_accounts(account_key)
);
