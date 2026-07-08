# GTF 회계기준 변환 서비스

K-GAAP 재무제표 데이터를 IFRS 검토 초안, 조정분개 후보, 판단 근거 리포트로 변환하는 회계·데이터 기반 업무 자동화 서비스입니다. PDF, Excel, CSV, 이미지 파일을 업로드하거나 DART API로 재무제표를 가져오면 계정 매핑, 판단 필요 항목 분류, 체크리스트 입력, 변환 초안 생성, 검토 로그 기록까지 한 화면에서 처리합니다.

본 프로젝트는 교내 창업·경영 프로그램에서 최우수상을 받은 팀 프로젝트 아이디어를 바탕으로, 포트폴리오 공개를 위해 핵심 기능을 개인 MVP로 재구현한 버전입니다.

이 서비스는 회계처리를 자동 확정하는 시스템이 아닙니다. 리스, 개발비, 수익인식, 금융상품, 충당부채처럼 판단이 필요한 항목을 식별하고 변환 초안을 제시하며, 최종 회계정책 판단과 승인은 회사 담당자 또는 회계 전문가가 수행하는 구조입니다.

<img width="1415" height="806" alt="스크린샷 2026-07-05 오후 9 41 56" src="https://github.com/user-attachments/assets/c5dae643-b72d-49c6-bb43-41689b34701c" />

<img width="1409" height="804" alt="스크린샷 2026-07-05 오후 9 49 41" src="https://github.com/user-attachments/assets/141d656d-486c-427f-8a0e-6b142d3fc2cf" />

<img width="1439" height="796" alt="스크린샷 2026-07-05 오후 9 50 36" src="https://github.com/user-attachments/assets/c2aee03e-2e13-438b-af86-9c79fdcb1a0c" />

<img width="1439" height="703" alt="스크린샷 2026-07-05 오후 9 58 20" src="https://github.com/user-attachments/assets/bd4e47d7-7b57-41b7-83ee-6b921c6f13f6" />

<img width="1440" height="900" alt="스크린샷 2026-07-05 오후 9 58 42" src="https://github.com/user-attachments/assets/840d541d-d288-4813-8163-0185fcba44d5" />

<img width="1440" height="813" alt="스크린샷 2026-07-05 오후 9 58 50" src="https://github.com/user-attachments/assets/696ee6ba-6acb-4391-8bb2-89f02ac649c4" />

<img width="1440" height="817" alt="스크린샷 2026-07-05 오후 9 59 01" src="https://github.com/user-attachments/assets/66ed5ad8-1a25-4101-8603-9bf2db2a72a4" />



## 프로젝트 배경과 기여 범위

- 원 프로젝트: 교내 창업·경영 프로그램 팀 프로젝트
- 성과: 최우수상 수상
- 현재 저장소: 포트폴리오 공개용 개인 MVP 재구현
- 핵심 방향: 회계 데이터 표준화, 검토 가능한 자동화, 판단 근거 기록

## 담당 역할

- 서비스 기획 및 사용자 흐름 설계
- K-GAAP 계정명 정규화 및 IFRS 표시 라인 매핑 구조 설계
- 리스, 개발비, 수익인식, 금융상품, 충당부채 등 판단 필요 항목 정의
- PDF, Excel, CSV, DART API 기반 계정 데이터 추출 흐름 구현
- 인증, 권한, API 라우팅, DB 스키마, 감사 로그 구조 재구현
- 회계 변환 로직 및 주요 API 테스트 추가

## 포트폴리오 재구현 설명

원 팀 프로젝트에서는 서비스 기획과 회계 처리 로직 설계를 담당했습니다. 공개 가능한 원본 코드가 없어, 당시 설계한 문제 정의와 처리 로직을 바탕으로 인증, 권한, DB 스키마, 테스트를 포함한 웹 MVP를 별도로 재구현했습니다.

이 저장소는 원 팀 프로젝트의 코드를 그대로 공개한 것이 아니라, 기획 의도와 도메인 로직을 포트폴리오에서 검증 가능한 형태로 다시 구성한 버전입니다. 구현 과정에서는 AI 페어 프로그래밍을 활용해 반복 구현과 리팩터링 속도를 높였고, 요구사항 정의, 회계 도메인 판단, 구조 분리 방향, 권한 정책, 테스트 기준은 직접 검토하며 정리했습니다.

## 프로젝트 의의

회계·재무 업무에서 AI와 자동화는 결과를 빠르게 만드는 것만으로는 충분하지 않다고 생각했습니다. 실제 업무에 활용되기 위해서는 어떤 계정이 어떻게 매핑되었는지, 어떤 항목에 전문가 판단이 필요한지, 어떤 근거로 조정분개 후보가 생성되었는지가 남아야 합니다.

GTF는 이러한 문제의식에서 출발해 K-GAAP 재무 데이터를 IFRS 검토 초안으로 변환하되, 사람이 검토하고 승인할 수 있는 구조를 중심에 두었습니다. 이는 AI, ERP, 데이터 플랫폼을 활용해 경영관리와 업무 운영 체계를 개선하는 Solution & AX 분야와도 맞닿아 있습니다.


## K-IFRS 기준서 반영 방식

이 MVP는 기준서 전문을 자동 해석하는 시스템이 아니라, K-GAAP 계정과목을 K-IFRS 검토 초안으로 바꿀 때 반복적으로 확인해야 하는 판단 포인트를 체크리스트와 변환 룰로 구조화한 버전입니다. 표준계정·계정명 별칭·체크리스트·기준서 문단 같은 기준정보 데이터는 `seeds/*.sql`을 단일 출처로 서버 시작 시 DB에 시드되고, 계산 로직(`gtf_app/domain.py`)은 계정키로만 분기하며 표시 정보는 전부 DB에서 조회해 주입받습니다. 계산기가 요구하는 계정키·체크리스트 키가 시드에서 빠지면 서버 시작 시 계약 검증이 실패해 조용한 불일치를 차단합니다.

| K-IFRS 기준서 | 적용 계정/영역 | 기술적 반영 |
| --- | --- | --- |
| K-IFRS 제1116호 리스 | 리스부채, 사용권자산 | 리스기간, 월 리스료, 증분차입이자율, 연장선택권을 체크리스트로 입력받고, 월 할인율로 리스료 현재가치를 계산해 K-GAAP 장부금액과의 조정액을 산출합니다. |
| K-IFRS 제1038호 무형자산 | 개발비, 무형자산 | 기술적 실현가능성, 완성 의도와 능력, 미래경제적효익, 원가의 신뢰성 있는 측정 가능성 4요건을 모두 충족해야 무형자산으로 분류하고, 하나라도 충족하지 않으면 연구개발비 처리 검토로 분기합니다. |
| K-IFRS 제1115호 고객과의 계약에서 생기는 수익 | 매출, 영업수익, 계약자산 | 계약 유형, 수행의무, 수익인식 시점, 변동대가 여부를 체크리스트로 받아 수익 인식 판단 근거와 주석 초안에 반영합니다. |
| K-IFRS 제1109호 금융상품 | 금융자산, 금융부채, 전환사채, 매출채권 | 사업모형, 계약상 현금흐름 특성(SPPI), 주요 계약조건, 기대신용손실 산정 방식과 연령분석표 보유 여부를 검토 항목으로 분리합니다. |
| K-IFRS 제1037호 충당부채, 우발부채 및 우발자산 | 충당부채 | 현재의무, 자원 유출 가능성, 금액의 신뢰성 있는 추정 가능성 3요건을 체크하고, 모두 충족하면 충당부채 인식 검토로, 미충족 시 공시 또는 추가 검토로 표시합니다. |
| K-IFRS 제1002호 재고자산 | 재고자산, 상품, 제품, 원재료 | 재고자산을 IFRS 표시 라인에 매핑하고, 원가와 순실현가능가치 비교가 필요하다는 검토 근거를 변환 리포트에 남깁니다. |
| K-IFRS 제1007호 현금흐름표 | 현금및현금성자산 | 현금및현금성자산 계정을 단순 매핑하되, 사용 제한 여부와 현금성자산 요건 확인이 필요하다는 기준 근거를 표시합니다. |

조정분개와 주석 초안은 위 기준서 판단을 자동 확정하지 않습니다. 대신 각 계정 행에 `mapping_type`을 부여해 단순 매핑과 판단 필요 항목을 분리하고, 판단 필요 항목은 검토자가 입력한 체크리스트 응답, 계산 근거, 기준서 요약, 승인/수정 요청 이력과 함께 감사 로그에 남기도록 설계했습니다.

### 기준서 문단 검색 DB와 AI 1차 분류

- K-GAAP(일반기업회계기준)과 K-IFRS 기준서의 판단 관련 문단 요약을 `standard_set`으로 분리한 `standards_paragraphs` 테이블에 시드하고, `GET /api/standards/search`로 계정·키워드·기준세트 기준 검색을 제공합니다. 변환 초안의 판단 필요 항목에는 해당 계정의 K-GAAP/K-IFRS 문단이 함께 첨부되어 화면, 근거 리포트, 검토용 Excel에 표시됩니다.
- 계정명이 키워드 사전 매핑에 실패한 미분류 계정(X9999)은 OpenAI가 표준계정 후보를 1차 분류로 제안합니다. 제안은 추출 결과에 후보로만 저장되고, 담당자가 추출 결과를 반영하는 시점에 확정되며, 이 과정("AI 제안 → 사람 확정")이 감사 로그에 기록됩니다. API 키가 없으면 제안 없이 기존 수동 분류 흐름으로 동작합니다.

## 주요 기능

- 관리자 계정 로그인 및 세션 쿠키 인증
- K-GAAP 재무제표 PDF, Excel, CSV, 이미지 업로드
- DART 사업보고서형 PDF의 표 직접 추출
- 업로드 후 자동 분석 실행
- 수동 계정 입력 및 예시 입력
- 내부 표준계정코드 기반 계정명 정규화
- 미분류 계정(X9999)에 대한 OpenAI 1차 분류 제안 및 반영 시 담당자 확정
- K-GAAP 계정명 → 내부 코드 → IFRS 표시 라인 매핑
- 단순 매핑 항목과 판단 필요 항목 분리
- 리스, 개발비, 수익인식, 금융상품, 충당부채 체크리스트 입력
- K-GAAP/K-IFRS 분리 기준서 문단 검색 DB 및 판단 항목별 근거 문단 표시
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

1. 웹 화면에서 관리자 이메일과 비밀번호로 로그인합니다.
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
DART_API_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
ADMIN_EMAIL=demo@gtf.local
ADMIN_PASSWORD=change-this-demo-password
```

현재 로그인은 앱 자체의 사용자 계정과 세션 쿠키로 동작합니다. 서버 시작 시 `ADMIN_EMAIL`/`ADMIN_PASSWORD`가 설정되어 있으면 `app_users`에 데모 계정 하나를 해시된 비밀번호로 시드하고, 이후 로그인은 저장된 사용자 해시를 검증합니다. 회원가입과 테스트 로그인 버튼은 제공하지 않습니다.

읽기 전용 데모 배포용 크레덴셜:

```text
Email: demo@gtf.local
Password: change-this-demo-password
```

`demo@gtf.local` 계정은 코드에서 읽기 전용으로 강제됩니다. 로그인, 조회, 리포트 다운로드 같은 GET 흐름은 사용할 수 있지만 프로젝트 생성, 업로드, 추출 반영, 변환 생성, 검토 승인, 삭제 같은 POST/DELETE 변경 작업은 403으로 차단됩니다. 운영 배포에서는 위 값을 그대로 사용하지 말고 Render 환경변수에서 별도 이메일과 강한 비밀번호로 교체하세요. 운영 계정을 읽기 전용으로 배포해야 할 때는 `ADMIN_READ_ONLY=true`를 설정합니다.


## DART와 Excel 산출물

`DART_API_KEY`가 설정되어 있으면 `POST /api/projects/{id}/dart/import`로 OpenDART 단일회사 전체 재무제표 계정 데이터를 가져옵니다. 요청에는 `corp_code`를 직접 넣거나, `company_name` 또는 `stock_code`와 `bsns_year`, `reprt_code`, `fs_div`를 전달할 수 있습니다. 가져온 DART 행은 기존 업로드와 동일하게 `extractions`에 저장되므로, 이후 `extractions/{extraction_id}/accept`, `validate`, `convert` 흐름을 그대로 사용합니다.

변환 초안 생성 후 `GET /api/projects/{id}/exports/review-workbook.xlsx`를 호출하면 검토용 Excel Workbook을 다운로드합니다. 포함 시트는 `01_원본_DART`, `02_계정매핑`, `03_조정분개`, `04_KIFRS_검토근거`, `05_감사로그`입니다.

## API

- `GET /api/auth/session`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/dart-config`
- `GET /api/standards/search?q=&account_key=&standard_set=`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{id}`
- `POST /api/projects/{id}/dart/import`
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
- `GET /api/projects/{id}/exports/review-workbook.xlsx`

## 주의 사항

- 변환 결과는 검토 초안이며 최종 재무제표가 아닙니다.
- 회계정책 판단, 할인율, 리스기간, 자산화 요건, 수익인식 방식 등은 사람이 검토해야 합니다.
- 배포 환경에서는 API 키를 코드에 저장하지 말고 Render 환경변수로 관리해야 합니다.
- 대량 파일 업로드 또는 장기 보관이 필요하면 파일 바이트를 DB에 직접 저장하는 방식 대신 S3 호환 스토리지 사용을 권장합니다.
