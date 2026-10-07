"use client"
import { useCallback, useEffect, useRef, useState } from "react"
import { api, type BatchImport, type BatchPreview } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { toKSTDateTime } from "@/lib/utils"
import { getRole } from "@/lib/auth"
import { JOB_STATUS } from "@/components/jobs-panel"

export function BatchUploader() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<BatchPreview | null>(null)
  const [idColumn, setIdColumn] = useState("")
  const [textColumn, setTextColumn] = useState("")
  const [batches, setBatches] = useState<BatchImport[]>([])
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [jobsPath, setJobsPath] = useState("/jobs")
  const sequence = useRef(0)
  useEffect(() => { setJobsPath(getRole() === "client" ? "/my-jobs" : "/jobs") }, [])
  const load = useCallback(async () => {
    const request = ++sequence.current
    try { const result = await api.getBatches(page * 20); if (request === sequence.current) { setBatches(result.items); setTotal(result.total) } }
    catch { if (request === sequence.current) setMessage("접수 내역을 불러오지 못했습니다.") }
  }, [page])
  useEffect(() => { load(); const timer = setInterval(load, 5000); return () => { clearInterval(timer); sequence.current++ } }, [load])
  const inspect = async () => {
    if (!file) return
    setBusy(true)
    try {
      const result = await api.previewBatch(file)
      setPreview(result)
      setIdColumn(result.columns.find(column => /^(content_?id|id)$/i.test(column)) ?? result.columns[0] ?? "")
      setTextColumn(result.columns.find(column => /^(text|content|body)$/i.test(column)) ?? result.columns[1] ?? "")
      setMessage("")
    } catch (error) { setMessage(error instanceof Error ? error.message : "파일 미리보기 실패") }
    finally { setBusy(false) }
  }
  const submit = async () => {
    if (!file) return
    setBusy(true)
    try {
      const result = await api.submitBatch(file, idColumn, textColumn)
      setMessage(`${result.accepted}건 접수, ${result.skipped}건 건너뜀. ${result.errors.slice(0, 5).map(item => `${item.row}행: ${item.reason}`).join(" ")}`)
      setPreview(null)
      setFile(null)
      setPage(0)
      await load()
    } catch (error) { setMessage(error instanceof Error ? error.message : "접수 실패") }
    finally { setBusy(false) }
  }
  return <div className="space-y-5">
    <h1 className="text-2xl font-bold text-slate-100">CSV·Excel 대량 분석</h1>
    <p className="text-sm text-slate-400">UTF-8 CSV 또는 XLSX를 선택하세요. 최대 2MB·500개 데이터 행·50열입니다. XLSX 압축 해제 크기는 20MB, 빈 행을 포함한 전체 행은 5,000개까지 허용합니다.</p>
    <div className="space-y-3 rounded border border-slate-700 bg-slate-800 p-4">
      <input aria-label="분석 파일" type="file" accept=".csv,.xlsx" disabled={busy} onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null) }} className="text-sm text-slate-200" />
      <Button onClick={inspect} disabled={!file || busy}>파일 미리보기</Button>
      {preview && <div className="space-y-2 text-sm text-slate-300">
        <p>{preview.format.toUpperCase()} · {preview.rows}행 · 열: {preview.columns.join(", ")}</p>
        <div className="flex flex-wrap gap-3">
          <label>콘텐츠 ID 열 <select aria-label="콘텐츠 ID 열" value={idColumn} onChange={e => setIdColumn(e.target.value)} className="rounded bg-slate-900 p-2">{preview.columns.map(column => <option key={column}>{column}</option>)}</select></label>
          <label>텍스트 열 <select aria-label="텍스트 열" value={textColumn} onChange={e => setTextColumn(e.target.value)} className="rounded bg-slate-900 p-2">{preview.columns.map(column => <option key={column}>{column}</option>)}</select></label>
        </div>
        <div className="max-h-36 overflow-auto rounded bg-slate-900 p-2 text-xs">{preview.sample.map((row, index) => <p key={index}>{Object.values(row).join(" | ")}</p>)}</div>
        <Button onClick={submit} disabled={busy || idColumn === textColumn || !idColumn || !textColumn}>분석 작업 접수</Button>
      </div>}
    </div>
    {message && <p role="status" className="text-sm text-slate-300">{message}</p>}
    <div className="space-y-2"><h2 className="text-lg font-semibold text-slate-100">접수 현황</h2>
      {batches.map(batch => <div key={batch.id} className="rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
        <p>{toKSTDateTime(batch.created_at)} · {batch.format.toUpperCase()} · 접수 {batch.accepted}/{batch.rows_total}건 · 제외 {batch.skipped}건</p>
        <p className="text-xs text-slate-400">{Object.entries(batch.by_status).map(([status, count]) => `${JOB_STATUS[status] ?? status} ${count}`).join(" · ") || "접수된 작업 없음"}</p>
        <div className="mt-2 flex gap-3 text-indigo-300"><a href={`${jobsPath}?batch_id=${batch.id}`}>배치 작업 보기</a>{batch.skipped > 0 && <button onClick={() => api.downloadBatchErrors(batch.id).catch(() => setMessage("오류 내역 다운로드에 실패했습니다."))}>제외된 행 오류 CSV</button>}</div>
      </div>)}
    </div>
    <div className="flex gap-3 text-sm text-indigo-300"><button disabled={page === 0} onClick={() => setPage(page - 1)} className="disabled:opacity-40">이전</button><span>{page + 1} / {Math.max(1, Math.ceil(total / 20))}페이지</span><button disabled={(page + 1) * 20 >= total} onClick={() => setPage(page + 1)} className="disabled:opacity-40">다음</button></div>
  </div>
}
