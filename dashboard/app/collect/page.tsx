"use client"
import { useRef, useState } from "react"
import {
  CheckCircle, AlertCircle,
  Loader2, StopCircle, Code, Globe, Plug,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { type RiskLevel } from "@/lib/api"
import { getToken } from "@/lib/auth"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

type Tab = "api" | "crawl"

// ── 탭 버튼 ────────────────────────────────────────────────────────────────

function TabBar({ active, crawling, onChange }: {
  active: Tab
  crawling: boolean
  onChange: (t: Tab) => void
}) {
  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "api",   label: "API 연동",  icon: <Plug  className="h-4 w-4" /> },
    { id: "crawl", label: "웹 크롤링", icon: <Globe className="h-4 w-4" /> },
  ]
  return (
    <div className="flex gap-1 border-b border-slate-700 pb-0">
      {tabs.map(t => (
        <button
          key={t.id}
          disabled={crawling && t.id !== "crawl"}
          onClick={() => onChange(t.id)}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px
            ${active === t.id
              ? "border-indigo-500 text-indigo-400"
              : crawling && t.id !== "crawl"
                ? "border-transparent text-slate-600 cursor-not-allowed"
                : "border-transparent text-slate-400 hover:text-slate-100 hover:border-slate-500"
            }`}
        >
          {t.icon}{t.label}
          {crawling && t.id === "crawl" && active !== "crawl" && (
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
          )}
        </button>
      ))}
      {crawling && (
        <span className="ml-auto flex items-center gap-1.5 text-xs text-indigo-400 self-center pr-1">
          <Loader2 className="h-3 w-3 animate-spin" />크롤링 진행 중
        </span>
      )}
    </div>
  )
}

// ── API 연동 탭 ─────────────────────────────────────────────────────────────

function ApiTab() {
  const [lang, setLang] = useState<"curl" | "python" | "js">("curl")

  const examples: Record<typeof lang, string> = {
    curl: `curl -X POST ${BASE}/api/analyze \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer cg-your-api-key" \\
  -d '{
    "content_id": "review-001",
    "text": "분석할 텍스트 내용"
  }'`,
    python: `import requests

response = requests.post(
    "${BASE}/api/analyze",
    headers={"Authorization": "Bearer cg-your-api-key"},
    json={
        "content_id": "review-001",
        "text": "분석할 텍스트 내용",
    },
)
result = response.json()
print(result["risk_level"], result["risk_score"])`,
    js: `const response = await fetch("${BASE}/api/analyze", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer cg-your-api-key",
  },
  body: JSON.stringify({
    content_id: "review-001",
    text: "분석할 텍스트 내용",
  }),
});
const result = await response.json();
console.log(result.risk_level, result.risk_score);`,
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-slate-100">API 자동 연동</h2>
        <p className="text-sm text-slate-400">
          서비스에서 새 콘텐츠가 등록될 때 API를 호출하면 자동으로 분석됩니다.
        </p>
      </div>

      {/* 엔드포인트 */}
      <div className="rounded-md border border-slate-700 bg-slate-900 p-4 space-y-3">
        <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">엔드포인트</p>
        <div className="flex items-center gap-2">
          <span className="bg-indigo-600/20 text-indigo-400 text-xs font-mono px-2 py-0.5 rounded">POST</span>
          <code className="text-sm text-slate-200 font-mono">{BASE}/api/analyze</code>
        </div>
        <div className="text-xs text-slate-500 space-y-1">
          <div><span className="text-slate-400">Authorization</span>: Bearer cg-your-api-key</div>
          <div><span className="text-slate-400">content_id</span>: 콘텐츠 고유 식별자</div>
          <div><span className="text-slate-400">text</span>: 분석할 텍스트</div>
        </div>
      </div>

      {/* 코드 예시 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide flex items-center gap-1.5">
            <Code className="h-3.5 w-3.5" />예시 코드
          </p>
          <div className="flex gap-1">
            {(["curl", "python", "js"] as const).map(l => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`px-2.5 py-1 rounded text-xs transition-colors ${
                  lang === l ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:text-slate-100"
                }`}
              >
                {l === "js" ? "JavaScript" : l.charAt(0).toUpperCase() + l.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <pre className="rounded-md bg-slate-900 border border-slate-700 p-4 text-xs text-slate-300 font-mono overflow-x-auto leading-relaxed">
          {examples[lang]}
        </pre>
      </div>

      {/* API 키 관리 링크 */}
      <div className="rounded-md border border-slate-700 bg-slate-800 px-4 py-3 flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-200 font-medium">API 키가 필요하신가요?</p>
          <p className="text-xs text-slate-500 mt-0.5">어드민 페이지에서 클라이언트 등록 후 키를 발급하세요.</p>
        </div>
        <a href="/admin">
          <Button size="sm" variant="ghost" className="text-indigo-400 hover:text-indigo-300">
            키 관리 →
          </Button>
        </a>
      </div>
    </div>
  )
}

// ── 웹 크롤링 탭 ────────────────────────────────────────────────────────────

interface CrawlItem { content_id: string; text: string; risk_level: RiskLevel; risk_score: number }
interface DoneEvent { saved: number; skipped: number; errors: number }

function CrawlTab({ onCrawlingChange }: { onCrawlingChange: (v: boolean) => void }) {
  const [url, setUrl]           = useState("")
  const [maxItems, setMaxItems] = useState(20)
  const [running, setRunning]   = useState(false)
  const [status, setStatus]     = useState("")
  const [items, setItems]       = useState<CrawlItem[]>([])
  const [done, setDone]         = useState<DoneEvent | null>(null)
  const [error, setError]       = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const setRunningState = (v: boolean) => { setRunning(v); onCrawlingChange(v) }

  const start = async () => {
    if (!url.trim()) return
    setRunningState(true); setItems([]); setDone(null); setError(null); setStatus("연결 중...")
    abortRef.current = new AbortController()
    try {
      const token = getToken()
      const res = await fetch("/api/crawl", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ url: url.trim(), max_items: maxItems }),
        signal: abortRef.current.signal,
      })
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail ?? `${res.status}`) }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      while (true) {
        const { done: sd, value } = await reader.read()
        if (sd) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split("\n\n"); buffer = chunks.pop() ?? ""
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
      if ((e as Error).name !== "AbortError") setError(e instanceof Error ? e.message : String(e))
    } finally { setRunningState(false) }
  }

  const stop = () => { abortRef.current?.abort(); setRunningState(false); setStatus("") }

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-slate-100">웹 크롤링 분석</h2>
        <p className="text-sm text-slate-400">URL을 입력하면 페이지의 댓글·리뷰를 수집해 위험도를 실시간 분석합니다.</p>
      </div>

      <div className="flex gap-2">
        <Input placeholder="https://..." value={url} onChange={e => setUrl(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !running && start()} disabled={running} className="flex-1" />
        <select value={maxItems} onChange={e => setMaxItems(Number(e.target.value))} disabled={running}
          className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-md px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500">
          {[10, 20, 30, 50].map(n => <option key={n} value={n}>{n}건</option>)}
        </select>
        {running
          ? <Button variant="destructive" onClick={stop} className="gap-1.5"><StopCircle className="h-4 w-4" />중단</Button>
          : <Button onClick={start} disabled={!url.trim()}>분석 시작</Button>}
      </div>

      {(running || status) && !error && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          {running && <Loader2 className="h-4 w-4 animate-spin text-indigo-400 shrink-0" />}
          {status}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 rounded-md bg-red-950/30 px-4 py-3">
          <AlertCircle className="h-4 w-4 shrink-0" />{error}
        </div>
      )}

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

      {done && (
        <div className="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-800 px-5 py-4">
          <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0" />
          <span className="text-slate-300 text-sm">
            분석 완료 — 저장 <span className="text-emerald-400 font-semibold">{done.saved}건</span>
            {done.skipped > 0 && <> · 중복 <span className="text-slate-400">{done.skipped}건</span></>}
            {done.errors  > 0 && <> · 오류 <span className="text-red-400">{done.errors}건</span></>}
          </span>
        </div>
      )}
    </div>
  )
}

// ── 메인 페이지 ────────────────────────────────────────────────────────────

export default function CollectPage() {
  const [tab, setTab]           = useState<Tab>("api")
  const [crawling, setCrawling] = useState(false)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">데이터 수집</h1>

      <TabBar active={tab} crawling={crawling} onChange={setTab} />

      <div className={tab !== "api"   ? "hidden" : ""}><ApiTab /></div>
      <div className={tab !== "crawl" ? "hidden" : ""}><CrawlTab onCrawlingChange={setCrawling} /></div>
    </div>
  )
}
