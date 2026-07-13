import { useEffect, useMemo, useState } from "react";
import AlertTriangle from "lucide-react/dist/esm/icons/alert-triangle.js";
import Check from "lucide-react/dist/esm/icons/check.js";
import ClipboardList from "lucide-react/dist/esm/icons/clipboard-list.js";
import Cloud from "lucide-react/dist/esm/icons/cloud.js";
import Database from "lucide-react/dist/esm/icons/database.js";
import Download from "lucide-react/dist/esm/icons/download.js";
import FileCheck from "lucide-react/dist/esm/icons/file-check.js";
import FileSpreadsheet from "lucide-react/dist/esm/icons/file-spreadsheet.js";
import FileText from "lucide-react/dist/esm/icons/file-text.js";
import History from "lucide-react/dist/esm/icons/history.js";
import Info from "lucide-react/dist/esm/icons/info.js";
import Loader2 from "lucide-react/dist/esm/icons/loader-circle.js";
import PanelRightClose from "lucide-react/dist/esm/icons/panel-right-close.js";
import PanelRightOpen from "lucide-react/dist/esm/icons/panel-right-open.js";
import RefreshCw from "lucide-react/dist/esm/icons/refresh-cw.js";
import Upload from "lucide-react/dist/esm/icons/upload.js";
import XIcon from "lucide-react/dist/esm/icons/x.js";

import { api, download } from "./api";
import { classNames, fmtKRW } from "./format";
import { LoginScreen } from "./screens/LoginScreen";
import { ProjectDashboard } from "./screens/ProjectDashboard";
import type { AccountOption, AiDecision, AuditLog, Conversion, ConversionEntry, FocusTarget, ImportTab, Project, ProjectBundle, ReviewSummary, ReviewTab, Screen, SourceRow, Statement, SummaryAction, UploadRow, UserInfo } from "./types";
import { HeaderCell, Pill, SectionLabel, StatusBadge } from "./ui";

type DartReportOption = {
  corp_code: string;
  corp_name: string;
  bsns_year: string;
  reprt_code: string;
  reprt_name: string;
  report_name: string;
  receipt_no: string;
  receipt_date: string;
};

function ProjectLayout({
  bundle,
  screen,
  reviewTab,
  setScreen,
  setReviewTab,
  onBack,
  onRefresh,
  children,
}: {
  bundle: ProjectBundle;
  screen: Screen;
  reviewTab: ReviewTab;
  setScreen: (screen: Screen) => void;
  setReviewTab: (tab: ReviewTab) => void;
  onBack: () => void;
  onRefresh: () => void;
  children: React.ReactNode;
}) {
  const [showPanel, setShowPanel] = useState(true);
  const judgmentCount = bundle.statements.filter((row) => row.mapping_type === "judgment").length;
  const latestAudit = bundle.project.updated_at?.slice(0, 16).replace("T", " ");
  const nav = [
    { label: "DART 파일 가져오기", icon: Upload, action: () => setScreen("import"), active: screen === "import" },
    { label: "K-IFRS 체크리스트", icon: ClipboardList, action: () => { setScreen("review"); setReviewTab("checklist"); }, active: screen === "review" && reviewTab === "checklist" },
    { label: "변환 초안", icon: Database, action: () => { setScreen("review"); setReviewTab("adjustments"); }, active: screen === "review" && reviewTab === "adjustments" },
    { label: "검토 승인", icon: FileCheck, action: () => { setScreen("review"); setReviewTab("approval"); }, active: screen === "review" && reviewTab === "approval" },
    { label: "감사 로그", icon: History, action: () => { setScreen("review"); setReviewTab("audit"); }, active: screen === "review" && reviewTab === "audit" },
    { label: "내보내기", icon: Download, action: () => { setScreen("review"); setReviewTab("export"); }, active: screen === "review" && reviewTab === "export" },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-[#E8EBF0]">
      <aside className="w-56 flex-shrink-0 bg-[#0D1724] flex flex-col border-r border-[#1C2A3B]">
        <div className="h-12 flex items-center px-4 border-b border-[#1C2A3B]">
          <div className="w-6 h-6 bg-[#1740BE] flex items-center justify-center mr-2.5">
            <FileCheck className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="text-sm font-bold text-white">GTF IFRS Bridge</span>
        </div>
        <div className="px-3 py-3 border-b border-[#1C2A3B]">
          <button onClick={onBack} className="text-[10px] font-bold uppercase tracking-widest text-[#8A96A8] mb-2">← 모든 프로젝트</button>
          <div className="bg-[#162032] border border-[#1C2A3B] px-3 py-2.5">
            <div className="text-xs font-bold text-[#C8D0DC]">{bundle.project.company_name}</div>
            <div className="text-[10px] text-[#8A96A8] mt-1 font-mono">{bundle.project.period} · K-GAAP to K-IFRS</div>
            <div className="mt-2"><StatusBadge status={bundle.project.status} /></div>
          </div>
        </div>
        <nav className="flex-1 py-2 overflow-y-auto">
          <div className="px-3 py-1.5"><SectionLabel>작업 화면</SectionLabel></div>
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.label} onClick={item.action} className={classNames("w-full flex items-center gap-2.5 pl-3 pr-3 py-2 text-xs font-semibold border-l-2", item.active ? "border-[#4B7BF5] text-white bg-[#162032]" : "border-transparent text-[#8A96A8] hover:bg-[#162032]/50")}>
                <Icon className="w-3.5 h-3.5" />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-12 bg-white border-b border-[#D0D5E0] flex items-center px-5 gap-3">
          <div className="flex-1 min-w-0 text-xs">
            <span className="font-bold text-[#0A1628]">{bundle.project.company_name}</span>
            <span className="mx-2 text-[#C8D0DC]">/</span>
            <span className="font-mono text-[#677089]">{bundle.project.period}</span>
          </div>
          <button onClick={onRefresh} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-[#677089] border border-[#D0D5E0]">
            <RefreshCw className="w-3.5 h-3.5" />
            새로고침
          </button>
          <button onClick={() => setShowPanel((value) => !value)} className="p-1.5 border border-[#D0D5E0]">
            {showPanel ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
          </button>
        </header>
        <div className="flex-1 flex overflow-hidden">
          <main className="flex-1 overflow-auto">{children}</main>
          {showPanel && (
            <aside className="w-64 flex-shrink-0 border-l border-[#D0D5E0] bg-white overflow-y-auto">
              <div className="px-4 py-2.5 border-b border-[#D0D5E0] bg-[#F5F7FA]"><SectionLabel>검토 패널</SectionLabel></div>
              <div className="divide-y divide-[#EEF0F5]">
                <div className="px-4 py-3.5">
                  <div className="flex justify-between mb-2"><SectionLabel>요약</SectionLabel><span className="font-mono text-xs font-bold text-amber-700">{judgmentCount}건</span></div>
                  <PanelMetric label="업로드" value={bundle.uploads.length} />
                  <PanelMetric label="추출" value={bundle.extractions.length} />
                  <PanelMetric label="계정 행" value={bundle.statements.length} />
                  <PanelMetric label="판단 필요" value={judgmentCount} />
                </div>
                <div className="px-4 py-3.5">
                  <SectionLabel>최근 수정</SectionLabel>
                  <div className="text-xs text-[#677089] mt-2 font-mono">{latestAudit || "-"}</div>
                </div>
              </div>
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}

function PanelMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between text-xs py-1.5">
      <span className="text-[#677089]">{label}</span>
      <span className="font-mono font-bold text-[#0A1628]">{value}</span>
    </div>
  );
}

function ImportScreen({
  bundle,
  dartReady,
  onUpload,
  onExtract,
  onAccept,
  onDartReports,
  onDartImport,
  onManualAdd,
  onGoNext,
  focusTarget,
  accountOptions,
  onReclassify,
}: {
  bundle: ProjectBundle;
  dartReady: boolean;
  onUpload: (file: File) => Promise<void>;
  onExtract: (uploadId: string) => Promise<void>;
  onAccept: (extractionId: string, aiDecisions: Record<string, AiDecision>) => Promise<void>;
  onDartReports: (payload: Record<string, string>) => Promise<{ reports: DartReportOption[]; issues: string[]; metadata: Record<string, string> }>;
  onDartImport: (payload: Record<string, string>) => Promise<void>;
  onManualAdd: (rows: SourceRow[]) => Promise<void>;
  onGoNext: () => void;
  focusTarget?: FocusTarget | null;
  accountOptions: AccountOption[];
  onReclassify: (statementId: string, accountKey: string) => Promise<void>;
}) {
  const [tab, setTab] = useState<ImportTab>("file");
  const [busy, setBusy] = useState("");
  const [corpCode, setCorpCode] = useState("");
  const [companyName, setCompanyName] = useState(bundle.project.company_name);
  const [stockCode, setStockCode] = useState("");
  const [bsnsYear, setBsnsYear] = useState(bundle.project.period);
  const [reportCode, setReportCode] = useState("11011");
  const [fsDiv, setFsDiv] = useState("CFS");
  const [reports, setReports] = useState<DartReportOption[]>([]);
  const [selectedReportKey, setSelectedReportKey] = useState("");
  const [reportIssues, setReportIssues] = useState<string[]>([]);
  const [manualText, setManualText] = useState("현금및현금성자산,120000000\n리스부채,30000000\n개발비,45000000");
  const latestExtraction = bundle.extractions[0];
  const previewRows = latestExtraction?.rows || [];
  const [aiDecisions, setAiDecisions] = useState<Record<string, AiDecision>>({});
  const suggestedAccounts = previewRows.filter((row) => row.ai_suggestion).map((row) => row.account_name);
  const undecidedCount = suggestedAccounts.filter((name) => !aiDecisions[name]).length;
  const unclassifiedCount = bundle.statements.filter((row) => row.standard_code === "X9999").length;

  // 검토 요약의 행동 버튼이 보낸 목적지: 수동 입력 탭 열기 또는 계정 매핑 행으로 스크롤.
  useEffect(() => {
    if (!focusTarget) return;
    if (focusTarget.kind === "add_rows") setTab("manual");
    if (focusTarget.kind === "classify" || focusTarget.kind === "review_rows") {
      const elementId =
        focusTarget.kind === "classify" && focusTarget.statementId
          ? `mapping-row-${focusTarget.statementId}`
          : "mapping-table";
      setTimeout(() => document.getElementById(elementId)?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
    }
  }, [focusTarget?.seq]);

  function decideAi(accountName: string, decision: AiDecision) {
    setAiDecisions((current) => {
      const next = { ...current };
      if (next[accountName] === decision) delete next[accountName];
      else next[accountName] = decision;
      return next;
    });
  }

  async function run(label: string, work: () => Promise<void>) {
    setBusy(label);
    try {
      await work();
    } finally {
      setBusy("");
    }
  }

  function parseManualRows(): SourceRow[] {
    return manualText
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [account_name, amount] = line.split(",").map((item) => item.trim());
        return { account_name, amount: Number(amount || 0) };
      })
      .filter((row) => row.account_name);
  }

  async function lookupReports() {
    const result = await onDartReports({ corp_code: corpCode, company_name: companyName, stock_code: stockCode, from_year: "2024", to_year: bsnsYear });
    setReports(result.reports || []);
    setReportIssues(result.issues || []);
    const firstReport = result.reports?.[0];
    if (firstReport) selectReport(firstReport);
  }

  function reportKey(report: DartReportOption) {
    return `${report.bsns_year}:${report.reprt_code}:${report.receipt_no}`;
  }

  function selectReport(report: DartReportOption) {
    setSelectedReportKey(reportKey(report));
    setCorpCode(report.corp_code || corpCode);
    setCompanyName(report.corp_name || companyName);
    setBsnsYear(report.bsns_year);
    setReportCode(report.reprt_code);
  }

  function importSelectedReport() {
    const selectedReport = reports.find((report) => reportKey(report) === selectedReportKey);
    const payload = selectedReport
      ? { corp_code: selectedReport.corp_code, company_name: selectedReport.corp_name, stock_code: stockCode, bsns_year: selectedReport.bsns_year, reprt_code: selectedReport.reprt_code, fs_div: fsDiv }
      : { corp_code: corpCode, company_name: companyName, stock_code: stockCode, bsns_year: bsnsYear, reprt_code: reportCode, fs_div: fsDiv };
    return onDartImport(payload);
  }

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-sm font-bold text-[#0A1628]">DART 파일 가져오기</h2>
        <p className="text-xs text-[#677089] mt-0.5 font-medium">DART API, 파일 업로드, 수동 입력을 같은 추출 흐름으로 처리합니다</p>
      </div>

      <div className="grid grid-cols-4 gap-px bg-[#D0D5E0] border border-[#D0D5E0]">
        <Stat label="업로드" value={bundle.uploads.length} />
        <Stat label="추출 결과" value={bundle.extractions.length} />
        <Stat label="매핑 계정" value={bundle.statements.length} />
        <Stat label="DART API" value={dartReady ? "ON" : "OFF"} color={dartReady ? "text-emerald-700" : "text-amber-700"} />
      </div>

      <div className="bg-white border border-[#D0D5E0]">
        <div className="flex border-b border-[#D0D5E0]">
          {[
            ["file", "파일 업로드"],
            ["dart-api", "DART API 가져오기"],
            ["manual", "수동 입력"],
          ].map(([id, label]) => (
            <button key={id} onClick={() => setTab(id as ImportTab)} className={classNames("px-5 py-3 text-sm font-semibold", tab === id ? "text-[#1740BE] border-b-2 border-[#1740BE]" : "text-[#677089]")}>{label}</button>
          ))}
        </div>

        <div className="p-5">
          {tab === "file" && (
            <div className="space-y-4">
              <label className="block border border-dashed border-[#C8D0DC] p-10 text-center cursor-pointer bg-[#F5F7FA] hover:border-[#1740BE]/50">
                <Upload className="w-7 h-7 text-[#677089] mx-auto mb-3" />
                <p className="text-sm font-semibold text-[#0A1628]">PDF Excel CSV 이미지 업로드</p>
                <input type="file" className="hidden" onChange={(event) => event.target.files?.[0] && run("upload", () => onUpload(event.target.files![0]))} />
              </label>
              <SourceTable uploads={bundle.uploads} onExtract={(id) => run("extract", () => onExtract(id))} busy={busy} />
            </div>
          )}

          {tab === "dart-api" && (
            <div className="space-y-4">
              {!dartReady && (
                <div className="flex gap-2.5 p-3 bg-amber-50 border-l-4 border-amber-500">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  <p className="text-xs text-amber-800 font-medium">서버 환경변수 DART_API_KEY가 설정되지 않았습니다</p>
                </div>
              )}
              <div className="grid grid-cols-3 gap-4">
                <TextInput label="DART corp_code" value={corpCode} onChange={setCorpCode} placeholder="선택 입력" />
                <TextInput label="회사명" value={companyName} onChange={setCompanyName} />
                <TextInput label="종목코드" value={stockCode} onChange={setStockCode} placeholder="005930" />
                <TextInput label="사업연도" value={bsnsYear} onChange={setBsnsYear} />
                <SelectInput label="보고서" value={reportCode} onChange={setReportCode} options={[["11011", "사업보고서"], ["11012", "반기보고서"], ["11013", "1분기"], ["11014", "3분기"]]} />
                <label className="block">
                  <span className="block text-xs font-bold uppercase tracking-wide text-[#677089] mb-1.5">연결 별도</span>
                  <select value={fsDiv} onChange={(event) => setFsDiv(event.target.value)} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA]">
                    <option value="CFS">연결</option>
                    <option value="OFS">별도</option>
                  </select>
                </label>
              </div>
              <div className="flex items-center gap-2">
                <button disabled={!dartReady || !!busy} onClick={() => run("reports", lookupReports)} className="flex items-center gap-2 px-4 py-2 bg-white border border-[#1740BE] disabled:border-[#C8D0DC] disabled:text-[#8A96A8] text-[#1740BE] text-xs font-bold">
                  {busy === "reports" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ClipboardList className="w-3.5 h-3.5" />}
                  보고서 조회
                </button>
                <button disabled={!dartReady || !!busy} onClick={() => run("dart", importSelectedReport)} className="flex items-center gap-2 px-4 py-2 bg-[#1740BE] disabled:bg-[#C8D0DC] text-white text-xs font-bold">
                  {busy === "dart" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Cloud className="w-3.5 h-3.5" />}
                  DART에서 가져오기
                </button>
              </div>
              {reports.length > 0 && (
                <div className="border border-[#D0D5E0] bg-[#F5F7FA]">
                  <div className="px-4 py-2.5 border-b border-[#D0D5E0]">
                    <SectionLabel>조회 가능한 보고서</SectionLabel>
                  </div>
                  <div className="divide-y divide-[#D0D5E0]">
                    {reports.map((report) => {
                      const key = reportKey(report);
                      return (
                        <label key={key} className={classNames("flex items-center gap-3 px-4 py-3 cursor-pointer bg-white", selectedReportKey === key && "bg-blue-50")}>
                          <input type="radio" name="dart-report" checked={selectedReportKey === key} onChange={() => selectReport(report)} />
                          <span className="flex-1 text-sm font-semibold text-[#0A1628]">{report.bsns_year} {report.reprt_name}</span>
                          <span className="text-xs font-mono text-[#677089]">{report.receipt_date || "-"}</span>
                          <span className="text-xs text-[#677089] max-w-[320px] truncate">{report.report_name}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
              {reportIssues.length > 0 && (
                <div className="border-l-4 border-amber-500 bg-amber-50 px-3 py-2 text-xs text-amber-800 font-medium">
                  {reportIssues.join(" / ")}
                </div>
              )}
            </div>
          )}

          {tab === "manual" && (
            <div className="space-y-3">
              <textarea value={manualText} onChange={(event) => setManualText(event.target.value)} rows={6} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA] font-mono" />
              <p className="text-[11px] text-[#677089]">입력하면 추출 결과로 만들어지고, 미분류 계정에는 AI 1차 분류 제안이 붙습니다. 아래 미리보기에서 제안을 승인/거절한 뒤 반영하세요.</p>
              <button disabled={!!busy} onClick={() => run("manual", () => onManualAdd(parseManualRows()))} className="px-4 py-2 bg-[#1740BE] text-white text-xs font-bold">수동 입력 분석</button>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white border border-[#D0D5E0]">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#D0D5E0] bg-[#F5F7FA]">
          <SectionLabel>추출 결과 미리보기</SectionLabel>
          <div className="flex items-center gap-2">
            {latestExtraction && undecidedCount > 0 && latestExtraction.status !== "accepted" && (
              <span className="text-[11px] font-bold text-violet-700">AI 제안 {undecidedCount}건 승인/거절 필요 (1차 승인)</span>
            )}
            {latestExtraction && (
              <button
                disabled={latestExtraction.status === "accepted" || !!busy || undecidedCount > 0}
                onClick={() => run("accept", () => onAccept(latestExtraction.id, aiDecisions))}
                className="px-3 py-1.5 text-xs font-bold text-white bg-[#1740BE] disabled:bg-[#C8D0DC]"
              >
                추출 결과 반영
              </button>
            )}
          </div>
        </div>
        {latestExtraction && latestExtraction.issues?.length > 0 && (
          <div className="border-b border-[#D0D5E0] border-l-4 border-l-amber-500 bg-amber-50 px-4 py-2 text-xs text-amber-800 font-medium space-y-0.5">
            {latestExtraction.issues.map((issue, index) => (
              <div key={index}>{issue}</div>
            ))}
          </div>
        )}
        <RowsTable rows={previewRows} decisions={aiDecisions} onDecide={latestExtraction?.status === "accepted" ? undefined : decideAi} />
      </div>

      <MappingTable
        statements={bundle.statements}
        accountOptions={accountOptions}
        onReclassify={onReclassify}
        highlightId={focusTarget?.kind === "classify" ? focusTarget.statementId : undefined}
      />

      {!!bundle.statements.length && (
        <div className="bg-white border border-[#D0D5E0] px-4 py-3 flex items-center justify-between">
          <span className="text-xs text-[#677089]">
            {unclassifiedCount > 0
              ? `미분류 ${unclassifiedCount}건 — 추출 결과 미리보기에서 AI 제안을 승인하거나 재분류하면 승인 단계 진행이 원활합니다`
              : "모든 계정이 표준계정에 매핑되었습니다"}
          </span>
          <button onClick={onGoNext} className="px-4 py-2 text-xs font-bold text-white bg-[#1740BE]">
            다음 단계로 →
          </button>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color = "text-[#0A1628]" }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="bg-white px-5 py-3.5">
      <SectionLabel>{label}</SectionLabel>
      <div className={`text-xl font-bold font-mono mt-1 ${color}`}>{value}</div>
    </div>
  );
}

function TextInput({ label, value, onChange, placeholder = "" }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="block">
      <span className="block text-xs font-bold uppercase tracking-wide text-[#677089] mb-1.5">{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA]" />
    </label>
  );
}

function SelectInput({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: [string, string][] }) {
  return (
    <label className="block">
      <span className="block text-xs font-bold uppercase tracking-wide text-[#677089] mb-1.5">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA]">
        {options.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select>
    </label>
  );
}

function SourceTable({ uploads, onExtract, busy }: { uploads: UploadRow[]; onExtract: (id: string) => void; busy: string }) {
  return (
    <div className="border border-[#D0D5E0]">
      <table className="w-full text-xs">
        <thead><tr className="bg-[#F5F7FA]"><HeaderCell>파일명</HeaderCell><HeaderCell>형식</HeaderCell><HeaderCell right>크기</HeaderCell><HeaderCell>상태</HeaderCell><HeaderCell></HeaderCell></tr></thead>
        <tbody>
          {uploads.map((upload) => (
            <tr key={upload.id} className="border-t border-[#EEF0F5]">
              <td className="px-4 py-2.5 font-semibold">{upload.original_name}</td>
              <td className="px-4 py-2.5 text-[#677089]">{upload.content_type}</td>
              <td className="px-4 py-2.5 text-right font-mono">{Math.round(upload.size_bytes / 1024)} KB</td>
              <td className="px-4 py-2.5"><StatusBadge status={upload.extraction_status} /></td>
              <td className="px-4 py-2.5"><button disabled={!!busy} onClick={() => onExtract(upload.id)} className="text-xs font-bold text-[#1740BE]">분석 실행</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!uploads.length && <div className="text-center py-8 text-xs text-[#677089]">업로드된 파일이 없습니다</div>}
    </div>
  );
}

// 정적 Tailwind CSS에는 새 유틸리티 클래스가 생성되지 않으므로(빌드에 Tailwind 엔진 미연결),
// 승인/거절 버튼과 근거 툴팁은 인라인 스타일 + React 상태로 구현한다.
function DecisionButton({ kind, active, onClick }: { kind: AiDecision; active: boolean; onClick: () => void }) {
  const color = kind === "approved" ? "#059669" : "#DC2626"; // emerald-600 / red-600
  return (
    <button
      aria-label={kind === "approved" ? "제안 승인" : "제안 거절"}
      onClick={onClick}
      style={{
        padding: "4px 10px",
        fontSize: 11,
        fontWeight: 700,
        lineHeight: 1,
        borderRadius: 4,
        border: `1px solid ${color}`,
        whiteSpace: "nowrap",
        flexShrink: 0,
        cursor: "pointer",
        transition: "background-color .15s, color .15s",
        backgroundColor: active ? color : "#FFFFFF",
        color: active ? "#FFFFFF" : color,
      }}
    >
      {kind === "approved" ? "승인" : "거절"}
    </button>
  );
}

function RationaleTooltip({ suggestion }: { suggestion: NonNullable<SourceRow["ai_suggestion"]> }) {
  const { rationale, confidence, basis_reference, alternative_label, alternative_rejected_reason } = suggestion;
  const [open, setOpen] = useState(false);
  return (
    <span
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      style={{ position: "relative", display: "inline-flex", alignItems: "center", gap: 2, fontSize: 11, color: "#9AA1B0", cursor: "help", whiteSpace: "nowrap" }}
    >
      <Info style={{ width: 12, height: 12 }} /> 근거
      {open && (
        <span
          role="tooltip"
          style={{
            position: "absolute",
            bottom: "100%",
            left: "50%",
            transform: "translateX(-50%)",
            marginBottom: 8,
            zIndex: 50,
            width: 260,
            whiteSpace: "normal",
            borderRadius: 4,
            border: "1px solid #39415A",
            backgroundColor: "#232A3F",
            padding: "8px 12px",
            textAlign: "left",
            fontSize: 11,
            lineHeight: 1.5,
            color: "#FFFFFF",
            boxShadow: "0 4px 12px rgba(10,22,40,.35)",
            pointerEvents: "none",
          }}
        >
          <span style={{ display: "block", fontWeight: 700, color: "#C4B5FD", marginBottom: 2 }}>AI 분류 근거</span>
          {rationale || "근거 설명이 제공되지 않았습니다."}
          {basis_reference ? (
            <span style={{ display: "block", marginTop: 4, color: "#93C5FD" }}>근거 기준서: {basis_reference}</span>
          ) : null}
          {alternative_label ? (
            <span style={{ display: "block", marginTop: 4, color: "#FCD34D" }}>
              차선 후보: {alternative_label}
              {alternative_rejected_reason ? ` — ${alternative_rejected_reason}` : ""}
            </span>
          ) : null}
          <span style={{ display: "block", marginTop: 4, color: "#9AA1B0" }}>신뢰도: {confidence || "-"}</span>
          <span
            style={{
              position: "absolute",
              top: "100%",
              left: "50%",
              transform: "translateX(-50%)",
              border: "5px solid transparent",
              borderTopColor: "#232A3F",
            }}
          />
        </span>
      )}
    </span>
  );
}

function RowsTable({ rows, decisions = {}, onDecide }: { rows: SourceRow[]; decisions?: Record<string, AiDecision>; onDecide?: (accountName: string, decision: AiDecision) => void }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead><tr className="bg-[#F5F7FA]"><HeaderCell>원 계정명</HeaderCell><HeaderCell right>금액</HeaderCell><HeaderCell>재무제표</HeaderCell><HeaderCell>통화</HeaderCell><HeaderCell>AI 1차 분류 제안</HeaderCell></tr></thead>
        <tbody>
          {rows.map((row, index) => {
            const decision = decisions[row.account_name];
            return (
              <tr key={`${row.account_name}-${index}`} className="border-t border-[#EEF0F5]">
                <td className="px-4 py-2.5 font-semibold">{row.account_name}</td>
                <td className="px-4 py-2.5 text-right font-mono">{fmtKRW(row.amount)}</td>
                <td className="px-4 py-2.5 text-[#677089]">{row.statement_type || "-"}</td>
                <td className="px-4 py-2.5 text-[#677089]">{row.currency || "KRW"}</td>
                <td className="px-4 py-2.5">
                  {row.ai_suggestion ? (
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="inline-flex items-center px-2 py-0.5 text-[11px] font-bold bg-violet-50 text-violet-700 border border-violet-200 rounded">
                        {row.ai_suggestion.label}
                      </span>
                      <RationaleTooltip suggestion={row.ai_suggestion} />
                      {onDecide ? (
                        <div className="flex items-center gap-1">
                          <DecisionButton kind="approved" active={decision === "approved"} onClick={() => onDecide(row.account_name, "approved")} />
                          <DecisionButton kind="rejected" active={decision === "rejected"} onClick={() => onDecide(row.account_name, "rejected")} />
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-0.5 text-[11px] text-emerald-700 font-semibold"><Check className="w-3 h-3" /> 반영됨</span>
                      )}
                    </div>
                  ) : (
                    <span className="text-[#C8D0DC]">-</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!rows.length && <div className="text-center py-10 text-xs text-[#677089]">추출 결과가 없습니다</div>}
    </div>
  );
}

function MappingTable({
  statements,
  accountOptions,
  onReclassify,
  highlightId,
}: {
  statements: Statement[];
  accountOptions: AccountOption[];
  onReclassify: (statementId: string, accountKey: string) => Promise<void>;
  highlightId?: string;
}) {
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState("");

  async function apply(rowId: string) {
    const key = choice[rowId];
    if (!key) return;
    setBusyId(rowId);
    try {
      await onReclassify(rowId, key);
    } finally {
      setBusyId("");
    }
  }

  return (
    <div id="mapping-table" className="bg-white border border-[#D0D5E0]">
      <div className="px-4 py-3 border-b border-[#D0D5E0] bg-[#F5F7FA]"><SectionLabel>계정 매핑</SectionLabel></div>
      <table className="w-full text-xs">
        <thead><tr className="bg-[#F5F7FA]"><HeaderCell>원 계정</HeaderCell><HeaderCell right>금액</HeaderCell><HeaderCell>표준계정</HeaderCell><HeaderCell>코드</HeaderCell><HeaderCell>유형</HeaderCell><HeaderCell>근거</HeaderCell></tr></thead>
        <tbody>
          {statements.map((row) => (
            <tr
              key={row.id}
              id={`mapping-row-${row.id}`}
              style={row.id === highlightId ? { outline: "2px solid #1740BE", outlineOffset: "-2px" } : undefined}
              className={classNames("border-t border-[#EEF0F5]", row.mapping_type === "judgment" && "bg-amber-50/30", row.standard_code === "X9999" && "bg-red-50/40")}
            >
              <td className="px-4 py-2.5 font-semibold">{row.account_name}</td>
              <td className="px-4 py-2.5 text-right font-mono">{fmtKRW(row.amount)}</td>
              <td className="px-4 py-2.5">{row.normalized_account}</td>
              <td className={classNames("px-4 py-2.5 font-mono", row.standard_code === "X9999" ? "text-red-600 font-bold" : "text-[#677089]")}>{row.standard_code}</td>
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-1.5">
                  <Pill color={row.standard_code === "X9999" ? "red" : row.mapping_type === "judgment" ? "amber" : "blue"}>{row.standard_code === "X9999" ? "미분류" : row.mapping_type === "judgment" ? "판단 필요" : "단순 매핑"}</Pill>
                  {row.rule_summary?.includes("AI 1차 분류") && (
                    <span title="AI가 분류를 제안하고 담당자가 확정한 계정입니다" className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-bold bg-violet-50 text-violet-700 border border-violet-200 rounded">AI 분류</span>
                  )}
                  {row.rule_summary?.includes("담당자 재분류") && (
                    <span title="담당자가 직접 재분류한 계정입니다 (감사 로그 기록)" className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 rounded">재분류됨</span>
                  )}
                </div>
              </td>
              <td className="px-4 py-2.5 text-[#677089] max-w-[320px]">
                <div className="truncate">{row.rule_summary}</div>
                {row.standard_code === "X9999" && (
                  <div className="flex items-center gap-1.5 mt-1.5">
                    <select
                      value={choice[row.id] || ""}
                      onChange={(event) => setChoice((current) => ({ ...current, [row.id]: event.target.value }))}
                      className="px-2 py-1 text-[11px] border border-[#D0D5E0] bg-[#F5F7FA]"
                    >
                      <option value="">표준계정 선택</option>
                      {accountOptions.map((option) => (
                        <option key={option.account_key} value={option.account_key}>
                          {option.internal_label} ({option.standard_code})
                        </option>
                      ))}
                    </select>
                    <button
                      disabled={!choice[row.id] || busyId === row.id}
                      onClick={() => apply(row.id)}
                      className="px-2 py-1 text-[11px] font-bold text-white bg-[#1740BE] disabled:bg-[#C8D0DC]"
                    >
                      {busyId === row.id ? "적용 중..." : "재분류"}
                    </button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!statements.length && <div className="text-center py-8 text-xs text-[#677089]">반영된 계정이 없습니다</div>}
    </div>
  );
}

function ReviewScreen({
  bundle,
  tab,
  setTab,
  onConvert,
  onExport,
  focusTarget,
  onSummaryAction,
}: {
  bundle: ProjectBundle;
  tab: ReviewTab;
  setTab: (tab: ReviewTab) => void;
  onConvert: (responses: Record<string, Record<string, unknown>>) => Promise<void>;
  onExport: (name: string) => void;
  focusTarget?: FocusTarget | null;
  onSummaryAction: (action: SummaryAction, statementId?: string) => void;
}) {
  const [responses, setResponses] = useState<Record<string, Record<string, unknown>>>({});
  const [busy, setBusy] = useState(false);
  const judgmentStatements = bundle.statements.filter((statement) => statement.mapping_type === "judgment");
  const entries = bundle.conversion?.entries || [];

  // '체크리스트 입력' 버튼이 보낸 목적지: 해당 계정 카드로 스크롤.
  useEffect(() => {
    if (focusTarget?.kind === "fill_checklist" && tab === "checklist" && focusTarget.statementId) {
      const elementId = `checklist-card-${focusTarget.statementId}`;
      setTimeout(() => document.getElementById(elementId)?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
    }
  }, [focusTarget?.seq, tab]);

  function setResponse(statementId: string, key: string, value: unknown) {
    setResponses((current) => ({ ...current, [statementId]: { ...(current[statementId] || {}), [key]: value } }));
  }

  async function convert() {
    setBusy(true);
    try {
      await onConvert(responses);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-sm font-bold text-[#0A1628]">K-IFRS 변환 리뷰</h2>
        <p className="text-xs text-[#677089] mt-0.5 font-medium">체크리스트 입력 후 아래 변환 생성 버튼을 누르세요</p>
      </div>

      <div className="bg-white border border-[#D0D5E0]">
        <div className="flex border-b border-[#D0D5E0]">
          {[
            ["checklist", "체크리스트"],
            ["adjustments", `조정분개 ${entries.length}`],
            ["notes", "주석 초안"],
            ["approval", "검토 승인"],
            ["audit", "감사 로그"],
            ["export", "내보내기"],
          ].map(([id, label]) => (
            <button key={id} onClick={() => setTab(id as ReviewTab)} className={classNames("px-5 py-3 text-sm font-semibold", tab === id ? "text-[#1740BE] border-b-2 border-[#1740BE]" : "text-[#677089]")}>{label}</button>
          ))}
        </div>
        <div className="p-5">
          {tab === "checklist" && (
            <div className="space-y-4">
              {judgmentStatements.map((statement) => (
                <div
                  key={statement.id}
                  id={`checklist-card-${statement.id}`}
                  className="border border-[#D0D5E0]"
                  style={focusTarget?.kind === "fill_checklist" && focusTarget.statementId === statement.id ? { outline: "2px solid #1740BE", outlineOffset: "-2px" } : undefined}
                >
                  <div className="px-4 py-2.5 bg-amber-50 border-b border-[#D0D5E0] flex justify-between">
                    <span className="text-xs font-bold text-[#0A1628]">{statement.account_name}</span>
                    <span className="text-xs text-amber-800">{statement.rule_summary}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 p-4">
                    {statement.checklist.map((item) => (
                      <label key={item.key} className="block">
                        <span className="block text-xs font-bold text-[#677089] mb-1.5">{item.label}</span>
                        {item.type === "boolean" ? (
                          <select onChange={(event) => setResponse(statement.id, item.key, event.target.value === "true")} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA]">
                            <option value="">선택</option>
                            <option value="true">예</option>
                            <option value="false">아니오</option>
                          </select>
                        ) : (
                          <input type={item.type === "number" ? "number" : "text"} onChange={(event) => setResponse(statement.id, item.key, item.type === "number" ? Number(event.target.value) : event.target.value)} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA]" />
                        )}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
              {!judgmentStatements.length && <div className="text-center py-10 text-xs text-[#677089]">판단 필요 계정이 없습니다</div>}
              <div className="flex items-center justify-end gap-3 pt-2 border-t border-[#EEF0F5]">
                <span className="text-xs text-[#677089]">체크리스트 입력을 마쳤으면 변환 초안을 생성하세요</span>
                <button disabled={busy || !bundle.statements.length} onClick={convert} className="flex items-center gap-1.5 px-4 py-2 bg-[#1740BE] disabled:bg-[#C8D0DC] text-white text-xs font-bold">
                  {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  변환 생성
                </button>
              </div>
            </div>
          )}

          {tab === "adjustments" && <AdjustmentTable entries={entries} />}
          {tab === "notes" && <Notes notes={bundle.conversion?.draft_notes || []} ai={bundle.conversion?.ai_assistance} judgmentItems={bundle.conversion?.judgment_items || []} />}
          {tab === "approval" && <ApprovalPanel projectId={bundle.project.id} onAction={onSummaryAction} />}
          {tab === "audit" && <AuditTable logs={[]} projectId={bundle.project.id} />}
          {tab === "export" && <ExportPanel onExport={onExport} ready={!!bundle.conversion} />}
        </div>
      </div>
    </div>
  );
}

function AdjustmentTable({ entries }: { entries: ConversionEntry[] }) {
  return (
    <div className="overflow-x-auto border border-[#D0D5E0]">
      <table className="w-full text-xs">
        <thead><tr className="bg-[#F5F7FA]"><HeaderCell>원 계정</HeaderCell><HeaderCell>코드</HeaderCell><HeaderCell>K-IFRS 계정</HeaderCell><HeaderCell>표시 라인</HeaderCell><HeaderCell right>금액</HeaderCell><HeaderCell right>조정액</HeaderCell><HeaderCell>근거</HeaderCell></tr></thead>
        <tbody>
          {entries.map((entry, index) => (
            <tr key={`${entry.source_account}-${index}`} className="border-t border-[#EEF0F5]">
              <td className="px-4 py-2.5 font-semibold">{entry.source_account}</td>
              <td className="px-4 py-2.5 font-mono text-[#677089]">{entry.standard_code}</td>
              <td className="px-4 py-2.5">{entry.target_account}</td>
              <td className="px-4 py-2.5 text-[#677089]">{entry.statement_line_item || "-"}</td>
              <td className="px-4 py-2.5 text-right font-mono">{fmtKRW(entry.amount)}</td>
              <td className={classNames("px-4 py-2.5 text-right font-mono font-bold", entry.adjustment ? "text-emerald-700" : "text-[#677089]")}>{fmtKRW(entry.adjustment)}</td>
              <td className="px-4 py-2.5 text-[#677089] max-w-[360px] truncate">{entry.calculation || entry.basis}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!entries.length && <div className="text-center py-10 text-xs text-[#677089]">변환 초안을 먼저 생성하세요</div>}
    </div>
  );
}

function Notes({ notes, ai, judgmentItems }: { notes: Conversion["draft_notes"]; ai?: Conversion["ai_assistance"]; judgmentItems?: Conversion["judgment_items"] }) {
  const itemsWithParagraphs = (judgmentItems || []).filter((item) => item.standards_paragraphs?.length);
  return (
    <div className="space-y-3">
      {notes.map((note) => (
        <div key={note.account} className="border border-[#D0D5E0]">
          <div className="px-4 py-2.5 bg-[#F5F7FA] border-b border-[#D0D5E0] text-xs font-bold">{note.account}</div>
          <p className="p-4 text-sm text-[#677089] leading-relaxed">{note.draft_note}</p>
        </div>
      ))}
      {itemsWithParagraphs.map((item) => (
        <div key={`std-${item.statement_id}`} className="border border-[#D0D5E0]">
          <div className="px-4 py-2.5 bg-[#F5F7FA] border-b border-[#D0D5E0] flex items-center justify-between">
            <span className="text-xs font-bold">{item.account} · 기준서 문단 근거</span>
            <span className="text-[11px] text-[#677089]">K-GAAP / K-IFRS 기준서 문단 검색 DB</span>
          </div>
          <div className="divide-y divide-[#EEF0F5]">
            {(item.standards_paragraphs || []).map((paragraph, index) => (
              <div key={index} className="px-4 py-2.5 flex gap-3 items-start">
                <span className={classNames(
                  "shrink-0 px-2 py-0.5 text-[11px] font-bold border",
                  paragraph.standard_set === "K-IFRS" ? "bg-blue-50 text-blue-700 border-blue-200" : "bg-slate-100 text-slate-700 border-slate-300",
                )}>
                  {paragraph.standard_set}
                </span>
                <div className="text-xs leading-relaxed">
                  <span className="font-bold text-[#0A1628]">{paragraph.reference_code} {paragraph.paragraph_label}</span>
                  <span className="text-[#677089]"> — {paragraph.content}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      {ai && (
        <div className="border border-[#D0D5E0] p-4 bg-blue-50 text-xs text-blue-800">
          AI 판단 보조 {ai.status} · {ai.overall_note || "사람 검토 필요"}
        </div>
      )}
      {!notes.length && !itemsWithParagraphs.length && <div className="text-center py-10 text-xs text-[#677089]">주석 초안이 없습니다</div>}
    </div>
  );
}

const SUMMARY_ACTION_LABELS: Record<SummaryAction, string> = {
  classify: "분류하러 가기 →",
  fill_checklist: "체크리스트 입력 →",
  add_rows: "손익 행 추가 →",
  review_rows: "계정 행 확인 →",
};

function ApprovalPanel({ projectId, onAction }: { projectId: string; onAction: (action: SummaryAction, statementId?: string) => void }) {
  const [summary, setSummary] = useState<ReviewSummary | null>(null);
  const [reviewerName, setReviewerName] = useState("");
  const [memo, setMemo] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");

  async function loadSummary() {
    const data = await api<ReviewSummary>(`/api/projects/${projectId}/review-summary`).catch(() => null);
    setSummary(data);
  }

  useEffect(() => {
    loadSummary();
  }, [projectId]);

  async function submit(decision: "approved" | "changes_requested") {
    setBusy(true);
    setResult("");
    try {
      await api(`/api/projects/${projectId}/review`, {
        method: "POST",
        body: JSON.stringify({ decision, reviewer_name: reviewerName, memo }),
      });
      setResult(decision === "approved" ? "승인이 기록되었습니다." : "수정 요청이 기록되었습니다.");
      await loadSummary();
    } catch (error) {
      setResult(error instanceof Error ? error.message : "요청이 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  if (!summary) return <div className="text-center py-10 text-xs text-[#677089]">검토 요약을 불러오는 중...</div>;

  const severityStyle = (severity: string) =>
    severity === "error" ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-800 border-amber-200";

  return (
    <div className="space-y-4">
      <div className="border border-[#D0D5E0]">
        <div className="px-4 py-2.5 bg-[#FDF2F2] border-b border-[#D0D5E0] flex items-center justify-between">
          <span className="text-xs font-bold text-red-700">확인 필요 · {summary.counts.attention}건</span>
          <span className="text-[11px] text-[#677089]">문제 상황 기반 — 먼저 처리해야 할 항목</span>
        </div>
        <div className="divide-y divide-[#EEF0F5]">
          {summary.attention.map((item, index) => (
            <div key={index} className="px-4 py-2.5 flex items-start gap-2.5">
              <span className={classNames("shrink-0 px-2 py-0.5 text-[11px] font-bold border", severityStyle(item.severity))}>
                {item.severity === "error" ? "오류" : "경고"}
              </span>
              <div className="text-xs flex-1">
                <span className="font-bold text-[#0A1628]">{item.account}</span>
                <span className="text-[#677089]"> — {item.message}</span>
              </div>
              {item.action && (
                <button
                  onClick={() => onAction(item.action!, item.statement_id)}
                  className="shrink-0 px-2 py-0.5 text-[11px] font-semibold text-[#1740BE] bg-[#EFF4FF] rounded"
                >
                  {SUMMARY_ACTION_LABELS[item.action]}
                </button>
              )}
            </div>
          ))}
          {!summary.attention.length && <div className="px-4 py-3 text-xs text-emerald-700 font-semibold">확인 필요 항목이 없습니다.</div>}
        </div>
      </div>

      <div className="border border-[#D0D5E0]">
        <div className="px-4 py-2.5 bg-[#EFF4FF] border-b border-[#D0D5E0] flex items-center justify-between">
          <span className="text-xs font-bold text-[#1740BE]">회계 판단 항목 · {summary.counts.judgment}건</span>
          <span className="text-[11px] text-[#677089]">계정 종류 기반 — 값의 타당성 검토</span>
        </div>
        <div className="divide-y divide-[#EEF0F5]">
          {summary.judgment.map((item) => (
            <div key={item.statement_id} className="px-4 py-2.5 flex items-center gap-2.5 flex-wrap">
              <Pill color="blue">회계 판단</Pill>
              <span className="text-xs font-bold text-[#0A1628]">{item.account}</span>
              <span className="text-xs font-mono text-[#677089]">{fmtKRW(item.amount)}</span>
              <span className={classNames("px-2 py-0.5 text-[11px] font-bold border", item.checklist_answered ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-800 border-amber-200")}>
                {item.checklist_answered ? "체크리스트 입력됨" : "체크리스트 미입력"}
              </span>
              <span className="text-[11px] text-[#677089]">기준서 문단 {item.standards_paragraph_count}건 연결</span>
              {!item.checklist_answered && (
                <button
                  onClick={() => onAction("fill_checklist", item.statement_id)}
                  className="px-2 py-0.5 text-[11px] font-semibold text-[#1740BE] bg-[#EFF4FF] rounded"
                >
                  {SUMMARY_ACTION_LABELS.fill_checklist}
                </button>
              )}
            </div>
          ))}
          {!summary.judgment.length && <div className="px-4 py-3 text-xs text-[#677089]">회계 판단 항목이 없습니다.</div>}
        </div>
      </div>

      <div className="border border-[#D0D5E0] p-4 space-y-3">
        <div className="text-[11px] text-[#677089]">{summary.approval_policy}</div>
        <div className="grid grid-cols-2 gap-3">
          <TextInput label="검토자 이름" value={reviewerName} onChange={setReviewerName} placeholder="검토자" />
          <TextInput label="검토 메모" value={memo} onChange={setMemo} placeholder="판단 근거, 수정 요청 사유 등" />
        </div>
        <div className="flex items-center gap-2">
          <button
            disabled={busy || !summary.can_approve}
            onClick={() => submit("approved")}
            className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 disabled:bg-[#C8D0DC]"
            title={summary.can_approve ? "" : summary.has_conversion ? "오류 항목을 해결해야 승인할 수 있습니다" : "변환 초안을 먼저 생성하세요"}
          >
            승인 (2차 승인)
          </button>
          <button disabled={busy || !summary.has_conversion} onClick={() => submit("changes_requested")} className="px-4 py-2 text-xs font-bold text-white bg-amber-600 disabled:bg-[#C8D0DC]">
            수정 요청
          </button>
          {result && <span className="text-xs font-semibold text-[#1740BE]">{result}</span>}
        </div>
      </div>
    </div>
  );
}

function AuditTable({ projectId, logs }: { projectId: string; logs: AuditLog[] }) {
  const [items, setItems] = useState<AuditLog[]>(logs);
  useEffect(() => {
    api<AuditLog[]>(`/api/projects/${projectId}/audit`).then(setItems).catch(() => setItems([]));
  }, [projectId]);
  return (
    <div className="border border-[#D0D5E0] overflow-x-auto">
      <table className="w-full text-xs">
        <thead><tr className="bg-[#F5F7FA]"><HeaderCell>시각</HeaderCell><HeaderCell>사용자</HeaderCell><HeaderCell>이벤트</HeaderCell><HeaderCell>상세</HeaderCell></tr></thead>
        <tbody>
          {items.map((log) => (
            <tr key={log.id} className="border-t border-[#EEF0F5]">
              <td className="px-4 py-2.5 font-mono text-[#677089]">{log.created_at?.slice(0, 19).replace("T", " ")}</td>
              <td className="px-4 py-2.5">{log.actor}</td>
              <td className="px-4 py-2.5 font-semibold">{log.event_type}</td>
              <td className="px-4 py-2.5 text-[#677089] max-w-[480px] truncate">{JSON.stringify(log.detail)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!items.length && <div className="text-center py-10 text-xs text-[#677089]">감사 로그가 없습니다</div>}
    </div>
  );
}

function ExportPanel({ ready, onExport }: { ready: boolean; onExport: (name: string) => void }) {
  const exports = [
    ["adjustments.csv", "조정분개 CSV", "조정분개 후보 전체를 CSV로 내보냅니다", FileText],
    ["basis-report.txt", "검토 근거 리포트 TXT", "K-IFRS 변환 검토 근거를 텍스트로 생성합니다", FileCheck],
    ["review-workbook.xlsx", "검토용 Excel Workbook", "원본 DART 계정매핑 조정분개 검토근거 감사로그 5개 시트", FileSpreadsheet],
  ] as const;
  return (
    <div className="border border-[#D0D5E0]">
      {exports.map(([name, title, desc, Icon], index) => (
        <div key={name} className={classNames("flex items-center gap-4 px-5 py-4", index < exports.length - 1 && "border-b border-[#D0D5E0]")}>
          <div className="w-9 h-9 bg-[#EEF0F5] flex items-center justify-center border border-[#D0D5E0]"><Icon className="w-4 h-4 text-[#677089]" /></div>
          <div className="flex-1">
            <div className="text-sm font-bold text-[#0A1628]">{title}</div>
            <div className="text-xs text-[#677089] mt-0.5">{desc}</div>
          </div>
          <button disabled={!ready} onClick={() => onExport(name)} className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold text-white bg-[#0A1628] disabled:bg-[#C8D0DC]">
            <Download className="w-3.5 h-3.5" />
            다운로드
          </button>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [bundle, setBundle] = useState<ProjectBundle | null>(null);
  const [screen, setScreen] = useState<Screen>("import");
  const [reviewTab, setReviewTab] = useState<ReviewTab>("checklist");
  const [focusTarget, setFocusTarget] = useState<FocusTarget | null>(null);
  const [accountOptions, setAccountOptions] = useState<AccountOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [dartReady, setDartReady] = useState(false);
  const [toast, setToast] = useState("");

  async function loadSession() {
    setLoading(true);
    try {
      const session = await api<{ authenticated: boolean; user: UserInfo | null }>("/api/auth/session");
      setUser(session.user);
      if (session.user) {
        await loadProjects();
        const config = await api<{ api_key_ready: boolean }>("/api/dart-config");
        setDartReady(config.api_key_ready);
      }
    } finally {
      setLoading(false);
    }
  }

  async function loadProjects() {
    const list = await api<Project[]>("/api/projects");
    setProjects(list);
  }

  async function loadProject(projectId: string) {
    const next = await api<ProjectBundle>(`/api/projects/${projectId}`);
    setBundle(next);
  }

  useEffect(() => {
    loadSession().catch(() => setLoading(false));
  }, []);

  // 재분류 드롭다운 옵션: 표준계정 카탈로그를 로그인 후 한 번 로드한다 ('other' 제외).
  useEffect(() => {
    if (!user) return;
    api<{ accounts: AccountOption[] }>("/api/reference-data")
      .then((data) => setAccountOptions((data.accounts || []).filter((account) => account.account_key !== "other")))
      .catch(() => setAccountOptions([]));
  }, [user]);

  async function logout() {
    await api("/api/auth/logout", { method: "POST", body: "{}" });
    setUser(null);
    setBundle(null);
    setProjects([]);
  }

  async function createProject(payload: { company_name: string; period: string }) {
    const project = await api<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify({ ...payload, source_standard: "K-GAAP", target_standard: "K-IFRS" }),
    });
    await loadProjects();
    await loadProject(project.id);
    setScreen("import");
  }

  async function deleteProject(project: Project) {
    await api<{ deleted: boolean }>(`/api/projects/${project.id}`, { method: "DELETE" });
    setProjects((items) => items.filter((item) => item.id !== project.id));
    if (bundle?.project.id === project.id) {
      setBundle(null);
    }
  }

  async function refreshBundle() {
    if (bundle) await loadProject(bundle.project.id);
  }

  async function uploadFile(file: File) {
    if (!bundle) return;
    const form = new FormData();
    form.append("file", file);
    await api(`/api/projects/${bundle.project.id}/uploads`, { method: "POST", body: form });
    await refreshBundle();
  }

  async function extractUpload(uploadId: string) {
    if (!bundle) return;
    await api(`/api/projects/${bundle.project.id}/uploads/${uploadId}/extract`, { method: "POST", body: "{}" });
    await refreshBundle();
  }

  async function acceptExtraction(extractionId: string, aiDecisions: Record<string, AiDecision>) {
    if (!bundle) return;
    await api(`/api/projects/${bundle.project.id}/extractions/${extractionId}/accept`, {
      method: "POST",
      body: JSON.stringify({ ai_decisions: aiDecisions }),
    });
    await refreshBundle();
  }

  async function dartImport(payload: Record<string, string>) {
    if (!bundle) return;
    await api(`/api/projects/${bundle.project.id}/dart/import`, { method: "POST", body: JSON.stringify(payload) });
    await refreshBundle();
  }

  async function dartReports(payload: Record<string, string>) {
    if (!bundle) return { reports: [], issues: [], metadata: {} };
    return api<{ reports: DartReportOption[]; issues: string[]; metadata: Record<string, string> }>(`/api/projects/${bundle.project.id}/dart/reports`, { method: "POST", body: JSON.stringify(payload) });
  }

  async function manualAdd(rows: SourceRow[]) {
    if (!bundle) return;
    await api(`/api/projects/${bundle.project.id}/statements`, { method: "POST", body: JSON.stringify({ rows, source: "manual" }) });
    await refreshBundle();
  }

  async function convert(responses: Record<string, Record<string, unknown>>) {
    if (!bundle) return;
    await api(`/api/projects/${bundle.project.id}/convert`, { method: "POST", body: JSON.stringify({ responses }) });
    await refreshBundle();
    setReviewTab("adjustments");
    setToast("변환 초안을 생성했습니다");
  }

  // 검토 요약의 행동 버튼: 서버가 내려준 action대로 해결 지점으로 이동시킨다.
  function summaryAction(action: SummaryAction, statementId?: string) {
    if (action === "fill_checklist") {
      setScreen("review");
      setReviewTab("checklist");
    } else {
      setScreen("import");
    }
    setFocusTarget({ kind: action, statementId, seq: Date.now() });
  }

  async function reclassify(statementId: string, accountKey: string) {
    if (!bundle) return;
    await api(`/api/projects/${bundle.project.id}/statements/${statementId}/classify`, {
      method: "PATCH",
      body: JSON.stringify({ account_key: accountKey }),
    });
    await refreshBundle();
    setToast("재분류를 반영했습니다 (감사 로그 기록)");
  }

  const projectById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#E8EBF0] flex items-center justify-center text-sm text-[#677089]">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        로딩 중
      </div>
    );
  }

  if (!user) return <LoginScreen onLoggedIn={(nextUser) => { setUser(nextUser); loadProjects(); }} />;

  if (!bundle) {
    return (
      <ProjectDashboard
        user={user}
        projects={projects}
        loading={loading}
        onCreate={createProject}
        onDelete={deleteProject}
        onLogout={logout}
        onOpen={(project) => loadProject(project.id)}
      />
    );
  }

  const currentProject = projectById.get(bundle.project.id);
  const liveBundle = currentProject ? { ...bundle, project: currentProject } : bundle;
  return (
    <>
      {toast && (
        <div className="fixed right-4 top-4 z-50 bg-[#0A1628] text-white text-xs font-bold px-4 py-2">
          {toast}
          <button className="ml-3" onClick={() => setToast("")}>닫기</button>
        </div>
      )}
      <ProjectLayout
        bundle={liveBundle}
        screen={screen}
        reviewTab={reviewTab}
        setScreen={setScreen}
        setReviewTab={setReviewTab}
        onBack={() => { setBundle(null); loadProjects(); }}
        onRefresh={refreshBundle}
      >
        {screen === "import" ? (
          <ImportScreen
            bundle={liveBundle}
            dartReady={dartReady}
            onUpload={uploadFile}
            onExtract={extractUpload}
            onAccept={acceptExtraction}
            onDartReports={dartReports}
            onDartImport={dartImport}
            onManualAdd={manualAdd}
            onGoNext={() => { setScreen("review"); setReviewTab("checklist"); }}
            focusTarget={focusTarget}
            accountOptions={accountOptions}
            onReclassify={reclassify}
          />
        ) : (
          <ReviewScreen
            bundle={liveBundle}
            tab={reviewTab}
            setTab={setReviewTab}
            onConvert={convert}
            onExport={(name) => download(`/api/projects/${liveBundle.project.id}/exports/${name}`)}
            focusTarget={focusTarget}
            onSummaryAction={summaryAction}
          />
        )}
      </ProjectLayout>
    </>
  );
}
