# GTF Accounting Conversion MVP

K-GAAP financial statement conversion workflow for Korean startups and SMEs preparing overseas fundraising, IFRS reporting, or listing readiness.

This MVP is intentionally a review-first system. It identifies likely mapping and judgment items, generates conversion drafts, and preserves an audit trail. Final accounting policy decisions remain with company reviewers, accountants, and auditors.

## Features

- Upload K-GAAP financial statement files or paste extracted trial balance rows
- Preserve uploaded PDF, Excel, CSV, and image source files for OCR handoff
- Create extraction results from uploaded files before accepting rows into the mapping workflow
- Show OCR provider/model/API-key readiness before extraction
- Normalize account names into internal standard account codes
- Split simple 1:1 mappings from judgment-required areas
- Collect checklist inputs for leases, development costs, revenue recognition, financial instruments, and provisions
- Generate IFRS conversion draft entries and disclosure notes
- Record human review decisions for approval or requested changes
- Store every project, checklist response, generated output, and audit log in SQLite
- Web dashboard plus JSON API
- Saved project list for reopening prior work

## Run Locally

```bash
python3 server.py
```

Then open:

```text
http://127.0.0.1:4173
```

To use a different port:

```bash
PORT=8080 python3 server.py
```

## Deploy

This app runs on Python 3.11+. SQLite local mode uses the Python standard library; Postgres/Neon deployment uses `psycopg`.

Common deployment command:

```bash
PORT=$PORT python3 server.py
```

For platforms that require binding to a public interface:

```bash
HOST=0.0.0.0 PORT=$PORT python3 server.py
```

Included deployment files:

- `Procfile`: process command for Heroku-style platforms
- `render.yaml`: Render web service blueprint
- `runtime.txt`: Python runtime pin
- `requirements.txt`: Postgres driver dependency for Neon/Postgres deployment
- `.env.example`: local environment variable template

Health check:

```text
GET /healthz
```

For production, use a managed Postgres database instead of the local SQLite file. `render.yaml` is configured to require Postgres by default.

Recommended when Supabase is unavailable:

- Neon Postgres for SQL data
- S3-compatible object storage such as Cloudflare R2 for uploaded files

Postgres setup files:

- `postgres/README.md`
- `postgres/schema.sql`
- `supabase/schema.sql`
- `supabase/seed_reference_data.sql`
- `supabase/README.md`

Use `postgres/schema.sql` for Neon or other managed Postgres providers. Use `supabase/schema.sql` only when deploying specifically to Supabase.

Set these deployment variables when switching the persistence layer to Neon/Postgres:

```bash
DATABASE_BACKEND=postgres
DATABASE_URL=postgresql://...
```

The app includes an initial psycopg adapter for Postgres. Run `postgres/schema.sql` and `supabase/seed_reference_data.sql` in the managed Postgres provider before setting `DATABASE_BACKEND=postgres`.

`/healthz` exposes `database_config` so you can confirm whether the deployment is running in SQLite mode or Postgres mode.

## OCR Settings

The MVP reads OCR readiness from environment variables:

로컬에서 계속 사용할 OCR 키는 프로젝트 루트의 `.env` 또는 `.env.local`에 저장할 수 있습니다. 이 파일들은 `.gitignore`에 포함되어 저장소에는 올라가지 않습니다.

```bash
GEMINI_API_KEY=...
OCR_PROVIDER=gemini
GEMINI_OCR_MODEL=gemini-3.5-flash
CLAUDE_API_KEY=...
CLAUDE_MODEL=claude-sonnet-5
APP_ACCESS_CODE=...
```

환경변수로 직접 실행할 수도 있습니다.

```bash
GEMINI_API_KEY=... CLAUDE_API_KEY=... OCR_PROVIDER=gemini GEMINI_OCR_MODEL=gemini-3.5-flash python3 server.py
```

고객용 웹 UI에서는 OCR 키를 입력하지 않습니다. OCR 키와 모델은 운영자가 서버 환경변수 또는 `.env` 파일로 설정하고, 화면에는 연결 준비 상태만 표시합니다.

`GEMINI_API_KEY`가 없으면 PDF와 이미지는 샘플 추출 결과를 사용하며, 검토자가 확인하는 흐름은 그대로 유지됩니다.

Claude 판단 보조도 같은 방식으로 서버에서만 설정합니다. `CLAUDE_API_KEY`가 있으면 판단 필요 항목에 대해 기준 근거 요약과 추가 질문 초안을 생성하고, 없으면 변환 초안은 그대로 생성하되 사람 검토 단계로 넘깁니다. 최종 회계정책 판단과 승인은 담당자 또는 회계 전문가가 수행합니다.

배포 URL을 공개할 때는 `APP_ACCESS_CODE`를 설정하세요. 값이 설정되면 프로젝트, 업로드, 변환, 승인, 다운로드 API는 웹 UI에서 접근 코드를 입력한 사용자에게만 열립니다. 값이 없으면 로컬 개발처럼 공개 모드로 동작합니다.

## Database Layout

Local SQLite file:

```text
data/gtf.sqlite3
```

Operational workflow tables:

- `projects`: 회사, 기준, 기간, 진행 상태
- `uploads`: 업로드 원본 파일 메타데이터
- `extractions`: OCR/Excel/CSV 추출 결과
- `statements`: 매핑된 계정 행과 체크리스트
- `conversions`: 변환 초안 JSON
- `reviews`: 사람 검토 및 승인 이력
- `audit_logs`: 입력값, 적용 룰, 검증, 변환, 승인 감사 로그

Reference data tables:

- `standard_accounts`: 내부 표준계정코드 DB
- `kgaap_accounts`: K-GAAP 계정명/별칭 DB
- `ifrs_accounts`: IFRS 계정 및 기준서 요약 DB
- `mapping_rules`: K-GAAP → IFRS 변환 룰 DB
- `checklist_items`: 판단 필요 항목별 체크리스트 DB
- `standards_references`: 기준서 참조 DB
- `financial_statement_templates`: DART 연동 전 자체 재무제표 표시 양식 DB

The app seeds the local reference tables from the MVP defaults at startup. In production, run `postgres/schema.sql` and `supabase/seed_reference_data.sql` in the managed Postgres provider, then manage those tables as controlled master data.

## API

- `GET /api/projects`
- `GET /healthz`
- `GET /api/ocr-config`
- `GET /api/ai-config`
- `GET /api/access-config`
- `GET /api/reference-data`
- `POST /api/projects`
- `GET /api/projects/{id}`
- `GET /api/projects/{id}/uploads`
- `POST /api/projects/{id}/uploads`
- `GET /api/projects/{id}/extractions`
- `POST /api/projects/{id}/uploads/{upload_id}/extract`
- `POST /api/projects/{id}/extractions/{extraction_id}/accept`
- `POST /api/projects/{id}/statements`
- `POST /api/projects/{id}/validate`
- `POST /api/projects/{id}/convert`
- `POST /api/projects/{id}/review`
- `GET /api/projects/{id}/audit`
- `GET /api/projects/{id}/exports/adjustments.csv`
- `GET /api/projects/{id}/exports/basis-report.txt`

## Notes

The OCR and LLM provider integrations are represented as boundaries in this MVP. DART can be added later; until then, conversion drafts use the internal financial statement template DB for presentation lines. Keep human approval as a required workflow step.
