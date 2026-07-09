export type Screen = "import" | "review";
export type ReviewTab = "checklist" | "adjustments" | "notes" | "approval" | "audit" | "export";
export type ImportTab = "file" | "dart-api" | "manual";

export type UserInfo = { id: string; email: string; is_read_only: boolean; created_at: string };

export type Project = {
  id: string;
  company_name: string;
  source_standard: string;
  target_standard: string;
  period: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type UploadRow = {
  id: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  extraction_status: string;
  created_at: string;
};

export type Extraction = {
  id: string;
  upload_id: string;
  provider: string;
  status: string;
  rows: SourceRow[];
  issues: string[];
  created_at: string;
};

export type SourceRow = {
  account_name: string;
  amount: number;
  statement_type?: string;
  currency?: string;
  dart_account_id?: string;
  ai_suggestion?: {
    account_key: string;
    label: string;
    confidence: string;
    rationale: string;
    basis_reference?: string;
    alternative_label?: string;
    alternative_rejected_reason?: string;
  };
};

export type Statement = {
  id: string;
  account_name: string;
  normalized_account: string;
  standard_code: string;
  amount: number;
  period: string;
  mapping_type: "simple" | "judgment";
  rule_summary: string;
  checklist: ChecklistItem[];
};

export type ChecklistItem = {
  key: string;
  label: string;
  type: "text" | "number" | "boolean";
  required: boolean;
};

export type ConversionEntry = {
  source_account: string;
  standard_code: string;
  target_account: string;
  amount: number;
  adjustment: number;
  mapping_type: string;
  basis: string;
  calculation?: string;
  statement_type?: string;
  statement_line_item?: string;
};

export type StandardsParagraph = {
  standard_set: "K-GAAP" | "K-IFRS";
  reference_code: string;
  paragraph_label: string;
  title: string;
  content: string;
};

export type Conversion = {
  entries: ConversionEntry[];
  judgment_items: Array<{
    statement_id: string;
    account: string;
    checklist_response: Record<string, unknown>;
    basis: string;
    standards_paragraphs?: StandardsParagraph[];
  }>;
  draft_notes: Array<{ account: string; draft_note: string }>;
  ai_assistance?: { status: string; overall_note?: string; items?: unknown[] };
  review_status: string;
};

export type AuditLog = { id: string; event_type: string; actor: string; created_at: string; detail: unknown };

export type AiDecision = "approved" | "rejected";

export type ReviewAttentionItem = {
  type: "unclassified" | "checklist_missing" | "validation";
  severity: "error" | "warning";
  account: string;
  message: string;
};

export type ReviewSummary = {
  attention: ReviewAttentionItem[];
  judgment: Array<{
    statement_id: string;
    account: string;
    normalized_account: string;
    standard_code: string;
    amount: number;
    rule_summary: string;
    checklist_answered: boolean;
    checklist_response: Record<string, unknown>;
    standards_paragraph_count: number;
  }>;
  counts: { attention: number; attention_errors: number; judgment: number; unclassified: number };
  has_conversion: boolean;
  can_approve: boolean;
  approval_policy: string;
};

export type ProjectBundle = {
  project: Project;
  uploads: UploadRow[];
  extractions: Extraction[];
  statements: Statement[];
  conversion: Conversion | null;
  review: unknown | null;
};
