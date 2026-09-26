"use client"
import { useState } from "react"
import { api, type AnalysisRun, type Content } from "@/lib/api"
import { toKSTDateTime } from "@/lib/utils"

export function AnalysisHistory({ content }: { content: Content }) {
  const [runs, setRuns] = useState<AnalysisRun[] | null>(null)
  const [error, setError] = useState("")
  return <div className="space-y-2 text-xs text-slate-400">
    <button type="button" className="text-indigo-400" onClick={() => {
      if (runs) { setRuns(null); return }
      api.getAnalysisRuns(content).then(setRuns).catch(() => setError("분석 이력을 불러오지 못했습니다."))
    }}>분석 이력 {runs ? "닫기" : "보기"}</button>
    {error && <p role="alert" className="text-red-400">{error}</p>}
    {runs?.map(run => <div key={run.id} className="rounded border border-slate-700 p-2">
      {toKSTDateTime(run.created_at)} · {run.source} · {run.status} · {run.risk_level} ({run.risk_score.toFixed(2)})<br />
      {run.provider ?? "기존"}/{run.model ?? "미기록"} · 정책 {run.policy_version} · 프롬프트 {run.prompt_version} · {run.latency_ms == null ? "시간 미기록" : `${run.latency_ms}ms`}
    </div>)}
  </div>
}
