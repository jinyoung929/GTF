import type { ReactNode } from "react";

import { classNames, statusColor } from "./format";

const statusLabels: Record<string, string> = {
  created: "초안",
  source_uploaded: "업로드 완료",
  extracted: "추출 완료",
  mapped: "매핑 완료",
  draft_generated: "검토 필요",
  approved: "승인 완료",
  changes_requested: "수정 요청",
  source_import_failed: "가져오기 실패",
};

export function SectionLabel({ children }: { children: ReactNode }) {
  return <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{children}</span>;
}

export function Pill({ color, children }: { color: string; children: ReactNode }) {
  const cls =
    color === "green"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : color === "red"
        ? "bg-red-50 text-red-700 ring-red-200"
        : color === "amber"
          ? "bg-amber-50 text-amber-800 ring-amber-200"
          : color === "blue"
            ? "bg-blue-50 text-blue-700 ring-blue-200"
            : "bg-slate-50 text-slate-600 ring-slate-200";
  return <span className={`inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded ring-1 ${cls}`}>{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return <Pill color={statusColor(status)}>{statusLabels[status] || status}</Pill>;
}

export function HeaderCell({ children, right = false }: { children: ReactNode; right?: boolean }) {
  return (
    <th className={classNames("px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest text-[#677089]", right ? "text-right" : "text-left")}>
      {children}
    </th>
  );
}
