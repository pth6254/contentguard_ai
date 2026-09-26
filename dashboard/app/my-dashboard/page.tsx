"use client"
import { useEffect, useState } from "react"
import { api, type AnalysisJob, type ClientDashboard, type ClientWebhook, type Content } from "@/lib/api"
import { toKSTDateTime } from "@/lib/utils"

export default function MyDashboardPage() {
  const [summary, setSummary] = useState<ClientDashboard | null>(null)
  const [contents, setContents] = useState<Content[]>([])
  const [webhooks, setWebhooks] = useState<ClientWebhook[]>([])
  const [jobs, setJobs] = useState<AnalysisJob[]>([])
  const [error, setError] = useState("")
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState("")
  const load = () => Promise.all([api.getMyDashboard(), api.getMyContents(page * 20, search), api.getMyWebhooks(), api.listJobs()])
    .then(([stats, records, deliveries, ownJobs]) => { setSummary(stats); setContents(records.items); setTotal(records.total); setWebhooks(deliveries); setJobs(ownJobs); setError("") })
    .catch(() => setError("내 데이터를 불러오지 못했습니다."))
  useEffect(() => { load() }, [page, search])

  return <div className="space-y-5">
    <h1 className="text-2xl font-bold text-slate-100">{summary?.client.name ?? "고객"} 분석 현황</h1>
    {error && <p role="alert" className="text-red-400">{error} <button onClick={load} className="underline">재시도</button></p>}
    {summary && <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {[["전체 분석", summary.total], ["심사 대기", summary.by_status.PENDING ?? 0],
        ["진행 중 작업", (summary.jobs.PENDING ?? 0) + (summary.jobs.PROCESSING ?? 0)],
        ["웹훅 실패", summary.webhooks.FAILED ?? 0]].map(([label, value]) => <div key={label} className="rounded border border-slate-700 bg-slate-800 p-3"><p className="text-xs text-slate-400">{label}</p><p className="text-xl font-bold text-slate-100">{value}</p></div>)}
      <p className="col-span-full text-xs text-slate-500">적용 중인 고객 정책: {summary.policy_version ? `v${summary.policy_version}` : "기본 정책"}</p>
    </div>}
    <div className="space-y-2">
      <h2 className="text-lg font-semibold text-slate-100">내 콘텐츠 ({total}건)</h2>
      <input aria-label="콘텐츠 ID 검색" value={search} onChange={e => { setSearch(e.target.value); setPage(0) }} placeholder="콘텐츠 ID 검색" className="w-full rounded bg-slate-800 p-2 text-slate-100" />
      {contents.map(content => <div key={content.id} className="rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
        <p className="font-mono">{content.content_id} · {content.risk_level} · {content.review_status}</p>
        <p className="line-clamp-2 text-slate-400">{content.text}</p>
        <p className="text-xs text-slate-500">{toKSTDateTime(content.created_at)}</p>
      </div>)}
      <div className="flex gap-3 text-sm text-indigo-300"><button disabled={page === 0} onClick={() => setPage(page - 1)} className="disabled:opacity-40">이전</button><span>{page + 1}페이지</span><button disabled={(page + 1) * 20 >= total} onClick={() => setPage(page + 1)} className="disabled:opacity-40">다음</button></div>
    </div>
    <div className="space-y-2"><h2 className="text-lg font-semibold text-slate-100">최근 웹훅 전달</h2>
      {webhooks.length === 0 && <p className="text-sm text-slate-500">전달 내역이 없습니다.</p>}
      {webhooks.slice(0, 10).map(item => <p key={item.event_id} className="rounded bg-slate-800 p-2 text-sm text-slate-300">{item.content_id} · 심사 v{item.review_version} · {item.status} · 시도 {item.attempts}회</p>)}
    </div>
    <div className="space-y-2"><h2 className="text-lg font-semibold text-slate-100">최근 분석 작업</h2>
      {jobs.length === 0 && <p className="text-sm text-slate-500">접수된 작업이 없습니다.</p>}
      {jobs.slice(0, 10).map(job => <p key={job.id} className="rounded bg-slate-800 p-2 text-sm text-slate-300">{job.content_id} · {job.status}{job.last_error ? ` · 오류 ${job.last_error}` : ""}</p>)}
    </div>
  </div>
}
