"use client"
import { useCallback, useEffect, useRef, useState } from "react"
import { api, type AnalysisJob, type ClientDashboard, type ClientWebhook, type Content } from "@/lib/api"
import { toKSTDateTime } from "@/lib/utils"
import { AnalysisStatus } from "@/components/analysis-status"
import { CategoryScoreBars } from "@/components/category-score-bars"
import { HighlightedText } from "@/components/highlighted-text"
import { JOB_STATUS } from "@/components/jobs-panel"

export default function MyDashboardPage() {
  const [summary, setSummary] = useState<ClientDashboard | null>(null)
  const [contents, setContents] = useState<Content[]>([])
  const [webhooks, setWebhooks] = useState<ClientWebhook[]>([])
  const [jobs, setJobs] = useState<AnalysisJob[]>([])
  const [error, setError] = useState("")
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState("")
  const [message, setMessage] = useState("")
  const [retrying, setRetrying] = useState<number | null>(null)
  const sequence = useRef(0)
  useEffect(() => { setSearch(new URLSearchParams(window.location.search).get("search") ?? "") }, [])
  const load = useCallback(async () => {
    const request = ++sequence.current
    try {
      const [stats, records, deliveries, ownJobs] = await Promise.all([api.getMyDashboard(), api.getMyContents(page * 20, search), api.getMyWebhooks(), api.getJobs({ limit: 10 })])
      if (request !== sequence.current) return
      setSummary(stats); setContents(records.items); setTotal(records.total); setWebhooks(deliveries); setJobs(ownJobs.items); setError("")
    } catch { if (request === sequence.current) setError("내 데이터를 불러오지 못했습니다.") }
  }, [page, search])
  useEffect(() => { load(); const timer = setInterval(load, 10000); return () => { clearInterval(timer); sequence.current++ } }, [load])
  const retry = async (id: number) => {
    setRetrying(id)
    try { await api.retryMyContent(id); setMessage("다시 분석하도록 접수했습니다. 작업 관리에서 진행 상황을 확인하세요."); await load() }
    catch { setMessage("재분석을 접수하지 못했습니다. 현재 결과를 다시 확인하세요.") }
    finally { setRetrying(null) }
  }

  return <div className="space-y-5">
    <h1 className="text-2xl font-bold text-slate-100">{summary?.client.name ?? "고객"} 분석 현황</h1>
    {error && <p role="alert" className="text-red-400">{error} <button onClick={load} className="underline">재시도</button></p>}
    {message && <p role="status" className="text-sm text-indigo-300">{message}</p>}
    {summary && <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {[["전체 분석", summary.total], ["심사·재심사 대기", (summary.by_status.PENDING ?? 0) + summary.re_review_required],
        ["진행 중 작업", (summary.jobs.PENDING ?? 0) + (summary.jobs.PROCESSING ?? 0)],
        ["웹훅 실패", summary.webhooks.FAILED ?? 0]].map(([label, value]) => <div key={label} className="rounded border border-slate-700 bg-slate-800 p-3"><p className="text-xs text-slate-400">{label}</p><p className="text-xl font-bold text-slate-100">{value}</p></div>)}
      <p className="col-span-full text-xs text-slate-500">적용 중인 고객 정책: {summary.policy_version ? `v${summary.policy_version}` : "기본 정책"}</p>
    </div>}
    <div className="space-y-2">
      <h2 className="text-lg font-semibold text-slate-100">내 콘텐츠 ({total}건)</h2>
      <input aria-label="콘텐츠 ID 검색" value={search} onChange={e => { setSearch(e.target.value); setPage(0) }} placeholder="콘텐츠 ID 검색" className="w-full rounded bg-slate-800 p-2 text-slate-100" />
      {contents.map(content => <div key={content.id} className="rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
        <p className="font-mono">{content.content_id} · {content.risk_level} · {content.review_status}</p>
        <AnalysisStatus content={content} />
        <p className="line-clamp-2 text-slate-400">{content.text}</p>
        <p className="text-xs text-slate-500">{toKSTDateTime(content.created_at)}</p>
        <details className="mt-2 space-y-3"><summary className="cursor-pointer text-indigo-300">분석 근거 상세</summary>
          <div className="mt-3 rounded bg-slate-900 p-3"><HighlightedText text={content.text} spans={content.evidence_spans ?? []} /></div>
          {content.category_scores && <CategoryScoreBars scores={content.category_scores} />}
          <p>{content.explanation}</p><p className="text-slate-400">{content.explanation_json?.recommended_operator_check}</p>
        </details>
        {content.explanation_json?.analysis_status === "fallback" && <button disabled={retrying != null} onClick={() => retry(content.id)} className="mt-2 text-indigo-300 disabled:opacity-40">{retrying === content.id ? "접수 중…" : "임시 결과 다시 분석"}</button>}
      </div>)}
      <div className="flex gap-3 text-sm text-indigo-300"><button disabled={page === 0} onClick={() => setPage(page - 1)} className="disabled:opacity-40">이전</button><span>{page + 1}페이지</span><button disabled={(page + 1) * 20 >= total} onClick={() => setPage(page + 1)} className="disabled:opacity-40">다음</button></div>
    </div>
    <div className="space-y-2"><h2 className="text-lg font-semibold text-slate-100">최근 웹훅 전달</h2>
      {webhooks.length === 0 && <p className="text-sm text-slate-500">전달 내역이 없습니다.</p>}
      {webhooks.slice(0, 10).map(item => <p key={item.event_id} className="rounded bg-slate-800 p-2 text-sm text-slate-300">{item.content_id} · 심사 v{item.review_version} · {item.status} · 시도 {item.attempts}회</p>)}
    </div>
    <div className="space-y-2"><h2 className="text-lg font-semibold text-slate-100">최근 분석 작업</h2>
      {jobs.length === 0 && <p className="text-sm text-slate-500">접수된 작업이 없습니다.</p>}
      {jobs.slice(0, 10).map(job => <p key={job.id} className="rounded bg-slate-800 p-2 text-sm text-slate-300">{job.content_id} · {JOB_STATUS[job.status]}</p>)}
      <a href="/my-jobs" className="text-sm text-indigo-300">전체 작업 확인 · 재시도</a>
    </div>
  </div>
}
