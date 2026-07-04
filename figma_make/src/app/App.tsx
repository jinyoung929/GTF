import { useEffect, useMemo, useState } from "react";
import AlertTriangle from "lucide-react/dist/esm/icons/alert-triangle.js";
import ClipboardList from "lucide-react/dist/esm/icons/clipboard-list.js";
import Cloud from "lucide-react/dist/esm/icons/cloud.js";
import Database from "lucide-react/dist/esm/icons/database.js";
import Download from "lucide-react/dist/esm/icons/download.js";
import FileCheck from "lucide-react/dist/esm/icons/file-check.js";
import FileSpreadsheet from "lucide-react/dist/esm/icons/file-spreadsheet.js";
import FileText from "lucide-react/dist/esm/icons/file-text.js";
import History from "lucide-react/dist/esm/icons/history.js";
import Loader2 from "lucide-react/dist/esm/icons/loader-circle.js";
import PanelRightClose from "lucide-react/dist/esm/icons/panel-right-close.js";
import PanelRightOpen from "lucide-react/dist/esm/icons/panel-right-open.js";
import RefreshCw from "lucide-react/dist/esm/icons/refresh-cw.js";
import Upload from "lucide-react/dist/esm/icons/upload.js";

import { api, download } from "./api";
import { classNames, fmtKRW } from "./format";
import { LoginScreen } from "./screens/LoginScreen";
import { ProjectDashboard } from "./screens/ProjectDashboard";
import type { AuditLog, Conversion, ConversionEntry, ImportTab, Project, ProjectBundle, ReviewTab, Screen, SourceRow, Statement, UploadRow, UserInfo } from "./types";
import { HeaderCell, Pill, SectionLabel, StatusBadge } from "./ui";

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
  onDartImport,
  onManualAdd,
}: {
  bundle: ProjectBundle;
  dartReady: boolean;
  onUpload: (file: File) => Promise<void>;
  onExtract: (uploadId: string) => Promise<void>;
  onAccept: (extractionId: string) => Promise<void>;
  onDartImport: (payload: Record<string, string>) => Promise<void>;
  onManualAdd: (rows: SourceRow[]) => Promise<void>;
}) {
  const [tab, setTab] = useState<ImportTab>("file");
  const [busy, setBusy] = useState("");
  const [corpCode, setCorpCode] = useState("");
  const [companyName, setCompanyName] = useState(bundle.project.company_name);
  const [stockCode, setStockCode] = useState("");
  const [bsnsYear, setBsnsYear] = useState(bundle.project.period);
  const [fsDiv, setFsDiv] = useState("CFS");
  const [manualText, setManualText] = useState("현금및현금성자산,120000000\n리스부채,30000000\n개발비,45000000");
  const latestExtraction = bundle.extractions[0];
  const previewRows = latestExtraction?.rows || [];

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
                <SelectInput label="보고서" value="11011" options={[["11011", "사업보고서"], ["11012", "반기보고서"], ["11013", "1분기"], ["11014", "3분기"]]} />
                <label className="block">
                  <span className="block text-xs font-bold uppercase tracking-wide text-[#677089] mb-1.5">연결 별도</span>
                  <select value={fsDiv} onChange={(event) => setFsDiv(event.target.value)} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA]">
                    <option value="CFS">연결</option>
                    <option value="OFS">별도</option>
                  </select>
                </label>
              </div>
              <button disabled={!dartReady || !!busy} onClick={() => run("dart", () => onDartImport({ corp_code: corpCode, company_name: companyName, stock_code: stockCode, bsns_year: bsnsYear, reprt_code: "11011", fs_div: fsDiv }))} className="flex items-center gap-2 px-4 py-2 bg-[#1740BE] disabled:bg-[#C8D0DC] text-white text-xs font-bold">
                {busy === "dart" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Cloud className="w-3.5 h-3.5" />}
                DART에서 가져오기
              </button>
            </div>
          )}

          {tab === "manual" && (
            <div className="space-y-3">
              <textarea value={manualText} onChange={(event) => setManualText(event.target.value)} rows={6} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA] font-mono" />
              <button disabled={!!busy} onClick={() => run("manual", () => onManualAdd(parseManualRows()))} className="px-4 py-2 bg-[#1740BE] text-white text-xs font-bold">수동 계정 반영</button>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white border border-[#D0D5E0]">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#D0D5E0] bg-[#F5F7FA]">
          <SectionLabel>추출 결과 미리보기</SectionLabel>
          {latestExtraction && (
            <button disabled={latestExtraction.status === "accepted" || !!busy} onClick={() => run("accept", () => onAccept(latestExtraction.id))} className="px-3 py-1.5 text-xs font-bold text-white bg-[#1740BE] disabled:bg-[#C8D0DC]">
              추출 결과 반영
            </button>
          )}
        </div>
        <RowsTable rows={previewRows} />
      </div>

      <MappingTable statements={bundle.statements} />
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

function SelectInput({ label, value, options }: { label: string; value: string; options: [string, string][] }) {
  return (
    <label className="block">
      <span className="block text-xs font-bold uppercase tracking-wide text-[#677089] mb-1.5">{label}</span>
      <select defaultValue={value} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA]">
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

function RowsTable({ rows }: { rows: SourceRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead><tr className="bg-[#F5F7FA]"><HeaderCell>원 계정명</HeaderCell><HeaderCell right>금액</HeaderCell><HeaderCell>재무제표</HeaderCell><HeaderCell>통화</HeaderCell></tr></thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.account_name}-${index}`} className="border-t border-[#EEF0F5]">
              <td className="px-4 py-2.5 font-semibold">{row.account_name}</td>
              <td className="px-4 py-2.5 text-right font-mono">{fmtKRW(row.amount)}</td>
              <td className="px-4 py-2.5 text-[#677089]">{row.statement_type || "-"}</td>
              <td className="px-4 py-2.5 text-[#677089]">{row.currency || "KRW"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <div className="text-center py-10 text-xs text-[#677089]">추출 결과가 없습니다</div>}
    </div>
  );
}

function MappingTable({ statements }: { statements: Statement[] }) {
  return (
    <div className="bg-white border border-[#D0D5E0]">
      <div className="px-4 py-3 border-b border-[#D0D5E0] bg-[#F5F7FA]"><SectionLabel>계정 매핑</SectionLabel></div>
      <table className="w-full text-xs">
        <thead><tr className="bg-[#F5F7FA]"><HeaderCell>원 계정</HeaderCell><HeaderCell right>금액</HeaderCell><HeaderCell>표준계정</HeaderCell><HeaderCell>코드</HeaderCell><HeaderCell>유형</HeaderCell><HeaderCell>근거</HeaderCell></tr></thead>
        <tbody>
          {statements.map((row) => (
            <tr key={row.id} className={classNames("border-t border-[#EEF0F5]", row.mapping_type === "judgment" && "bg-amber-50/30")}>
              <td className="px-4 py-2.5 font-semibold">{row.account_name}</td>
              <td className="px-4 py-2.5 text-right font-mono">{fmtKRW(row.amount)}</td>
              <td className="px-4 py-2.5">{row.normalized_account}</td>
              <td className="px-4 py-2.5 font-mono text-[#677089]">{row.standard_code}</td>
              <td className="px-4 py-2.5"><Pill color={row.mapping_type === "judgment" ? "amber" : "blue"}>{row.mapping_type === "judgment" ? "판단 필요" : "단순 매핑"}</Pill></td>
              <td className="px-4 py-2.5 text-[#677089] max-w-[320px] truncate">{row.rule_summary}</td>
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
}: {
  bundle: ProjectBundle;
  tab: ReviewTab;
  setTab: (tab: ReviewTab) => void;
  onConvert: (responses: Record<string, Record<string, unknown>>) => Promise<void>;
  onExport: (name: string) => void;
}) {
  const [responses, setResponses] = useState<Record<string, Record<string, unknown>>>({});
  const [busy, setBusy] = useState(false);
  const judgmentStatements = bundle.statements.filter((statement) => statement.mapping_type === "judgment");
  const entries = bundle.conversion?.entries || [];

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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-[#0A1628]">K-IFRS 변환 리뷰</h2>
          <p className="text-xs text-[#677089] mt-0.5 font-medium">체크리스트 입력 후 변환 초안을 생성합니다</p>
        </div>
        <button disabled={busy || !bundle.statements.length} onClick={convert} className="flex items-center gap-1.5 px-3.5 py-2 bg-[#1740BE] disabled:bg-[#C8D0DC] text-white text-xs font-bold">
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          변환 생성
        </button>
      </div>

      <div className="bg-white border border-[#D0D5E0]">
        <div className="flex border-b border-[#D0D5E0]">
          {[
            ["checklist", "체크리스트"],
            ["adjustments", `조정분개 ${entries.length}`],
            ["notes", "주석 초안"],
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
                <div key={statement.id} className="border border-[#D0D5E0]">
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
            </div>
          )}

          {tab === "adjustments" && <AdjustmentTable entries={entries} />}
          {tab === "notes" && <Notes notes={bundle.conversion?.draft_notes || []} ai={bundle.conversion?.ai_assistance} />}
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

function Notes({ notes, ai }: { notes: Conversion["draft_notes"]; ai?: Conversion["ai_assistance"] }) {
  return (
    <div className="space-y-3">
      {notes.map((note) => (
        <div key={note.account} className="border border-[#D0D5E0]">
          <div className="px-4 py-2.5 bg-[#F5F7FA] border-b border-[#D0D5E0] text-xs font-bold">{note.account}</div>
          <p className="p-4 text-sm text-[#677089] leading-relaxed">{note.draft_note}</p>
        </div>
      ))}
      {ai && (
        <div className="border border-[#D0D5E0] p-4 bg-blue-50 text-xs text-blue-800">
          AI 판단 보조 {ai.status} · {ai.overall_note || "사람 검토 필요"}
        </div>
      )}
      {!notes.length && <div className="text-center py-10 text-xs text-[#677089]">주석 초안이 없습니다</div>}
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

  async function acceptExtraction(extractionId: string) {
    if (!bundle) return;
    await api(`/api/projects/${bundle.project.id}/extractions/${extractionId}/accept`, { method: "POST", body: "{}" });
    await refreshBundle();
  }

  async function dartImport(payload: Record<string, string>) {
    if (!bundle) return;
    await api(`/api/projects/${bundle.project.id}/dart/import`, { method: "POST", body: JSON.stringify(payload) });
    await refreshBundle();
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
            onDartImport={dartImport}
            onManualAdd={manualAdd}
          />
        ) : (
          <ReviewScreen
            bundle={liveBundle}
            tab={reviewTab}
            setTab={setReviewTab}
            onConvert={convert}
            onExport={(name) => download(`/api/projects/${liveBundle.project.id}/exports/${name}`)}
          />
        )}
      </ProjectLayout>
    </>
  );
}
