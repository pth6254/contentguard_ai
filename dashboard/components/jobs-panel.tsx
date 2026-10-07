"use client"
import { useCallback, useEffect, useRef, useState } from "react"
import { api, type AnalysisJob } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { toKSTDateTime } from "@/lib/utils"

export const JOB_STATUS: Record<string, string> = {
  PENDING: "대기", PROCESSING: "분석 중", COMPLETED: "완료", FAILED: "실패", CANCELLED: "취소", DEGRADED: "임시 분석 · 재시도 필요",
}
const retryable = (job: AnalysisJob) => job.status === "FAILED" || job.status === "DEGRADED"

export function JobsPanel({ customer = false }: { customer?: boolean }) {
  const [jobs, setJobs] = useState<AnalysisJob[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [clientId, setClientId] = useState("")
  const [batchId, setBatchId] = useState("")
  const [clients, setClients] = useState<{ id: number; name: string }[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [contentId, setContentId] = useState("")
  const [body, setBody] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const requestId = useRef(0)
  useEffect(() => {
    setBatchId(new URLSearchParams(window.location.search).get("batch_id") ?? "")
    if (!customer) api.getClients().then(setClients).catch(() => setError("고객 목록을 불러오지 못했습니다."))
  }, [customer])
  const load = useCallback(async () => {
    const request = ++requestId.current
    try {
      const result = await api.getJobs({ limit: 20, offset: page * 20, status, search, client_id: clientId, batch_id: batchId })
      if (request !== requestId.current) return
      setJobs(result.items); setTotal(result.total); setError("")
    } catch { if (request === requestId.current) setError("작업 목록을 불러오지 못했습니다.") }
  }, [page, status, search, clientId, batchId])
  useEffect(() => { load(); const timer = setInterval(load, 5000); return () => { clearInterval(timer); requestId.current++ } }, [load])
  const changed = () => { setPage(0); setSelected([]) }
  const submit = async () => {
    setBusy(true)
    try { await api.submitJob(contentId, body); setBody(""); setMessage("분석 작업을 접수했습니다."); await load() }
    catch { setMessage("접수하지 못했습니다. 콘텐츠 ID 중복 또는 입력 내용을 확인하세요.") }
    finally { setBusy(false) }
  }
  const act = async (job: AnalysisJob, action: "retry" | "cancel") => {
    setBusy(true)
    try { if (action === "retry") await api.retryJob(job.id); else await api.cancelJob(job.id); setMessage(action === "retry" ? "재시도를 접수했습니다." : "취소를 요청했습니다."); await load() }
    catch { setMessage("작업 상태가 변경되었거나 다른 분석이 진행 중입니다. 목록을 새로 확인하세요.") }
    finally { setBusy(false) }
  }
  const retrySelected = async () => {
    setBusy(true)
    try {
      const result = await api.retryJobs(selected)
      setMessage(`${result.accepted.length}건 재시도 접수 · ${result.errors.length}건 제외${result.errors.length ? ": " + result.errors.map(item => item.reason).join(" / ") : ""}`)
      setSelected(result.errors.map(item => item.id)); await load()
    } catch { setMessage("선택한 작업을 재시도하지 못했습니다.") }
    finally { setBusy(false) }
  }
  return <div className="space-y-5">
    <h1 className="text-2xl font-bold text-slate-100">분석 작업</h1>
    <p className="text-sm text-slate-400">임시 결과는 최대 3회 자동 재시도한 후 별도로 표시됩니다. 실패·임시 분석 작업을 선택해 다시 처리할 수 있습니다.</p>
    <details className="rounded border border-slate-700 bg-slate-800 p-4"><summary className="cursor-pointer text-slate-200">새 분석 접수</summary>
      <div className="mt-3 space-y-2">
        <input aria-label="콘텐츠 ID" value={contentId} onChange={e => setContentId(e.target.value)} maxLength={200} placeholder="콘텐츠 ID" className="w-full rounded bg-slate-900 p-2 text-slate-100" />
        <textarea aria-label="분석할 텍스트" value={body} onChange={e => setBody(e.target.value)} maxLength={8000} placeholder="분석할 텍스트" className="w-full rounded bg-slate-900 p-2 text-slate-100" />
        <Button disabled={busy || !contentId.trim() || !body.trim()} onClick={submit}>작업 접수</Button>
      </div>
    </details>
    <div className="flex flex-wrap gap-2">
      <input aria-label="작업 콘텐츠 ID 검색" placeholder="콘텐츠 ID 검색" value={search} onChange={e => { setSearch(e.target.value); changed() }} className="rounded bg-slate-800 p-2 text-slate-100" />
      <select aria-label="작업 상태" value={status} onChange={e => { setStatus(e.target.value); changed() }} className="rounded bg-slate-800 p-2 text-slate-100"><option value="">모든 상태</option>{Object.entries(JOB_STATUS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select>
      {!customer && <select aria-label="작업 고객" value={clientId} onChange={e => { setClientId(e.target.value); changed() }} className="rounded bg-slate-800 p-2 text-slate-100"><option value="">모든 고객</option>{clients.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}</select>}
      {batchId && <button onClick={() => { setBatchId(""); changed() }} className="text-sm text-indigo-300">현재 배치 필터 해제 ×</button>}
      <Button onClick={load} variant="ghost">새로고침</Button>
    </div>
    {error && <p role="alert" className="text-red-400">{error}</p>}
    {message && <p role="status" className="text-sm text-slate-300">{message}</p>}
    <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
      <span>전체 {total}건</span>
      <button onClick={() => setSelected(jobs.filter(retryable).map(job => job.id))} className="text-indigo-300">이 페이지의 실패·임시 분석 선택</button>
      <Button disabled={busy || !selected.length} onClick={retrySelected}>선택 {selected.length}건 재시도</Button>
    </div>
    {!jobs.length && !error && <p className="text-slate-400">조건에 맞는 작업이 없습니다.</p>}
    <div className="space-y-2">{jobs.map(job => <div key={job.id} className="flex flex-wrap items-center gap-3 rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
      {retryable(job) && <input type="checkbox" aria-label={`${job.content_id} 재시도 선택`} checked={selected.includes(job.id)} onChange={e => setSelected(e.target.checked ? [...selected, job.id] : selected.filter(id => id !== job.id))} />}
      <span className="font-mono">{job.content_id}</span><span>{job.kind === "reanalysis" ? "재분석" : "신규 분석"}</span>
      {!customer && <span className="text-xs text-slate-400">고객 {clients.find(client => client.id === job.client_id)?.name ?? job.client_id ?? "운영자"}</span>}
      <span className={retryable(job) ? "text-amber-400" : "text-indigo-300"}>{job.cancel_requested ? "취소 요청됨" : JOB_STATUS[job.status]}</span>
      <span>{toKSTDateTime(job.created_at)} · 시도 {job.attempts}회</span>
      {job.last_error && <span className="text-xs text-slate-400">{job.last_error === "LLMUnavailable" ? "분석 모델 응답을 확인하지 못했습니다." : "처리 오류가 발생했습니다."}</span>}
      {retryable(job) && <button disabled={busy} onClick={() => act(job, "retry")} className="text-indigo-300 disabled:opacity-40">재시도</button>}
      {["PENDING", "PROCESSING"].includes(job.status) && !job.cancel_requested && <button disabled={busy} onClick={() => act(job, "cancel")} className="text-amber-400 disabled:opacity-40">취소</button>}
      {job.content_record_id && <a className="text-emerald-400" href={`${customer ? "/my-dashboard" : "/history"}?search=${encodeURIComponent(job.content_id)}`}>결과 보기</a>}
    </div>)}</div>
    <div className="flex items-center gap-3 text-sm text-indigo-300"><button disabled={page === 0} onClick={() => { setPage(page - 1); setSelected([]) }} className="disabled:opacity-40">이전</button><span>{page + 1} / {Math.max(1, Math.ceil(total / 20))}페이지</span><button disabled={(page + 1) * 20 >= total} onClick={() => { setPage(page + 1); setSelected([]) }} className="disabled:opacity-40">다음</button></div>
  </div>
}
