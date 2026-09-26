"use client"
import { useEffect, useState } from "react"
import { api, type AnalysisJob } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { toKSTDateTime } from "@/lib/utils"

export default function JobsPage() {
  const [jobs, setJobs] = useState<AnalysisJob[]>([])
  const [contentId, setContentId] = useState("")
  const [body, setBody] = useState("")
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const load = () => api.listJobs().then(setJobs).catch(() => setMessage("작업 목록을 불러오지 못했습니다."))
  useEffect(() => { load(); const timer = setInterval(load, 5000); return () => clearInterval(timer) }, [])
  const submit = async () => {
    setBusy(true); setMessage("")
    try {
      const job = await api.submitJob(contentId, body)
      setMessage(`작업 ${job.id} 접수됨`)
      setBody("")
      await load()
    } catch (error) { setMessage(error instanceof Error ? error.message : "접수 실패") }
    finally { setBusy(false) }
  }
  const act = async (job: AnalysisJob, action: "retry" | "cancel") => {
    try { if (action === "retry") await api.retryJob(job.id); else await api.cancelJob(job.id); await load() }
    catch { setMessage("작업 상태를 변경하지 못했습니다. 새로고침 후 다시 시도해 주세요.") }
  }
  return <div className="space-y-5">
    <h1 className="text-2xl font-bold text-slate-100">분석 작업</h1>
    <p className="text-sm text-slate-400">긴 분석은 접수 후 별도 워커가 처리합니다. 재분석 작업도 이 목록에 나타납니다.</p>
    <div className="space-y-2 rounded border border-slate-700 bg-slate-800 p-4">
      <input aria-label="콘텐츠 ID" value={contentId} onChange={e => setContentId(e.target.value)} maxLength={200} placeholder="콘텐츠 ID" className="w-full rounded bg-slate-900 p-2 text-slate-100" />
      <textarea aria-label="분석할 텍스트" value={body} onChange={e => setBody(e.target.value)} maxLength={8000} placeholder="분석할 텍스트" className="w-full rounded bg-slate-900 p-2 text-slate-100" />
      <Button disabled={busy || !contentId.trim() || !body.trim()} onClick={submit}>분석 작업 접수</Button>
    </div>
    {message && <p role="status" className="text-sm text-slate-300">{message}</p>}
    <div className="space-y-2">{jobs.map(job => <div key={job.id} className="flex flex-wrap items-center gap-3 rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
      <span className="font-mono">{job.content_id}</span><span>{job.kind === "reanalysis" ? "재분석" : "신규 분석"}</span>
      <span className={job.status === "FAILED" ? "text-red-400" : "text-indigo-300"}>{job.status}</span>
      <span>{toKSTDateTime(job.created_at)}</span>
      {job.last_error && <span>오류: {job.last_error}</span>}
      {job.status === "FAILED" && <button onClick={() => act(job, "retry")} className="text-indigo-400">재시도</button>}
      {(job.status === "PENDING" || job.status === "PROCESSING") && <button onClick={() => act(job, "cancel")} className="text-amber-400">취소</button>}
      {job.status === "COMPLETED" && job.content_record_id && <a className="text-emerald-400" href={`/history?search=${encodeURIComponent(job.content_id)}`}>결과 보기</a>}
    </div>)}</div>
  </div>
}
