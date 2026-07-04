from __future__ import annotations

INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GTF 회계기준 변환</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header class="topbar">
    <div class="brand-block">
      <span class="eyebrow">Accounting conversion workspace</span>
      <h1>GTF 회계기준 변환</h1>
      <p>K-GAAP 재무제표 업로드부터 IFRS 검토 초안, 조정분개, 근거 리포트까지 한 화면에서 처리합니다.</p>
    </div>
    <div class="topbar-actions">
      <span class="status-chip">업로드</span>
      <span class="status-chip">검증</span>
      <span class="status-chip">리포트</span>
      <span id="userStatus" class="status-chip">로그인 확인 중</span>
      <button id="logoutBtn" class="ghost hidden">로그아웃</button>
      <button id="sampleBtn" class="secondary">예시 입력</button>
    </div>
  </header>

  <section id="authPanel" class="access-panel">
    <div>
      <span class="eyebrow">Admin sign in</span>
      <h2>관리자 로그인</h2>
      <p id="authMessage">운영자가 발급한 관리자 계정으로 접속하세요. 회원가입은 제공하지 않습니다.</p>
    </div>
    <div class="access-actions">
      <input id="loginEmail" type="email" autocomplete="email" placeholder="관리자 이메일">
      <input id="loginPassword" type="password" autocomplete="current-password" placeholder="관리자 비밀번호">
      <button id="loginBtn" class="primary">로그인</button>
    </div>
  </section>

  <section id="accessPanel" class="access-panel hidden">
    <div>
      <h2>접근 코드</h2>
      <p id="accessMessage">운영자가 발급한 접근 코드를 입력하세요.</p>
    </div>
    <div class="access-actions">
      <input id="accessCodeInput" type="password" autocomplete="current-password" placeholder="접근 코드">
      <button id="saveAccessCodeBtn" class="primary">저장</button>
      <button id="clearAccessCodeBtn" class="ghost">초기화</button>
    </div>
  </section>

  <main id="appShell" class="layout hidden">
    <aside class="sidebar panel">
      <div class="panel-head">
        <h2>프로젝트</h2>
        <button id="refreshProjectsBtn" class="ghost">새로고침</button>
      </div>
      <div id="projectList" class="project-empty">저장된 프로젝트가 없습니다.</div>
    </aside>

    <section class="panel project-panel primary-work-panel">
      <div class="panel-head">
        <div>
          <h2>새 변환 프로젝트</h2>
          <p>회사와 대상 기간을 정하면 업로드, 검증, 변환 단계가 열립니다.</p>
        </div>
        <span id="statusPill" class="pill">시작 전</span>
      </div>
      <form id="projectForm" class="grid">
        <label>회사명
          <input name="company_name" value="GTF Bio Inc." required>
        </label>
        <label>대상 기간
          <input name="period" value="2026">
        </label>
        <label>원 기준
          <select name="source_standard">
            <option>K-GAAP</option>
          </select>
        </label>
        <label>변환 기준
          <select name="target_standard">
            <option>IFRS</option>
            <option>US GAAP</option>
          </select>
        </label>
        <div class="form-actions">
          <button type="submit" class="primary">프로젝트 생성</button>
        </div>
      </form>
    </section>

    <section class="panel progress-panel workflow-panel">
      <div class="panel-head">
        <div>
          <h2>진행 흐름</h2>
          <p>원본 업로드, 데이터 검증, 변환 초안 생성, 사람 검토 순서로 진행됩니다.</p>
        </div>
        <span id="nextActionPill" class="pill">프로젝트 생성</span>
      </div>
      <div id="workflowSteps" class="steps"></div>
      <div id="nextActionGuide" class="next-action-guide">
        <strong>다음 단계</strong>
        <span>프로젝트를 생성하면 업로드와 매핑 작업을 시작할 수 있습니다.</span>
      </div>
      <div class="summary-grid">
        <div class="metric">
          <strong id="metricUploads">0</strong>
          <span>원본 파일</span>
        </div>
        <div class="metric">
          <strong id="metricExtractions">0</strong>
          <span>추출 결과</span>
        </div>
        <div class="metric">
          <strong id="metricStatements">0</strong>
          <span>매핑 계정</span>
        </div>
        <div class="metric">
          <strong id="metricJudgments">0</strong>
          <span>판단 필요</span>
        </div>
      </div>
    </section>

    <section class="panel input-panel">
      <div class="panel-head">
        <div>
          <h2>수동 입력</h2>
          <p>OCR 대신 계정명과 금액을 직접 붙여넣을 수 있습니다.</p>
        </div>
        <button id="mapBtn" class="primary" disabled>계정 매핑</button>
      </div>
      <textarea id="csvInput" spellcheck="false"></textarea>
    </section>

    <section class="panel upload-panel">
      <div class="panel-head">
        <div>
          <h2>원본 파일</h2>
          <p>PDF, Excel, CSV, 이미지를 업로드하면 추출 결과를 먼저 검토합니다.</p>
        </div>
        <button id="uploadBtn" class="primary" disabled>업로드 및 분석</button>
      </div>
      <label>재무제표 파일
        <input id="fileInput" type="file" accept=".pdf,.xlsx,.xls,.csv,.png,.jpg,.jpeg">
      </label>
      <div id="uploadList" class="file-empty">업로드된 파일이 없습니다.</div>
    </section>

    <section class="panel extraction-panel">
      <div class="panel-head">
        <h2>추출 결과</h2>
        <span id="extractionPill" class="pill">대기</span>
      </div>
      <div id="extractionList" class="file-empty">아직 추출 결과가 없습니다.</div>
    </section>

    <section class="panel wide">
      <div class="panel-head">
        <div>
          <h2>계정 매핑 및 판단항목</h2>
          <p>단순 매핑 항목과 회계정책 판단이 필요한 항목을 분리합니다.</p>
        </div>
        <div class="actions">
          <button id="validateBtn" class="secondary" disabled>검증</button>
          <button id="convertBtn" class="primary" disabled>변환 초안 생성</button>
        </div>
      </div>
      <div id="mappingTable" class="table-empty">프로젝트를 생성한 뒤 계정 데이터를 매핑하세요.</div>
      <div id="validation" class="validation-report"></div>
    </section>

    <section class="panel result-panel wide">
      <div class="panel-head">
        <div>
          <h2>변환 초안 및 리포트</h2>
          <p>조정분개, 표시 라인, 판단 근거, OpenAI 검토 메모를 확인합니다.</p>
        </div>
        <div class="actions export-actions">
          <button id="exportCsvBtn" class="download" disabled>조정분개 CSV</button>
          <button id="exportReportBtn" class="download primary-download" disabled>근거 리포트</button>
        </div>
      </div>
      <div id="outputBox" class="draft-empty">아직 생성된 변환 초안이 없습니다.</div>
    </section>

    <section class="panel review-panel">
      <div class="panel-head">
        <h2>검토 및 승인</h2>
        <span id="reviewPill" class="pill">대기</span>
      </div>
      <div class="grid">
        <label>검토자
          <input id="reviewerName" value="회계 검토자">
        </label>
        <label>검토 메모
          <input id="reviewMemo" placeholder="승인 근거 또는 수정 요청 사항">
        </label>
      </div>
      <div class="actions review-actions">
        <button id="requestChangesBtn" class="ghost" disabled>수정 요청</button>
        <button id="approveBtn" class="primary" disabled>초안 승인</button>
      </div>
    </section>

    <section class="panel audit-panel">
      <h2>감사 로그</h2>
      <div id="auditLog" class="log-empty">아직 기록된 이벤트가 없습니다.</div>
    </section>
  </main>

  <script src="/app.js"></script>
</body>
</html>
"""


STYLES_CSS = """
:root {
  color-scheme: light;
  --ink: #172126;
  --muted: #66737a;
  --line: #d7e0e3;
  --surface: #f3f6f7;
  --panel: #ffffff;
  --accent: #096b5b;
  --accent-hover: #075648;
  --accent-soft: #e8f5f1;
  --accent-2: #285176;
  --accent-2-soft: #edf3f8;
  --warn: #9c5b10;
  --danger: #9e2f2f;
  --success: #167455;
  --shadow: 0 8px 24px rgba(23, 33, 38, 0.06);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", sans-serif;
  color: var(--ink);
  background: var(--surface);
  line-height: 1.45;
}

.topbar {
  min-height: 116px;
  padding: 22px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  border-bottom: 1px solid var(--line);
  background: #fff;
}

.hidden { display: none !important; }

.brand-block {
  display: grid;
  gap: 5px;
  max-width: 780px;
}

.eyebrow {
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.topbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.status-chip {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  border: 1px solid #c9d9dd;
  border-radius: 999px;
  padding: 0 10px;
  background: #f8fbfb;
  color: #40555f;
  font-size: 12px;
  font-weight: 700;
}

.access-panel {
  margin: 16px 16px 0;
  padding: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid #cfe0dd;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--shadow);
}

.access-panel p { color: var(--muted); }

.access-actions {
  min-width: min(420px, 100%);
  display: grid;
  grid-template-columns: minmax(170px, 1fr) minmax(170px, 1fr) auto;
  gap: 8px;
}

h1, h2, p { margin: 0; }
h1 { font-size: 28px; line-height: 1.18; letter-spacing: 0; }
h2 { font-size: 16px; letter-spacing: 0; }
p { margin-top: 4px; color: var(--muted); font-size: 13px; }

.layout {
  display: grid;
  grid-template-columns: 280px minmax(340px, 0.95fr) minmax(420px, 1.05fr);
  grid-auto-flow: row dense;
  align-items: start;
  gap: 14px;
  padding: 14px;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  min-width: 0;
  box-shadow: 0 1px 2px rgba(24, 32, 39, 0.03);
}

.primary-work-panel {
  border-color: #bdd5d2;
  box-shadow: var(--shadow);
}

.sidebar {
  grid-column: 1;
  grid-row: 1 / span 4;
  position: sticky;
  top: 14px;
  max-height: calc(100vh - 28px);
  overflow: auto;
}

.project-panel { grid-column: 2 / 4; }

.progress-panel { grid-column: 2 / 4; }

.input-panel { grid-column: 2; }

.upload-panel { grid-column: 3; }

.extraction-panel { grid-column: 2 / 4; }

.result-panel {
  grid-column: 2 / 4;
}

.wide {
  grid-column: 2 / 4;
  grid-row: auto;
}

.review-panel { grid-column: 2; }

.audit-panel { grid-column: 3; }

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.panel-head > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

label {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}

input, select, textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--ink);
  background: #fff;
  font: inherit;
  font-size: 14px;
}

input, select { height: 38px; padding: 0 10px; }
textarea {
  min-height: 224px;
  resize: vertical;
  padding: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

button {
  min-height: 36px;
  border-radius: 6px;
  border: 1px solid var(--line);
  padding: 0 14px;
  font-weight: 650;
  cursor: pointer;
  background: #fff;
  color: var(--ink);
  white-space: nowrap;
}

button:not(:disabled):hover {
  border-color: #b7c8cd;
  background: #f8fbfb;
}

button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.primary {
  border-color: var(--accent);
  background: var(--accent);
  color: #fff;
}

.primary:not(:disabled):hover {
  border-color: var(--accent-hover);
  background: var(--accent-hover);
}

.ghost {
  background: #fff;
  color: var(--accent-2);
}

.secondary {
  border-color: #c7d7df;
  background: var(--accent-2-soft);
  color: var(--accent-2);
}

.secondary:not(:disabled):hover {
  border-color: #aebfca;
  background: #e2edf4;
}

.delete-upload-btn {
  border-color: #efc2c2;
  color: var(--danger);
}

.delete-upload-btn:not(:disabled):hover {
  border-color: #d99898;
  background: #fff4f4;
}

.download {
  border-color: #b8cec8;
  background: var(--accent-soft);
  color: var(--accent);
}

.download:not(:disabled):hover {
  border-color: #92bbb0;
  background: #dcf0ea;
}

.primary-download {
  border-color: var(--accent);
  background: var(--accent);
  color: #fff;
}

.primary-download:not(:disabled):hover {
  border-color: var(--accent-hover);
  background: var(--accent-hover);
}

.pill {
  min-width: 94px;
  text-align: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 10px;
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.export-actions {
  padding: 8px;
  border: 1px solid #c9ddd7;
  border-radius: 8px;
  background: #f7fcfa;
}

.review-actions { margin-top: 12px; }

.steps {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 16px;
  counter-reset: workflow;
}

.step {
  min-height: 72px;
  display: grid;
  align-content: center;
  gap: 4px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 11px 10px;
  background: #fbfcfc;
  color: var(--muted);
  position: relative;
}

.step strong {
  display: block;
  color: var(--ink);
  font-size: 12px;
  line-height: 1.25;
}

.step span {
  font-size: 11px;
}

.step.done {
  border-color: #9ccfc2;
  background: #eef8f5;
}

.step.current {
  border-color: var(--accent);
  box-shadow: inset 0 0 0 1px var(--accent);
  background: #f8fffc;
}

.step.done strong,
.step.current strong {
  color: var(--accent);
}

.next-action-guide {
  display: grid;
  gap: 4px;
  margin: 0 0 16px;
  padding: 12px 14px;
  border: 1px solid #c9ddd7;
  border-left: 4px solid var(--accent);
  border-radius: 8px;
  background: #f7fcfa;
}

.next-action-guide strong {
  color: var(--accent);
  font-size: 13px;
}

.next-action-guide span {
  color: var(--ink);
  font-size: 13px;
  line-height: 1.5;
}

.next-primary {
  box-shadow: 0 0 0 3px rgba(9, 107, 91, 0.16);
  border-color: var(--accent) !important;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric {
  min-height: 74px;
  display: grid;
  align-content: center;
  gap: 4px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px;
  background: #fff;
}

.metric strong {
  font-size: 24px;
  line-height: 1;
}

.metric span {
  color: var(--muted);
  font-size: 12px;
}

.config-list {
  display: grid;
  gap: 10px;
}

.config-list div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 38px;
  border-bottom: 1px solid var(--line);
}

.config-list div:last-child {
  border-bottom: 0;
}

.config-list span {
  color: var(--muted);
  font-size: 12px;
}

.config-list strong {
  text-align: right;
  font-size: 13px;
  font-weight: 700;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.45;
}

th, td {
  border-bottom: 1px solid var(--line);
  padding: 10px 9px;
  text-align: left;
  vertical-align: top;
}

th {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  background: #f5f8f8;
  position: sticky;
  top: 0;
  z-index: 1;
}

.table-scroll {
  max-width: 100%;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
}

.table-scroll table th,
.table-scroll table td {
  border-bottom: 1px solid var(--line);
}

.mapping-table th:nth-child(3),
.mapping-table td:nth-child(3),
.result-table th:nth-child(5),
.result-table th:nth-child(6),
.result-table td:nth-child(5),
.result-table td:nth-child(6) {
  text-align: right;
}

.result-table td:nth-child(7) {
  min-width: 300px;
}

.result-table th:nth-child(1),
.result-table td:nth-child(1),
.result-table th:nth-child(3),
.result-table td:nth-child(3) {
  min-width: 150px;
}

.num-cell {
  color: var(--ink);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.basis-cell {
  color: #43545b;
  line-height: 1.55;
}

.badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  background: #ecf5f3;
  color: var(--accent);
}

.badge.warn {
  background: #fff3df;
  color: var(--warn);
}

.checklist {
  display: grid;
  gap: 8px;
  min-width: 300px;
  padding: 10px;
  border: 1px solid #dce6e8;
  border-radius: 8px;
  background: #fbfdfd;
}

.checkitem {
  display: grid;
  gap: 5px;
  padding-bottom: 8px;
  border-bottom: 1px solid #edf2f3;
}

.checkitem:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.checklabel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--ink);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.45;
}

.required-mark {
  color: var(--warn);
  font-weight: 800;
}

.checklist input[type="checkbox"] {
  width: 16px;
  height: 16px;
  margin: 0;
}

.checkline {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  color: var(--ink);
  font-weight: 700;
  line-height: 1.45;
  font-size: 12px;
  min-height: 34px;
  padding-bottom: 8px;
  border-bottom: 1px solid #edf2f3;
}

.checkline:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.notice {
  min-height: 26px;
  margin-top: 12px;
  color: var(--muted);
  font-size: 13px;
}

.validation-report {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.validation-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: var(--muted);
  font-size: 13px;
}

.validation-checks {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 8px;
}

.validation-check {
  display: grid;
  gap: 4px;
  min-height: 74px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfcfc;
  font-size: 12px;
}

.validation-check strong {
  color: var(--ink);
  font-size: 13px;
}

.validation-check span {
  color: var(--muted);
  line-height: 1.45;
}

.validation-check.pass {
  border-color: #bddbd4;
  background: #f2faf7;
}

.validation-check.warning {
  border-color: #f0d19a;
  background: #fff8ec;
}

.validation-check.error {
  border-color: #efb8b8;
  background: #fff4f4;
}

pre {
  min-height: 220px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #101820;
  color: #f5fbfc;
  font-size: 12px;
}

.draft-empty {
  color: var(--muted);
  font-size: 13px;
}

.draft-view {
  display: grid;
  gap: 18px;
}

.draft-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px 16px;
  align-items: center;
  padding: 14px;
  border: 1px solid #cfe0dd;
  border-radius: 8px;
  background: #f6fbfa;
  color: var(--muted);
  font-size: 13px;
}

.draft-summary strong {
  color: var(--ink);
  font-size: 15px;
}

.draft-section {
  display: grid;
  gap: 10px;
}

.draft-section h3 {
  margin: 0;
  color: var(--ink);
  font-size: 14px;
}

.draft-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 10px;
}

.draft-card {
  display: grid;
  gap: 7px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fbfcfc;
  font-size: 12px;
}

.draft-card strong {
  color: var(--ink);
  font-size: 13px;
}

.draft-card span {
  color: var(--muted);
  line-height: 1.45;
}

.ai-summary-card {
  grid-column: 1 / -1;
  border-color: #c7d7df;
  background: #f7fbfd;
}

.ai-card {
  border-color: #d6e3e6;
  background: #fff;
}

.ai-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.risk-pill {
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 800;
  background: #edf3f8;
  color: var(--accent-2);
}

.risk-pill.medium {
  background: #fff3df;
  color: var(--warn);
}

.risk-pill.high {
  background: #fff0f0;
  color: var(--danger);
}

.question-list {
  margin: 0;
  padding-left: 16px;
  color: var(--muted);
}

.question-list li {
  margin: 3px 0;
}

.log-item {
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
  font-size: 13px;
}

.log-item strong { display: block; }
.log-item span { color: var(--muted); font-size: 12px; }
.log-detail {
  display: grid;
  gap: 5px;
  margin-top: 8px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfcfc;
}

.log-detail-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}

.log-detail-row strong {
  color: var(--ink);
  font-size: 12px;
}
.table-empty, .log-empty { color: var(--muted); font-size: 13px; }
.file-empty {
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
  padding: 10px 0;
}
.file-item {
  display: grid;
  gap: 6px;
  margin-top: 10px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfcfc;
  font-size: 13px;
}
.file-item span { color: var(--muted); font-size: 12px; }
.file-item table { margin-top: 8px; }
.item-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
.issues {
  margin: 8px 0 0;
  padding-left: 18px;
  color: var(--warn);
  font-size: 12px;
}
.project-empty { color: var(--muted); font-size: 13px; }
.project-item {
  width: 100%;
  min-height: 64px;
  display: grid;
  gap: 4px;
  margin-top: 8px;
  padding: 11px 12px;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
}
.project-item strong { font-size: 13px; line-height: 1.25; }
.project-item span { color: var(--muted); font-size: 12px; font-weight: 500; }
.project-item.active {
  border-color: var(--accent);
  background: #eef7f4;
}

.project-item:hover:not(:disabled) {
  border-color: #b8c9ce;
  background: #fbfcfc;
}

@media (max-width: 980px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { position: static; max-height: none; }
  .project-panel,
  .progress-panel,
  .input-panel,
  .upload-panel,
  .extraction-panel,
  .result-panel,
  .wide,
  .review-panel,
  .audit-panel,
  .sidebar { grid-column: auto; grid-row: auto; }
  .wide { grid-row: auto; }
  .steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .topbar { align-items: flex-start; flex-direction: column; padding: 16px; }
  .access-panel { align-items: stretch; flex-direction: column; margin: 10px 10px 0; }
  .access-actions { grid-template-columns: 1fr; }
  .layout { padding: 10px; }
  .grid { grid-template-columns: 1fr; }
  .form-actions { justify-content: stretch; }
  .form-actions button { width: 100%; }
  .panel-head { align-items: flex-start; flex-direction: column; }
  .panel-head > .actions { width: 100%; }
  .panel-head > .actions button { flex: 1; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  table, thead, tbody, tr, th, td { display: block; }
  th { display: none; }
  td { padding: 8px 0; }
}
"""


APP_JS = """
let activeProjectId = null;
let statements = [];
let uploads = [];
let extractions = [];
let hasDraft = false;
let projects = [];
let accessRequired = false;
let currentUser = null;
let lastValidationStatus = null;
let currentStatus = null;

const $ = (selector) => document.querySelector(selector);
const accessStorageKey = "gtfAccessCode";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function localizeText(value) {
  return String(value ?? "-")
    .replaceAll("review required", "추가 검토 필요")
    .replaceAll("Human review required", "사람 검토 필요")
    .replaceAll("Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.", "Anthropic API 크레딧이 부족합니다. Anthropic 콘솔의 Plans & Billing에서 크레딧을 충전해야 합니다.");
}

function riskLabel(value) {
  const labels = { low: "낮음", medium: "중간", high: "높음" };
  return labels[value] || value || "-";
}

function savedAccessCode() {
  return sessionStorage.getItem(accessStorageKey) || "";
}

function authHeaders(baseHeaders = {}) {
  return { ...baseHeaders };
}

function isReadOnlyUser() {
  return Boolean(currentUser && currentUser.is_read_only);
}

function renderAccessPanel(message = "") {
  const panel = $("#accessPanel");
  if (!panel) return;
  panel.classList.toggle("hidden", !accessRequired);
  if (!accessRequired) return;
  const hasCode = Boolean(savedAccessCode());
  $("#accessMessage").textContent = message || (hasCode ? "접근 코드가 저장되었습니다. API 요청에 자동 적용됩니다." : "운영자가 발급한 접근 코드를 입력하세요.");
  $("#accessCodeInput").value = hasCode ? savedAccessCode() : "";
}

function handleAccessError(data) {
  if (data && data.login_required) {
    currentUser = null;
    renderAuthPanel(data.error || "로그인이 필요합니다.");
  } else if (data && data.access_required) {
    accessRequired = true;
    renderAccessPanel(data.error || "접근 코드가 필요합니다.");
  }
}

function renderAuthPanel(message = "") {
  const isLoggedIn = Boolean(currentUser);
  $("#authPanel").classList.toggle("hidden", isLoggedIn);
  $("#appShell").classList.toggle("hidden", !isLoggedIn);
  $("#logoutBtn").classList.toggle("hidden", !isLoggedIn);
  $("#sampleBtn").disabled = !isLoggedIn;
  $("#userStatus").textContent = isLoggedIn ? `${currentUser.email}${isReadOnlyUser() ? " · 읽기 전용" : ""}` : "로그인 필요";
  const projectSubmit = $("#projectForm button[type='submit']");
  if (projectSubmit) projectSubmit.disabled = !isLoggedIn || isReadOnlyUser();
  if (!isLoggedIn) {
    $("#authMessage").textContent = message || "운영자가 발급한 관리자 계정으로 접속하세요. 회원가입은 제공하지 않습니다.";
  }
}

const workflowDefinitions = [
  { key: "created", title: "프로젝트", hint: "기본 정보" },
  { key: "source_uploaded", title: "원본", hint: "파일 업로드" },
  { key: "extracted", title: "추출", hint: "OCR/Excel" },
  { key: "mapped", title: "매핑", hint: "계정 분류" },
  { key: "draft_generated", title: "초안", hint: "조정분개" },
  { key: "approved", title: "승인", hint: "사람 검토" }
];

const statusLabels = {
  created: "생성됨",
  source_uploaded: "원본 업로드",
  extracted: "추출 완료",
  mapped: "매핑 완료",
  draft_generated: "초안 생성",
  approved: "승인 완료",
  changes_requested: "수정 요청",
  connected: "연결 완료",
  not_configured: "키 미설정",
  skipped: "건너뜀",
  pending_ocr: "OCR 대기",
  analyzing: "분석 중",
  needs_review: "검토 필요",
  accepted: "반영 완료",
  failed: "실패",
  simple: "단순 매핑",
  judgment: "판단 필요",
  pass: "통과",
  passed: "통과",
  warning: "주의",
  error: "오류",
  "project.created": "프로젝트 생성",
  "source.uploaded": "원본 파일 업로드",
  "source.deleted": "원본 파일 삭제",
  "source.extracted": "원본 데이터 추출",
  "extraction.accepted": "추출 결과 반영",
  "statements.mapped": "계정 매핑",
  "validation.completed": "데이터 검증",
  "conversion.generated": "변환 초안 생성",
  "review.recorded": "검토 결과 기록",
  local_csv_parser: "CSV 파서",
  local_xlsx_parser: "Excel 파서",
  local_pdf_table_parser: "PDF 표 분석",
  unsupported_excel: "지원하지 않는 Excel",
  ocr_placeholder: "OCR 대기 샘플",
  ocr_not_configured: "분석 설정 필요",
  gemini: "Gemini OCR",
  openai: "OpenAI"
};

function labelFor(value) {
  return statusLabels[value] || value || "-";
}

function summarizeValue(value) {
  if (Array.isArray(value)) {
    if (value.length === 0) return "없음";
    if (value.length <= 3 && value.every((item) => typeof item !== "object")) {
      return value.map((item) => String(item)).join(", ");
    }
    return `${value.length}개 항목`;
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value);
    if (keys.length === 0) return "없음";
    return keys.slice(0, 4).map((key) => `${key}: ${summarizeValue(value[key])}`).join(" / ");
  }
  if (typeof value === "boolean") return value ? "예" : "아니오";
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number(value).toLocaleString();
  if (typeof value === "string" && statusLabels[value]) return labelFor(value);
  return String(value);
}

function auditDetailRows(log) {
  const detail = log.detail || {};
  const labels = {
    id: "ID",
    company_name: "회사명",
    source_standard: "원 기준",
    target_standard: "목표 기준",
    period: "기간",
    status: "상태",
    upload_id: "업로드 ID",
    original_name: "파일명",
    content_type: "파일 형식",
    size_bytes: "파일 크기",
    extraction_id: "추출 ID",
    provider: "처리 방식",
    ocr_config: "추출 방식",
    row_count: "행 수",
    issues: "이슈",
    count: "처리 건수",
    source: "입력 출처",
    responses: "체크리스트 응답",
    entry_count: "조정분개 수",
    review_id: "검토 ID",
    decision: "검토 결과",
    memo: "검토 메모",
    conversion_id: "변환 초안 ID",
    warnings: "주의",
    checks: "검증 항목",
    total_amount: "합계",
    judgment_count: "판단 필요",
    simple_count: "단순 매핑",
    ai_status: "AI 상태",
    claude_status: "Claude 상태"
  };
  const preferred = [
    "company_name", "period", "source_standard", "target_standard", "original_name",
    "content_type", "size_bytes", "provider", "row_count", "count", "entry_count",
    "status", "decision", "memo", "issues", "warnings", "checks", "responses",
    "total_amount", "judgment_count", "simple_count"
  ];
  const keys = [...preferred.filter((key) => key in detail), ...Object.keys(detail).filter((key) => !preferred.includes(key))];
  return keys.slice(0, 10).map((key) => `
    <div class="log-detail-row">
      <strong>${escapeHtml(labels[key] || key)}</strong>
      <span>${escapeHtml(summarizeValue(detail[key]))}</span>
    </div>
  `).join("");
}

function workflowIndex(status) {
  if (status === "changes_requested") return 4;
  const index = workflowDefinitions.findIndex((step) => step.key === status);
  return index >= 0 ? index : -1;
}

function nextActionLabel(status) {
  if (!status) return "프로젝트 생성";
  if (status === "created") return "원본 업로드";
  if (status === "source_uploaded") return "추출 실행";
  if (status === "extracted") return "계정 반영";
  if (status === "mapped") return "변환 초안 생성";
  if (status === "draft_generated") return "검토 및 승인";
  if (status === "changes_requested") return "수정 후 재검토";
  if (status === "approved") return "완료";
  return labelFor(status);
}

function nextActionDetail(status) {
  if (!activeProjectId) return "프로젝트를 생성하면 업로드와 매핑 작업을 시작할 수 있습니다.";
  if (status === "created") return "재무제표 파일을 선택한 뒤 원본 파일 영역의 업로드 및 분석 버튼을 누르세요.";
  if (status === "source_uploaded") return "업로드 파일 목록에서 분석 실행을 눌러 추출 결과를 만드세요.";
  if (status === "extracted") return "추출 결과를 확인한 뒤 계정 반영 버튼을 눌러 매핑 테이블에 추가하세요.";
  if (status === "mapped") {
    if (lastValidationStatus === "passed" || lastValidationStatus === "warning") {
      return "검증 결과를 확인했습니다. 중대한 오류가 없다면 변환 초안 생성 버튼을 누르세요.";
    }
    return "변환 초안 생성 전에 검증 버튼을 눌러 중복, 단위, 기간, 손익계산서 필수 항목을 확인하세요.";
  }
  if (status === "draft_generated") return "변환 초안과 OpenAI 판단 보조 결과를 검토한 뒤 리포트를 다운로드하거나 승인하세요.";
  if (status === "changes_requested") return "수정 요청 내용을 반영한 뒤 다시 검증과 변환 초안 생성을 진행하세요.";
  if (status === "approved") return "승인이 완료되었습니다. 근거 리포트와 조정분개 CSV를 내려받아 보관하세요.";
  return "현재 단계의 안내에 따라 다음 버튼을 선택하세요.";
}

function nextActionTarget(status) {
  if (!activeProjectId) return "#projectForm button[type='submit']";
  if (status === "created") return "#uploadBtn";
  if (status === "source_uploaded") return ".extract-btn";
  if (status === "extracted") return ".accept-extraction-btn";
  if (status === "mapped") {
    return (lastValidationStatus === "passed" || lastValidationStatus === "warning") ? "#convertBtn" : "#validateBtn";
  }
  if (status === "draft_generated") return "#exportReportBtn";
  return "";
}

function updateNextActionGuide(status) {
  const guide = $("#nextActionGuide");
  if (!guide) return;
  guide.innerHTML = `
    <strong>다음 단계 · ${escapeHtml(nextActionLabel(status))}</strong>
    <span>${escapeHtml(nextActionDetail(status))}</span>
  `;
  document.querySelectorAll(".next-primary").forEach((element) => element.classList.remove("next-primary"));
  const target = nextActionTarget(status);
  if (!target) return;
  const element = document.querySelector(target);
  if (element && !element.disabled) element.classList.add("next-primary");
}

function updateProgress(status) {
  const currentIndex = workflowIndex(status);
  $("#nextActionPill").textContent = nextActionLabel(status);
  $("#workflowSteps").innerHTML = workflowDefinitions.map((step, index) => {
    const state = index < currentIndex ? "done" : index === currentIndex ? "current" : "";
    return `
      <div class="step ${state}">
        <strong>${index + 1}. ${step.title}</strong>
        <span>${step.hint}</span>
      </div>
    `;
  }).join("");
  updateNextActionGuide(status);
}

function updateMetrics() {
  $("#metricUploads").textContent = uploads.length;
  $("#metricExtractions").textContent = extractions.length;
  $("#metricStatements").textContent = statements.length;
  $("#metricJudgments").textContent = statements.filter((statement) => statement.mapping_type === "judgment").length;
}

async function refreshOcrConfig() {
  if (!$("#ocrModePill")) return;
  const config = await api("/api/ocr-config");
  $("#ocrModePill").textContent = config.api_key_ready ? "연결 준비" : "샘플 모드";
  $("#ocrProvider").textContent = labelFor(config.provider) || config.provider;
  $("#ocrModel").textContent = config.model;
  $("#ocrApiKey").textContent = config.api_key_ready ? "서버 설정됨" : "관리자 설정 필요";
  $("#ocrFailureMode").textContent = config.manual_review_on_failure ? "수동 검토" : "자동 실패";
}

async function refreshAiConfig() {
  if (!$("#aiModePill")) return;
  const config = await api("/api/ai-config");
  $("#aiModePill").textContent = config.api_key_ready ? "연결 준비" : "키 미설정";
  $("#aiProvider").textContent = labelFor(config.provider) || config.provider;
  $("#aiModel").textContent = config.model;
  $("#aiApiKey").textContent = config.api_key_ready ? "서버 설정됨" : "관리자 설정 필요";
  $("#aiReviewMode").textContent = config.human_review_required ? "사람 최종 검토" : "자동 확정";
}

async function refreshAccessConfig() {
  const res = await fetch("/api/access-config");
  const config = await res.json();
  accessRequired = Boolean(config.enabled);
  renderAccessPanel();
  return config;
}

async function refreshSession() {
  const res = await fetch("/api/auth/session", { credentials: "same-origin" });
  const data = await res.json().catch(() => ({}));
  currentUser = data.authenticated ? data.user : null;
  renderAuthPanel();
  return currentUser;
}

async function submitAuth() {
  const email = $("#loginEmail").value.trim();
  const password = $("#loginPassword").value;
  if (!email || !password) {
    renderAuthPanel("관리자 이메일과 비밀번호를 입력하세요.");
    return;
  }
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    currentUser = data.user;
    $("#loginPassword").value = "";
    renderAuthPanel();
    resetWorkspace();
    await refreshProtectedData();
  } catch (error) {
    renderAuthPanel(error.message || "로그인 처리에 실패했습니다.");
  }
}

async function refreshProtectedData() {
  await refreshProjects();
}

async function refreshReferenceData() {
  if (!$("#referenceDbPill")) return;
  const data = await api("/api/reference-data");
  const total = (data.summary || []).reduce((sum, item) => sum + Number(item.count || 0), 0);
  $("#referenceDbPill").textContent = `${total.toLocaleString()}건`;
  $("#referenceDbList").innerHTML = (data.summary || []).map((item) => `
    <div>
      <span>${escapeHtml(item.label)}</span>
      <strong>${Number(item.count || 0).toLocaleString()}건</strong>
    </div>
  `).join("");
}

function csvSample() {
  return [
    "계정명,금액",
    "현금및현금성자산,120000000",
    "매출채권,88000000",
    "재고자산,54000000",
    "리스부채,30000000",
    "개발비,45000000",
    "제품매출,240000000",
    "전환사채,70000000",
    "충당부채,18000000"
  ].join("\\n");
}

async function api(path, options = {}) {
  const headers = authHeaders({ "Content-Type": "application/json", ...(options.headers || {}) });
  const res = await fetch(path, {
    ...options,
    headers,
    credentials: "same-origin"
  });
  const data = await res.json().catch(() => ({}));
  handleAccessError(data);
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

async function uploadApi(path, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(path, {
    method: "POST",
    headers: authHeaders(),
    credentials: "same-origin",
    body: form
  });
  const data = await res.json().catch(() => ({}));
  handleAccessError(data);
  if (!res.ok) throw new Error(data.error || "Upload failed");
  return data;
}

async function downloadApi(path, filename) {
  const res = await fetch(path, { headers: authHeaders(), credentials: "same-origin" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    handleAccessError(data);
    throw new Error(data.error || "Download failed");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function setStatus(text) {
  currentStatus = text;
  $("#statusPill").textContent = labelFor(text);
  updateProgress(text);
}

function setReviewState(text) {
  $("#reviewPill").textContent = labelFor(text);
}

function setWorkflowEnabled(enabled) {
  $("#mapBtn").disabled = !enabled || isReadOnlyUser();
  $("#uploadBtn").disabled = !enabled || isReadOnlyUser();
  updateNextActionGuide(currentStatus);
}

function setExportEnabled(enabled) {
  $("#exportCsvBtn").disabled = !enabled;
  $("#exportReportBtn").disabled = !enabled;
}

function getChecklistResponses() {
  const responses = {};
  document.querySelectorAll("[data-statement]").forEach((cell) => {
    const id = cell.dataset.statement;
    responses[id] = {};
    cell.querySelectorAll("input").forEach((input) => {
      if (input.type === "checkbox") {
        responses[id][input.name] = input.checked;
      } else if (input.type === "number") {
        responses[id][input.name] = input.value === "" ? null : Number(input.value);
      } else {
        responses[id][input.name] = input.value;
      }
    });
  });
  return responses;
}

function checklistHtml(statement) {
  if (!statement.checklist || statement.checklist.length === 0) {
    return '<span class="badge">1:1 매핑</span>';
  }
  const controls = statement.checklist.map((item) => {
    const requiredMark = item.required ? '<span class="required-mark">필수</span>' : '<span class="badge">선택</span>';
    const placeholder = item.type === "number" ? "숫자 입력" : "내용 입력";
    if (item.type === "boolean") {
      return `
        <label class="checkline">
          <input type="checkbox" name="${item.key}">
          <span>${item.label}</span>
          ${requiredMark}
        </label>
      `;
    }
    return `
      <label class="checkitem">
        <span class="checklabel"><span>${item.label}</span>${requiredMark}</span>
        <input type="${item.type === "number" ? "number" : "text"}" name="${item.key}" placeholder="${placeholder}">
      </label>
    `;
  }).join("");
  return `<div class="checklist" data-statement="${statement.id}">${controls}</div>`;
}

function renderMapping() {
  updateMetrics();
  if (!statements.length) {
    $("#mappingTable").innerHTML = '<div class="table-empty">아직 매핑된 계정이 없습니다.</div>';
    return;
  }
  const rows = statements.map((s) => `
    <tr>
      <td>${s.account_name}</td>
      <td>${s.standard_code}<br>${s.normalized_account}</td>
      <td>${Number(s.amount).toLocaleString()}</td>
      <td><span class="badge ${s.mapping_type === "judgment" ? "warn" : ""}">${labelFor(s.mapping_type)}</span></td>
      <td>${s.rule_summary}</td>
      <td>${checklistHtml(s)}</td>
    </tr>
  `).join("");
  $("#mappingTable").innerHTML = `
    <div class="table-scroll">
    <table class="mapping-table">
      <thead>
        <tr>
          <th>K-GAAP 계정</th>
          <th>내부 코드</th>
          <th>금액</th>
          <th>유형</th>
          <th>적용 룰</th>
          <th>체크리스트</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    </div>
  `;
}

function renderValidation(result) {
  if (!result) {
    $("#validation").innerHTML = "";
    return;
  }
  const issueItems = [...(result.issues || []), ...(result.warnings || [])]
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const checks = (result.checks || []).map((check) => `
    <div class="validation-check ${escapeHtml(check.status)}">
      <strong>${escapeHtml(check.name)} · ${labelFor(check.status)}</strong>
      <span>${escapeHtml(check.detail)}</span>
    </div>
  `).join("");
  $("#validation").innerHTML = `
    <div class="validation-summary">
      <span class="badge ${result.status === "passed" ? "" : "warn"}">${labelFor(result.status)}</span>
      <span>${Number(result.row_count || 0).toLocaleString()}개 행</span>
      <span>단순 매핑 ${Number(result.simple_count || 0).toLocaleString()}개</span>
      <span>판단 필요 ${Number(result.judgment_count || 0).toLocaleString()}개</span>
      <span>합계 ${Number(result.total_amount || 0).toLocaleString()}</span>
    </div>
    ${checks ? `<div class="validation-checks">${checks}</div>` : ""}
    ${issueItems ? `<ul class="issues">${issueItems}</ul>` : ""}
  `;
}

function renderDraft(draft) {
  if (!draft) {
    $("#outputBox").className = "draft-empty";
    $("#outputBox").innerHTML = "아직 생성된 변환 초안이 없습니다.";
    return;
  }
  $("#outputBox").className = "draft-view";
  const entries = draft.entries || [];
  const entryRows = entries.map((entry) => `
    <tr>
      <td>${escapeHtml(entry.source_account)}</td>
      <td>${escapeHtml(entry.standard_code)}</td>
      <td>${escapeHtml(entry.target_account)}</td>
      <td>${escapeHtml(entry.statement_type || "-")} · ${escapeHtml(entry.statement_line_item || "-")}</td>
      <td class="num-cell">${Number(entry.amount || 0).toLocaleString()}</td>
      <td class="num-cell">${Number(entry.adjustment || 0).toLocaleString()}</td>
      <td class="basis-cell">${escapeHtml(localizeText(entry.calculation || entry.basis || "-"))}</td>
    </tr>
  `).join("");
  const judgmentCards = (draft.judgment_items || []).map((item) => `
    <div class="draft-card">
      <strong>${escapeHtml(item.account)}</strong>
      <span>${escapeHtml(localizeText(item.basis))}</span>
    </div>
  `).join("");
  const noteCards = (draft.draft_notes || []).map((note) => `
    <div class="draft-card">
      <strong>${escapeHtml(note.account)}</strong>
      <span>${escapeHtml(localizeText(note.draft_note))}</span>
    </div>
  `).join("");
  const ai = draft.ai_assistance || {};
  const aiCards = (ai.items || []).map((item) => {
    const risk = String(item.risk_level || "").toLowerCase();
    const questions = (item.additional_questions || []).map((question) => `<li>${escapeHtml(question)}</li>`).join("");
    return `
      <div class="draft-card ai-card">
        <div class="ai-card-head">
          <strong>${escapeHtml(item.account || "-")}</strong>
          <span class="risk-pill ${escapeHtml(risk)}">위험도 ${escapeHtml(riskLabel(item.risk_level))}</span>
        </div>
        <span><strong>분류 방향</strong> ${escapeHtml(localizeText(item.classification_hint || "-"))}</span>
        <span><strong>검토 메모</strong> ${escapeHtml(localizeText(item.review_note || "-"))}</span>
        <span><strong>근거 요약</strong> ${escapeHtml(localizeText(item.basis_summary || "-"))}</span>
        ${questions ? `<ul class="question-list">${questions}</ul>` : '<span><strong>추가 질문</strong> -</span>'}
      </div>
    `;
  }).join("");
  const aiIssues = (ai.issues || []).map((issue) => `<li>${escapeHtml(localizeText(issue))}</li>`).join("");
  const aiStatus = `${labelFor(ai.status || "not_configured")} · ${ai.model || "모델 미설정"}`;
  $("#outputBox").innerHTML = `
    <div class="draft-summary">
      <strong>${escapeHtml(draft.project?.company_name || "-")} · ${escapeHtml(draft.project?.period || "-")}</strong>
      <span>${escapeHtml(draft.project?.source_standard || "K-GAAP")} → ${escapeHtml(draft.project?.target_standard || "IFRS")} · ${escapeHtml(localizeText(draft.review_status || "검토 필요"))}</span>
      <span>생성 시각 ${draft.generated_at ? new Date(draft.generated_at).toLocaleString() : "-"}</span>
    </div>
    <div class="draft-section">
      <h3>조정분개 리스트</h3>
      <div class="table-scroll">
      <table class="result-table">
        <thead>
          <tr>
            <th>원 계정</th>
            <th>코드</th>
            <th>IFRS 계정</th>
            <th>표시 양식</th>
            <th>금액</th>
            <th>조정액</th>
            <th>계산/근거</th>
          </tr>
        </thead>
        <tbody>${entryRows || '<tr><td colspan="7">생성된 조정분개가 없습니다.</td></tr>'}</tbody>
      </table>
      </div>
    </div>
    <div class="draft-section">
      <h3>판단 필요 항목</h3>
      <div class="draft-list">${judgmentCards || '<div class="draft-empty">판단 필요 항목이 없습니다.</div>'}</div>
    </div>
    <div class="draft-section">
      <h3>OpenAI 판단 보조</h3>
      <div class="draft-list">
        <div class="draft-card ai-summary-card">
          <strong>${escapeHtml(aiStatus)}</strong>
          <span>${escapeHtml(localizeText(ai.overall_note || "OpenAI 판단 보조 결과가 없습니다."))}</span>
          ${aiIssues ? `<ul class="issues">${aiIssues}</ul>` : ""}
        </div>
        ${aiCards || '<div class="draft-empty">표시할 판단 보조 결과가 없습니다.</div>'}
      </div>
    </div>
    <div class="draft-section">
      <h3>주석 초안</h3>
      <div class="draft-list">${noteCards || '<div class="draft-empty">생성된 주석 초안이 없습니다.</div>'}</div>
    </div>
  `;
}

function renderUploads() {
  updateMetrics();
  if (!uploads.length) {
    $("#uploadList").innerHTML = '<div class="file-empty">업로드된 파일이 없습니다.</div>';
    return;
  }
  $("#uploadList").innerHTML = uploads.map((file) => `
      <div class="file-item">
        <strong>${file.original_name}</strong>
        <span>${file.content_type} · ${Number(file.size_bytes).toLocaleString()} bytes · ${labelFor(file.extraction_status)}</span>
        <div class="item-actions">
          <button class="secondary extract-btn" data-upload-id="${file.id}" ${file.extraction_status === "analyzing" ? "disabled" : ""}>${uploadActionLabel(file.extraction_status)}</button>
          <button class="ghost delete-upload-btn" data-delete-upload-id="${file.id}">삭제</button>
        </div>
      </div>
  `).join("");
  document.querySelectorAll("[data-upload-id]").forEach((button) => {
    button.addEventListener("click", () => extractUpload(button.dataset.uploadId));
  });
  document.querySelectorAll("[data-delete-upload-id]").forEach((button) => {
    button.addEventListener("click", () => deleteUpload(button.dataset.deleteUploadId));
  });
  updateNextActionGuide(currentStatus);
}

function uploadActionLabel(status) {
  if (status === "analyzing") return "분석 중";
  if (status === "failed") return "다시 분석";
  if (status === "needs_review" || status === "accepted") return "재분석";
  return "분석 실행";
}

function renderExtractions() {
  updateMetrics();
  if (!extractions.length) {
    $("#extractionList").innerHTML = '<div class="file-empty">아직 추출 결과가 없습니다.</div>';
    $("#extractionPill").textContent = "대기";
    return;
  }
  $("#extractionPill").textContent = labelFor(extractions[0].status);
  $("#extractionList").innerHTML = extractions.map((extraction) => {
    const rows = (extraction.rows || []).map((row) => `
      <tr><td>${row.account_name}</td><td>${Number(row.amount).toLocaleString()}</td></tr>
    `).join("");
    const issues = (extraction.issues || []).map((issue) => `<li>${issue}</li>`).join("");
    return `
      <div class="file-item">
        <strong>${labelFor(extraction.provider)} · ${labelFor(extraction.status)}</strong>
        <span>${(extraction.rows || []).length}개 행 추출</span>
        <table>
          <thead><tr><th>계정명</th><th>금액</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        ${issues ? `<ul class="issues">${issues}</ul>` : ""}
        <div class="item-actions">
          <button class="primary accept-extraction-btn" data-extraction-id="${extraction.id}" ${extraction.status === "accepted" ? "disabled" : ""}>계정 반영</button>
        </div>
      </div>
    `;
  }).join("");
  document.querySelectorAll("[data-extraction-id]").forEach((button) => {
    button.addEventListener("click", () => acceptExtraction(button.dataset.extractionId));
  });
  updateNextActionGuide(currentStatus);
}

function renderProjects() {
  if (!projects.length) {
    $("#projectList").innerHTML = '<div class="project-empty">저장된 프로젝트가 없습니다.</div>';
    return;
  }
  $("#projectList").innerHTML = projects.map((project) => `
    <button class="project-item ${project.id === activeProjectId ? "active" : ""}" data-project-id="${project.id}">
      <strong>${project.company_name}</strong>
      <span>${project.period} · ${project.target_standard} · ${labelFor(project.status)}</span>
    </button>
  `).join("");
  document.querySelectorAll("[data-project-id]").forEach((button) => {
    button.addEventListener("click", () => loadProject(button.dataset.projectId));
  });
}

async function refreshProjects() {
  projects = await api("/api/projects");
  renderProjects();
}

function resetWorkspace() {
  statements = [];
  uploads = [];
  extractions = [];
  hasDraft = false;
  lastValidationStatus = null;
  currentStatus = null;
  renderMapping();
  renderUploads();
  renderExtractions();
  updateMetrics();
  renderDraft(null);
  $("#validation").textContent = "";
  $("#approveBtn").disabled = true;
  $("#requestChangesBtn").disabled = true;
  setExportEnabled(false);
  setReviewState("대기");
  updateProgress(null);
}

function syncProjectForm(project) {
  $("#projectForm").elements.company_name.value = project.company_name;
  $("#projectForm").elements.period.value = project.period;
  $("#projectForm").elements.source_standard.value = project.source_standard;
  $("#projectForm").elements.target_standard.value = project.target_standard;
}

async function loadProject(projectId) {
  const data = await api(`/api/projects/${projectId}`);
  activeProjectId = data.project.id;
  lastValidationStatus = null;
  syncProjectForm(data.project);
  setStatus(data.project.status);
  statements = data.statements || [];
  uploads = data.uploads || [];
  extractions = data.extractions || [];
  renderMapping();
  renderValidation(null);
  renderUploads();
  renderExtractions();
  hasDraft = Boolean(data.conversion);
  renderDraft(data.conversion);
  $("#validateBtn").disabled = statements.length === 0 || isReadOnlyUser();
  $("#convertBtn").disabled = statements.length === 0 || (!hasDraft && data.project.status === "mapped") || isReadOnlyUser();
  $("#approveBtn").disabled = !hasDraft || isReadOnlyUser();
  $("#requestChangesBtn").disabled = !hasDraft || isReadOnlyUser();
  setExportEnabled(hasDraft);
  setWorkflowEnabled(true);
  updateNextActionGuide(currentStatus);
  if (data.review) {
    setReviewState(data.review.decision === "approved" ? "approved" : "changes_requested");
    $("#reviewerName").value = data.review.reviewer_name;
    $("#reviewMemo").value = data.review.memo;
  } else {
    setReviewState(hasDraft ? "검토 가능" : "대기");
  }
  await refreshAudit();
  renderProjects();
}

async function refreshAudit() {
  if (!activeProjectId) return;
  const logs = await api(`/api/projects/${activeProjectId}/audit`);
  $("#auditLog").innerHTML = logs.length ? logs.map((log) => {
    const detailRows = auditDetailRows(log);
    return `
      <div class="log-item">
        <strong>${labelFor(log.event_type)}</strong>
        <span>${new Date(log.created_at).toLocaleString()} by ${escapeHtml(log.actor)}</span>
        ${detailRows ? `<div class="log-detail">${detailRows}</div>` : ""}
      </div>
    `;
  }).join("") : '<div class="log-empty">아직 기록된 이벤트가 없습니다.</div>';
}

$("#sampleBtn").addEventListener("click", () => {
  $("#csvInput").value = csvSample();
});

$("#saveAccessCodeBtn").addEventListener("click", async () => {
  const code = $("#accessCodeInput").value.trim();
  if (!code) {
    renderAccessPanel("접근 코드를 입력하세요.");
    return;
  }
  sessionStorage.setItem(accessStorageKey, code);
  renderAccessPanel("접근 코드가 저장되었습니다. 데이터를 다시 불러옵니다.");
  try {
    await refreshProtectedData();
    renderAccessPanel("접근 코드가 확인되었습니다.");
  } catch (error) {
    renderAccessPanel(error.message || "접근 코드 확인에 실패했습니다.");
  }
});

$("#clearAccessCodeBtn").addEventListener("click", () => {
  sessionStorage.removeItem(accessStorageKey);
  renderAccessPanel("접근 코드가 초기화되었습니다.");
});

$("#loginBtn").addEventListener("click", () => submitAuth());
$("#loginPassword").addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitAuth();
});
$("#logoutBtn").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST", body: "{}" });
  currentUser = null;
  projects = [];
  resetWorkspace();
  renderProjects();
  renderAuthPanel("로그아웃되었습니다.");
});

$("#projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  const project = await api("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  activeProjectId = project.id;
  lastValidationStatus = null;
  setStatus(project.status);
  setWorkflowEnabled(true);
  $("#validateBtn").disabled = true;
  $("#convertBtn").disabled = true;
  $("#approveBtn").disabled = true;
  $("#requestChangesBtn").disabled = true;
  setExportEnabled(false);
  hasDraft = false;
  setReviewState("대기");
  statements = [];
  uploads = [];
  extractions = [];
  renderMapping();
  renderUploads();
  renderExtractions();
  renderDraft(null);
  $("#validation").textContent = "";
  await refreshProjects();
  await refreshAudit();
});

$("#uploadBtn").addEventListener("click", async () => {
  const file = $("#fileInput").files[0];
  if (!file) {
    $("#uploadList").innerHTML = '<div class="file-empty">먼저 PDF, Excel, CSV 또는 이미지 파일을 선택하세요.</div>';
    return;
  }
  $("#uploadBtn").disabled = true;
  $("#uploadBtn").textContent = "업로드 중";
  try {
    const upload = await uploadApi(`/api/projects/${activeProjectId}/uploads`, file);
    uploads = [{ ...upload, extraction_status: "analyzing" }, ...uploads];
    renderUploads();
    setStatus("source_uploaded");
    await refreshProjects();
    await refreshAudit();
    await extractUpload(upload.id);
  } finally {
    $("#uploadBtn").disabled = !activeProjectId || isReadOnlyUser();
    $("#uploadBtn").textContent = "업로드 및 분석";
  }
});

async function extractUpload(uploadId) {
  uploads = uploads.map((upload) => (
    upload.id === uploadId ? { ...upload, extraction_status: "analyzing" } : upload
  ));
  renderUploads();
  const extraction = await api(`/api/projects/${activeProjectId}/uploads/${uploadId}/extract`, {
    method: "POST",
    body: "{}"
  });
  extractions = [extraction, ...extractions];
  uploads = uploads.map((upload) => (
    upload.id === uploadId ? { ...upload, extraction_status: extraction.status } : upload
  ));
  renderUploads();
  renderExtractions();
  setStatus("extracted");
  await refreshProjects();
  await refreshAudit();
}

async function deleteUpload(uploadId) {
  if (!activeProjectId) return;
  const target = uploads.find((upload) => upload.id === uploadId);
  const message = target ? `${target.original_name} 파일을 삭제합니다.` : "업로드 파일을 삭제합니다.";
  if (!window.confirm(message)) return;
  await api(`/api/projects/${activeProjectId}/uploads/${uploadId}`, {
    method: "DELETE"
  });
  uploads = uploads.filter((upload) => upload.id !== uploadId);
  extractions = extractions.filter((extraction) => extraction.upload_id !== uploadId);
  renderUploads();
  renderExtractions();
  setStatus(uploads.length ? "source_uploaded" : "created");
  await refreshProjects();
  await refreshAudit();
}

async function acceptExtraction(extractionId) {
  const result = await api(`/api/projects/${activeProjectId}/extractions/${extractionId}/accept`, {
    method: "POST",
    body: "{}"
  });
  statements = [...statements, ...result.statements];
  lastValidationStatus = null;
  extractions = extractions.map((extraction) => (
    extraction.id === extractionId ? { ...extraction, status: "accepted" } : extraction
  ));
  renderMapping();
  renderExtractions();
  $("#validateBtn").disabled = isReadOnlyUser();
  $("#convertBtn").disabled = true;
  setStatus("mapped");
  await refreshProjects();
  await refreshAudit();
}

$("#mapBtn").addEventListener("click", async () => {
  const result = await api(`/api/projects/${activeProjectId}/statements`, {
    method: "POST",
    body: JSON.stringify({ csv_text: $("#csvInput").value, source: "manual_csv" })
  });
  statements = result.statements;
  lastValidationStatus = null;
  renderMapping();
  $("#validateBtn").disabled = isReadOnlyUser();
  $("#convertBtn").disabled = true;
  setStatus("mapped");
  await refreshProjects();
  await refreshAudit();
});

$("#validateBtn").addEventListener("click", async () => {
  const result = await api(`/api/projects/${activeProjectId}/validate`, { method: "POST", body: "{}" });
  lastValidationStatus = result.status;
  renderValidation(result);
  $("#convertBtn").disabled = result.status === "failed" || isReadOnlyUser();
  updateNextActionGuide(currentStatus);
  await refreshAudit();
});

$("#convertBtn").addEventListener("click", async () => {
  const result = await api(`/api/projects/${activeProjectId}/convert`, {
    method: "POST",
    body: JSON.stringify({ responses: getChecklistResponses() })
  });
  renderDraft(result);
  setStatus("draft_generated");
  hasDraft = true;
  $("#approveBtn").disabled = isReadOnlyUser();
  $("#requestChangesBtn").disabled = isReadOnlyUser();
  setExportEnabled(true);
  setReviewState("검토 가능");
  await refreshProjects();
  await refreshAudit();
});

async function submitReview(decision) {
  if (!hasDraft) return;
  const review = await api(`/api/projects/${activeProjectId}/review`, {
    method: "POST",
    body: JSON.stringify({
      decision,
      reviewer_name: $("#reviewerName").value,
      memo: $("#reviewMemo").value
    })
  });
  const label = review.decision === "approved" ? "approved" : "changes_requested";
  setStatus(label);
  setReviewState(label);
  await refreshProjects();
  await refreshAudit();
}

$("#approveBtn").addEventListener("click", () => submitReview("approved"));
$("#requestChangesBtn").addEventListener("click", () => submitReview("changes_requested"));
$("#refreshProjectsBtn").addEventListener("click", refreshProjects);
$("#exportCsvBtn").addEventListener("click", () => {
  if (!activeProjectId || !hasDraft) return;
  downloadApi(`/api/projects/${activeProjectId}/exports/adjustments.csv`, "gtf_adjustments.csv");
});
$("#exportReportBtn").addEventListener("click", () => {
  if (!activeProjectId || !hasDraft) return;
  downloadApi(`/api/projects/${activeProjectId}/exports/basis-report.txt`, "gtf_basis_report.txt");
});

$("#csvInput").value = "";
updateProgress(null);
updateMetrics();

async function initApp() {
  await refreshAccessConfig();
  await refreshSession();
  if (!currentUser) {
    return;
  }
  if (accessRequired && !savedAccessCode()) {
    renderAccessPanel("운영자가 발급한 접근 코드를 입력하면 프로젝트 데이터를 불러옵니다.");
    return;
  }
  try {
    await refreshProtectedData();
  } catch (error) {
    renderAccessPanel(error.message || "초기 데이터를 불러오지 못했습니다.");
  }
}

initApp();
"""
