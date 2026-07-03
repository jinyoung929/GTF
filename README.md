# GTF 회계기준 변환 서비스

K-GAAP 재무제표 데이터를 IFRS 검토 초안, 조정분개 후보, 판단 근거 리포트로 변환하는 회계·데이터 기반 업무 자동화 서비스입니다.

본 프로젝트는 교내 창업·경영 프로그램에서 최우수상을 받은 팀 프로젝트 아이디어를 바탕으로, 포트폴리오 공개를 위해 핵심 기능을 개인 MVP로 재구현한 버전입니다.

이 서비스는 회계처리를 자동 확정하는 시스템이 아닙니다. 리스, 개발비, 수익인식, 금융상품, 충당부채처럼 판단이 필요한 항목을 식별하고 변환 초안을 제시하며, 최종 회계정책 판단과 승인은 회사 담당자 또는 회계 전문가가 수행하는 구조입니다.

## Project Context

- 원 프로젝트: 교내 창업·경영 프로그램 팀 프로젝트
- 성과: 최우수상 수상
- 현재 저장소: 포트폴리오 공개용 개인 MVP 재구현
- 핵심 방향: 회계 데이터 표준화, 검토 가능한 자동화, 판단 근거 기록

## My Role

- 서비스 기획 및 사용자 흐름 설계
- K-GAAP 계정명 정규화 및 IFRS 표시 라인 매핑 구조 설계
- 리스, 개발비, 수익인식, 금융상품, 충당부채 등 판단 필요 항목 정의
- PDF/Excel/CSV 업로드 기반 계정 데이터 추출 흐름 구현
- 인증, 권한, API 라우팅, DB 스키마, 감사 로그 구조 재구현
- 회계 변환 로직 및 주요 API 테스트 추가

## Portfolio Rebuild Note

원 팀 프로젝트에서는 서비스 기획과 UX 흐름, 회계 업무 처리 로직 설계를 담당했습니다. 당시에는 구현 담당이 아니었기 때문에 포트폴리오에 공개할 수 있는 제 코드가 없었습니다. 그래서 당시 정의했던 문제, 사용자 작업 흐름, 검토·감사 로직, 회계 판단이 필요한 업무 규칙을 바탕으로 인증, 권한, DB 스키마, 테스트를 포함한 웹 MVP를 별도로 재구현했습니다.

이 저장소는 원 팀 프로젝트의 코드를 공개한 것이 아니라, 제가 담당했던 기획과 업무 흐름 설계를 실제 동작하는 코드로 검증하기 위해 다시 만든 포트폴리오용 구현입니다. 구현 과정에서는 AI 페어 프로그래밍을 활용해 반복 구현과 리팩터링 속도를 높였고, 요구사항 정의, UX 흐름, 회계 도메인 판단, 감사 로그 구조, 권한 정책, 테스트 기준은 직접 검토하며 정리했습니다.

## Why This Project Matters

회계·재무 업무에서 AI와 자동화는 결과를 빠르게 만드는 것만으로는 충분하지 않다고 생각했습니다. 실제 업무에 활용되기 위해서는 어떤 계정이 어떻게 매핑되었는지, 어떤 항목에 전문가 판단이 필요한지, 어떤 근거로 조정분개 후보가 생성되었는지가 남아야 합니다.

GTF는 이러한 문제의식에서 출발해 K-GAAP 재무 데이터를 IFRS 검토 초안으로 변환하되, 사람이 검토하고 승인할 수 있는 구조를 중심에 두었습니다. 이는 AI·ERP·데이터 플랫폼을 활용해 경영관리와 업무 운영 체계를 개선하는 Solution & AX 분야와도 맞닿아 있습니다.

## 주요 기능

- 사용자 회원가입 및 로그인
- K-GAAP 재무제표 PDF, Excel, CSV, 이미지 업로드
- DART 사업보고서형 PDF의 표 직접 추출
- 업로드 후 자동 분석 실행
- 수동 계정 입력 및 예시 입력
- 내부 표준계정코드 기반 계정명 정규화
- K-GAAP 계정명 → 내부 코드 → IFRS 표시 라인 매핑
- 단순 매핑 항목과 판단 필요 항목 분리
- 리스, 개발비, 수익인식, 금융상품, 충당부채 체크리스트 입력
- IFRS 변환 초안, 조정분개, 주석 초안 생성
- OpenAI 판단 보조 결과 카드 표시
- 검토 및 승인/수정 요청 기록
- 감사 로그 및 근거 리포트 다운로드

## 실행 방법

```bash
python3 server.py
```

기본 주소:

```text
http://127.0.0.1:4173
```

다른 포트로 실행:

```bash
PORT=4179 python3 server.py
```

## 사용 흐름

1. 웹 화면에서 이메일과 비밀번호로 회원가입 또는 로그인합니다.
2. 새 변환 프로젝트를 생성합니다.
3. PDF, Excel, CSV, 이미지 파일을 업로드합니다.
4. 업로드 후 자동 분석 결과를 확인합니다.
5. 추출 결과를 계정에 반영합니다.
6. 매핑 및 판단 필요 항목을 검토합니다.
7. 체크리스트를 입력합니다.
8. 변환 초안을 생성합니다.
9. 조정분개, 판단 근거, 주석 초안, OpenAI 보조 결과를 검토합니다.
10. 검토자 메모를 남기고 승인 또는 수정 요청을 기록합니다.

수동 입력 영역은 기본값 없이 비어 있습니다. 테스트용 데이터가 필요하면 상단의 `예시 입력` 버튼을 누르면 됩니다.

## 배포

Render 배포 기준 실행 명령:

```bash
HOST=0.0.0.0 python3 server.py
```

포함된 배포 파일:

- `Procfile`: Heroku 스타일 실행 명령
- `render.yaml`: Render 웹 서비스 설정
- `runtime.txt`: Python 런타임 버전
- `requirements.txt`: Postgres 및 PDF 파서 의존성
- `.env.example`: 로컬 환경변수 예시

헬스 체크:

```text
GET /healthz
```

## 환경변수

서버 환경변수 또는 로컬 `.env`, `.env.local` 파일로 설정합니다. 고객용 프론트엔드에는 API 키를 입력하지 않습니다.

```bash
DATABASE_BACKEND=postgres
DATABASE_URL=postgresql://...
GEMINI_API_KEY=...
OCR_PROVIDER=gemini
GEMINI_OCR_MODEL=gemini-3.5-flash
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

현재 로그인은 앱 자체의 사용자 계정과 세션 쿠키로 동작합니다. 예전 접근 코드 방식은 테스트 편의를 위해 비활성화되어 있습니다.

## 데이터베이스

로컬 SQLite:

```text
data/gtf.sqlite3
```

운영 배포에서는 Neon 등 관리형 Postgres 사용을 권장합니다.

주요 업무 테이블:

- `app_users`: 로그인 사용자
- `user_sessions`: 로그인 세션
- `projects`: 변환 프로젝트
- `uploads`: 업로드 원본 파일과 파일 바이트
- `extractions`: PDF/OCR/Excel/CSV 추출 결과
- `statements`: 매핑된 계정 행과 체크리스트
- `conversions`: 변환 초안 JSON
- `reviews`: 검토 및 승인 이력
- `audit_logs`: 입력값, 적용 룰, 변환, 검토 감사 로그

기준정보 테이블:

- `standard_accounts`: 내부 표준계정코드
- `kgaap_accounts`: K-GAAP 계정명/별칭
- `ifrs_accounts`: IFRS 계정 및 기준 요약
- `mapping_rules`: 변환 룰
- `checklist_items`: 판단 필요 항목 체크리스트
- `standards_references`: 기준서 참조
- `financial_statement_templates`: IFRS 표시 양식

## PDF 처리 방식

텍스트와 표 구조가 살아 있는 DART 사업보고서형 PDF는 OCR 전에 `pdfplumber`로 표를 직접 분석합니다. 재무제표 본문 구간을 우선 추출하고, 현금흐름표·자본변동표성 행은 제외하여 변환 가능한 핵심 계정만 매핑합니다.

이미지 스캔 PDF 또는 표 직접 추출이 어려운 파일은 Gemini OCR 경로로 전환할 수 있습니다. 이때 `GEMINI_API_KEY`가 서버에 설정되어 있어야 합니다.

## API

- `GET /api/auth/session`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{id}`
- `POST /api/projects/{id}/uploads`
- `POST /api/projects/{id}/uploads/{upload_id}/extract`
- `POST /api/projects/{id}/extractions/{extraction_id}/accept`
- `POST /api/projects/{id}/statements`
- `POST /api/projects/{id}/validate`
- `POST /api/projects/{id}/convert`
- `POST /api/projects/{id}/review`
- `GET /api/projects/{id}/audit`
- `GET /api/projects/{id}/exports/adjustments.csv`
- `GET /api/projects/{id}/exports/basis-report.txt`

## 주의 사항

- 변환 결과는 검토 초안이며 최종 재무제표가 아닙니다.
- 회계정책 판단, 할인율, 리스기간, 자산화 요건, 수익인식 방식 등은 사람이 검토해야 합니다.
- 배포 환경에서는 API 키를 코드에 저장하지 말고 Render 환경변수로 관리해야 합니다.
- 대량 파일 업로드 또는 장기 보관이 필요하면 파일 바이트를 DB에 직접 저장하는 방식 대신 S3 호환 스토리지 사용을 권장합니다.
