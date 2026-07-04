import { useState } from "react";
import ChevronRight from "lucide-react/dist/esm/icons/chevron-right.js";
import FileCheck from "lucide-react/dist/esm/icons/file-check.js";
import LogOut from "lucide-react/dist/esm/icons/log-out.js";
import Plus from "lucide-react/dist/esm/icons/plus.js";
import X from "lucide-react/dist/esm/icons/x.js";

import { classNames } from "../format";
import type { Project, UserInfo } from "../types";
import { HeaderCell, SectionLabel, StatusBadge } from "../ui";

export function ProjectDashboard({
  projects,
  user,
  onOpen,
  onCreate,
  onLogout,
  loading,
}: {
  projects: Project[];
  user: UserInfo;
  onOpen: (project: Project) => void;
  onCreate: (payload: { company_name: string; period: string }) => void;
  onLogout: () => void;
  loading: boolean;
}) {
  const [showModal, setShowModal] = useState(false);
  const [company, setCompany] = useState("샘플테크 주식회사");
  const [period, setPeriod] = useState("2026");

  function submitCreate() {
    onCreate({ company_name: company, period });
    setShowModal(false);
  }

  const reviewCount = projects.filter((project) => ["draft_generated", "mapped", "changes_requested"].includes(project.status)).length;
  return (
    <div className="min-h-screen bg-[#E8EBF0]">
      <header className="h-12 bg-[#0D1724] flex items-center px-6 justify-between">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 bg-[#1740BE] flex items-center justify-center">
            <FileCheck className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-bold text-white text-sm">GTF IFRS Bridge</span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className="text-[#8A96A8]">{user.email}</span>
          <button onClick={onLogout} className="flex items-center gap-1.5 text-[#8A96A8] hover:text-white">
            <LogOut className="w-3.5 h-3.5" />
            로그아웃
          </button>
        </div>
      </header>

      <div className="bg-white border-b border-[#D0D5E0]">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-base font-bold text-[#0A1628]">프로젝트</h1>
            <p className="text-xs text-[#677089] mt-0.5 font-medium">K-GAAP to K-IFRS 변환 검토 프로젝트 관리</p>
          </div>
          <button disabled={user.is_read_only} onClick={() => setShowModal(true)} className="flex items-center gap-2 px-3.5 py-2 bg-[#1740BE] hover:bg-[#1234A8] disabled:bg-[#C8D0DC] text-white text-xs font-bold transition-colors">
            <Plus className="w-3.5 h-3.5" />
            새 프로젝트
          </button>
        </div>
      </div>

      <main className="max-w-6xl mx-auto px-6 py-6 space-y-5">
        <div className="grid grid-cols-4 gap-4">
          {[
            ["전체 프로젝트", projects.length, "활성 프로젝트"],
            ["검토 필요", reviewCount, "승인 대기"],
            ["승인 완료", projects.filter((p) => p.status === "approved").length, "완료"],
            ["읽기 전용", user.is_read_only ? "ON" : "OFF", "현재 계정"],
          ].map(([label, value, sub]) => (
            <div key={String(label)} className="bg-white border border-[#D0D5E0] px-5 py-4">
              <SectionLabel>{label}</SectionLabel>
              <div className="text-2xl font-bold font-mono text-[#0A1628] mt-1">{value}</div>
              <div className="text-xs text-[#677089] mt-1">{sub}</div>
            </div>
          ))}
        </div>

        <div className="bg-white border border-[#D0D5E0]">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#D0D5E0]">
            <SectionLabel>{loading ? "불러오는 중" : `${projects.length}개 프로젝트`}</SectionLabel>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#F5F7FA] border-b border-[#D0D5E0]">
                <HeaderCell>회사명</HeaderCell>
                <HeaderCell right>사업연도</HeaderCell>
                <HeaderCell>기준</HeaderCell>
                <HeaderCell>상태</HeaderCell>
                <HeaderCell>최근 수정</HeaderCell>
                <HeaderCell></HeaderCell>
              </tr>
            </thead>
            <tbody>
              {projects.map((project, index) => (
                <tr key={project.id} className={classNames("border-b border-[#EEF0F5] hover:bg-[#F5F7FA]", index % 2 === 1 && "bg-[#FAFBFC]")}>
                  <td className="px-4 py-3 font-semibold text-[#0A1628]">{project.company_name}</td>
                  <td className="px-4 py-3 text-right font-mono">{project.period}</td>
                  <td className="px-4 py-3 text-xs text-[#677089]">{project.source_standard} to {project.target_standard}</td>
                  <td className="px-4 py-3"><StatusBadge status={project.status} /></td>
                  <td className="px-4 py-3 font-mono text-xs text-[#677089]">{project.updated_at?.slice(0, 10)}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => onOpen(project)} className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold text-[#1740BE] border border-[#1740BE]/30 bg-blue-50 hover:bg-[#1740BE] hover:text-white">
                      열기 <ChevronRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!projects.length && <div className="text-center py-12 text-sm text-[#677089]">프로젝트가 없습니다</div>}
        </div>
      </main>

      {showModal && (
        <div className="fixed inset-0 bg-[#0A1628]/50 flex items-center justify-center z-50">
          <div className="bg-white border border-[#D0D5E0] w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#D0D5E0] bg-[#F5F7FA]">
              <SectionLabel>새 프로젝트 생성</SectionLabel>
              <button onClick={() => setShowModal(false)}><X className="w-4 h-4" /></button>
            </div>
            <div className="p-5 space-y-4">
              <label className="block">
                <span className="block text-xs font-bold uppercase tracking-wide text-[#677089] mb-1.5">회사명</span>
                <input value={company} onChange={(e) => setCompany(e.target.value)} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA]" />
              </label>
              <label className="block">
                <span className="block text-xs font-bold uppercase tracking-wide text-[#677089] mb-1.5">사업연도</span>
                <input value={period} onChange={(e) => setPeriod(e.target.value)} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA] font-mono" />
              </label>
            </div>
            <div className="flex border-t border-[#D0D5E0]">
              <button onClick={() => setShowModal(false)} className="flex-1 py-3 text-sm font-bold text-[#677089] bg-[#F5F7FA]">취소</button>
              <button onClick={submitCreate} className="flex-1 py-3 text-sm font-bold text-white bg-[#1740BE]">생성</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
