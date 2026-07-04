export function fmtKRW(value: number) {
  if (!value) return "0";
  const abs = Math.abs(value).toLocaleString("ko-KR");
  return value < 0 ? `(${abs})` : abs;
}

export function statusColor(status: string) {
  if (status === "approved") return "green";
  if (status === "changes_requested" || status === "source_import_failed" || status === "failed") return "red";
  if (status === "draft_generated" || status === "needs_review" || status === "mapped") return "amber";
  if (status === "extracted" || status === "source_uploaded") return "blue";
  return "gray";
}

export function classNames(...values: Array<string | false | undefined>) {
  return values.filter(Boolean).join(" ");
}
