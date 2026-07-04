import { useState } from "react";
import type { FormEvent } from "react";
import FileCheck from "lucide-react/dist/esm/icons/file-check.js";

import { api } from "../api";
import type { UserInfo } from "../types";
import { SectionLabel } from "../ui";

export function LoginScreen({ onLoggedIn }: { onLoggedIn: (user: UserInfo) => void }) {
  const [email, setEmail] = useState("demo@gtf.local");
  const [password, setPassword] = useState("change-this-demo-password");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await api<{ authenticated: boolean; user: UserInfo }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      onLoggedIn(result.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인 실패");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#E8EBF0] flex items-center justify-center px-4">
      <div className="w-full max-w-[380px]">
        <div className="flex items-center gap-3 mb-9">
          <div className="w-10 h-10 bg-[#1740BE] flex items-center justify-center">
            <FileCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-lg font-bold text-[#0A1628] leading-none">GTF IFRS Bridge</div>
            <div className="text-xs text-[#677089] mt-1 font-medium">K-GAAP to K-IFRS 변환 검토 시스템</div>
          </div>
        </div>

        <form onSubmit={submit} className="bg-white border border-[#D0D5E0]">
          <div className="px-6 py-5 border-b border-[#D0D5E0]">
            <SectionLabel>관리자 로그인</SectionLabel>
          </div>
          <div className="px-6 py-5 space-y-4">
            <label className="block">
              <span className="block text-xs font-bold uppercase tracking-wide text-[#677089] mb-1.5">이메일</span>
              <input value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA] focus:outline-none focus:border-[#1740BE]" />
            </label>
            <label className="block">
              <span className="block text-xs font-bold uppercase tracking-wide text-[#677089] mb-1.5">비밀번호</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full px-3 py-2 text-sm border border-[#D0D5E0] bg-[#F5F7FA] focus:outline-none focus:border-[#1740BE]" />
            </label>
            {error && <div className="text-xs font-semibold text-red-700 bg-red-50 border border-red-200 px-3 py-2">{error}</div>}
            <button disabled={loading} className="w-full py-2.5 bg-[#1740BE] hover:bg-[#1234A8] disabled:opacity-60 text-white text-sm font-bold transition-colors">
              {loading ? "인증 중" : "로그인"}
            </button>
          </div>
          <div className="px-6 py-3.5 bg-[#F5F7FA] border-t border-[#D0D5E0] text-xs text-[#677089]">
            데모 계정은 읽기 전용입니다
          </div>
        </form>
      </div>
    </div>
  );
}
