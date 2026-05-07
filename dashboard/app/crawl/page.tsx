"use client"
import { useRef, useState } from "react"
import { Loader2, CheckCircle, AlertCircle, StopCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { RiskLevel } from "@/lib/api"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

interface CrawlItem {
  content_id: string
  text: string
  risk_level: RiskLevel
  risk_score: number
}

interface DoneEvent {
  saved: number
  skipped: number
  errors: number
}

export default function CrawlPage() {
  const [url, setUrl]           = useState("")
  const [maxItems, setMaxItems] = useState(20)
  const [running, setRunning]   = useState(false)
  const [status, setStatus]     = useState("")
  const [items, setItems]       = useState<CrawlItem[]>([])
  const [done, setDone]         = useState<DoneEvent | null>(null)
  const [error, setError]       = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const start = async () => {
    if (!url.trim()) return
    setRunning(true); setItems([]); setDone(null); setError(null)
    setStatus("연결 중...")
    abortRef.current = new AbortController()

    try {
      const res = await fetch(`${BASE}/api/crawl`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), max_items: maxItems }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `${res.status}`)
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done: streamDone, value } = await reader.read()
        if (streamDone) break

        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split("\n\n")
        buffer = chunks.pop() ?? ""

        for (const chunk of chunks) {
          if (!chunk.startsWith("data: ")) continue
          const ev = JSON.parse(chunk.slice(6))

          if (ev.type === "status")    setStatus(ev.message)
          if (ev.type === "scraped")   setStatus(`스크래핑 완료 — ${ev.chars.toLocaleString()}자 수신`)
          if (ev.type === "extracted") setStatus(`${ev.count}개 텍스트 추출 완료 — 분석 중...`)
          if (ev.type === "item")      setItems(prev => [...prev, ev])
          if (ev.type === "error")     { setError(ev.message); return }
          if (ev.type === "done")      { setDone(ev); setStatus("") }
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name !== "AbortError")
        setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const stop = () => { abortRef.current?.abort(); setRunning(false); setStatus("") }

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-slate-100">실시간 크롤링 분석</h1>
      <p className="text-sm text-slate-400">
        URL을 입력하면 페이지의 댓글·리뷰를 자동으로 수집해 위험도를 분석합니다.
        분석 결과는 실시간으로 표시되고 대시보드에 저장됩니다.
      </p>

      {/* 입력 */}
      <div className="flex gap-2">
        <Input
          placeholder="https://..."
          value={url}
          onChange={e => setUrl(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !running && start()}
          disabled={running}
          className="flex-1"
        />
        <select
          value={maxItems}
          onChange={e => setMaxItems(Number(e.target.value))}
          disabled={running}
          className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-md px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          {[10, 20, 30, 50].map(n => <option key={n} value={n}>{n}건</option>)}
        </select>
        {running
          ? <Button variant="destructive" onClick={stop} className="gap-1.5"><StopCircle className="h-4 w-4" />중단</Button>
          : <Button onClick={start} disabled={!url.trim()}>분석 시작</Button>
        }
      </div>

      {/* 진행 상태 */}
      {(running || status) && !error && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          {running && <Loader2 className="h-4 w-4 animate-spin text-indigo-400 shrink-0" />}
          {status}
        </div>
      )}

      {/* 오류 */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 rounded-md bg-red-950/30 px-4 py-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* 실시간 결과 목록 */}
      {items.length > 0 && (
        <div className="rounded-lg border border-slate-700 bg-slate-800 overflow-hidden">
          <div className="px-4 py-2 border-b border-slate-700 flex items-center justify-between">
            <span className="text-xs text-slate-500">분석 결과</span>
            <span className="text-xs text-slate-500">{items.length}건</span>
          </div>
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-3 border-b border-slate-700 last:border-0 animate-in fade-in duration-300">
              <Badge variant={item.risk_level}>{item.risk_level}</Badge>
              <span className="font-mono text-xs text-slate-500 w-10 shrink-0">{item.risk_score.toFixed(2)}</span>
              <p className="flex-1 text-sm text-slate-300 truncate">{item.text}</p>
            </div>
          ))}
        </div>
      )}

      {/* 완료 요약 */}
      {done && (
        <div className="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-800 px-5 py-4">
          <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0" />
          <span className="text-slate-300 text-sm">
            분석 완료 —{" "}
            저장 <span className="text-emerald-400 font-semibold">{done.saved}건</span>
            {done.skipped > 0 && <> · 중복 <span className="text-slate-400">{done.skipped}건</span></>}
            {done.errors  > 0 && <> · 오류 <span className="text-red-400">{done.errors}건</span></>}
          </span>
        </div>
      )}
    </div>
  )
}
