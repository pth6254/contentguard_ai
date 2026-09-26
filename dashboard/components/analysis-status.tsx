import type { Content } from "@/lib/api"

export function AnalysisStatus({ content }: { content: Content }) {
  const status = content.explanation_json?.analysis_status
  const review = content.needs_re_review ? <span className="rounded border border-orange-600 bg-orange-950 px-2 py-0.5 text-xs font-semibold text-orange-300">재심사 필요</span> : null
  if (status === "fallback") {
    return <>{review}<span className="rounded border border-amber-600 bg-amber-950 px-2 py-0.5 text-xs font-semibold text-amber-300" title="AI 분석 실패: 임시 결과이며 직접 검토가 필요합니다">임시 분석 · 직접 검토</span></>
  }
  if (status === "completed") {
    return <>{review}<span className="rounded border border-emerald-800 bg-emerald-950 px-2 py-0.5 text-xs text-emerald-300">분석 완료</span></>
  }
  return <>{review}<span className="rounded border border-slate-600 bg-slate-800 px-2 py-0.5 text-xs text-slate-400">분석 상태 미기록</span></>
}
