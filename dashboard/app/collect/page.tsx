"use client"
import { useCallback, useRef, useState } from "react"
import {
  Upload, FileText, X, CheckCircle, AlertCircle,
  Loader2, StopCircle, Code, Globe, Plug,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api, type RiskLevel, type UploadResult } from "@/lib/api"

const ADMIN_SECRET = process.env.NEXT_PUBLIC_ADMIN_SECRET ?? ""
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

type Tab = "api" | "file" | "crawl"

// ── 탭 버튼 ────────────────────────────────────────────────────────────────

function TabBar({ active, crawling, onChange }: {
  active: Tab
  crawling: boolean
  onChange: (t: Tab) => void
}) {
  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "api",   label: "API 연동",    icon: <Plug  className="h-4 w-4" /> },
    { id: "file",  label: "파일 업로드", icon: <Upload className="h-4 w-4" /> },
    { id: "crawl", label: "웹 크롤링",   icon: <Globe  className="h-4 w-4" /> },
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

// ── 파일 업로드 탭 ──────────────────────────────────────────────────────────

const SUPPORTED_EXTS = new Set([".csv", ".xlsx", ".xls", ".json", ".txt"])
const EXT_LABELS: Record<string, string> = {
  ".csv": "CSV", ".xlsx": "Excel", ".xls": "Excel", ".json": "JSON", ".txt": "텍스트",
}

function getExt(filename: string): string {
  const idx = filename.lastIndexOf(".")
  return idx >= 0 ? filename.slice(idx).toLowerCase() : ""
}

interface PreviewRow { content_id: string; text: string }

function parseCsvLine(line: string): string[] {
  const result: string[] = []; let cur = ""; let inQ = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') { if (inQ && line[i + 1] === '"') { cur += '"'; i++ } else inQ = !inQ }
    else if (ch === ',' && !inQ) { result.push(cur); cur = "" }
    else cur += ch
  }
  result.push(cur); return result
}

function parseCsvPreview(text: string): { rows: PreviewRow[]; error: string | null } {
  const lines = text.split(/\r?\n/).filter(Boolean)
  if (lines.length < 2) return { rows: [], error: null }
  const headers = parseCsvLine(lines[0]).map(h => h.trim())
  const cidIdx = headers.indexOf("content_id"), txtIdx = headers.indexOf("text")
  if (txtIdx === -1)
    return { rows: [], error: "'text' 컬럼이 없습니다." }
  const prefix = `CSV_${Date.now()}`
  return {
    rows: lines.slice(1).map((line, i) => {
      const cols = parseCsvLine(line)
      const content_id = cidIdx !== -1 ? (cols[cidIdx] ?? "").trim() : `${prefix}_${String(i + 1).padStart(4, "0")}`
      return { content_id, text: (cols[txtIdx] ?? "").trim() }
    }),
    error: null,
  }
}

function FileTab() {
  const [file, setFile]             = useState<File | null>(null)
  const [fileExt, setFileExt]       = useState("")
  const [preview, setPreview]       = useState<PreviewRow[]>([])
  const [parseError, setParseError] = useState<string | null>(null)
  const [uploading, setUploading]   = useState(false)
  const [result, setResult]         = useState<UploadResult | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (f: File) => {
    const ext = getExt(f.name)
    if (!SUPPORTED_EXTS.has(ext)) return
    setFile(f); setFileExt(ext); setResult(null); setUploadError(null); setPreview([]); setParseError(null)
    if (ext === ".csv") {
      const reader = new FileReader()
      reader.onload = e => {
        const { rows, error } = parseCsvPreview(e.target?.result as string)
        setPreview(rows); setParseError(error)
      }
      reader.readAsText(f, "utf-8")
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [])

  const reset = () => {
    setFile(null); setFileExt(""); setPreview([]); setParseError(null)
    setResult(null); setUploadError(null)
  }

  const upload = async () => {
    if (!file) return
    setUploading(true); setUploadError(null)
    try { setResult(await api.uploadFile(file)) }
    catch (e: unknown) { setUploadError(e instanceof Error ? e.message : String(e)) }
    finally { setUploading(false) }
  }

  const isCsv = fileExt === ".csv"
  const canUpload = !!file && !parseError && !uploading

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-slate-100">파일 일괄 업로드</h2>
        <p className="text-sm text-slate-400">
          CSV · Excel · JSON · TXT 형식을 지원합니다. 최대 1,000건.{" "}
          CSV / Excel / JSON은{" "}
          <code className="bg-slate-800 px-1 rounded text-slate-300">content_id</code>,{" "}
          <code className="bg-slate-800 px-1 rounded text-slate-300">text</code>{" "}
          컬럼(키)이 필요하며, TXT는 줄 단위로 자동 분리됩니다.
        </p>
      </div>

      {!file && (
        <div
          onDrop={handleDrop} onDragOver={e => e.preventDefault()}
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center gap-3 rounded-lg border-2 border-dashed border-slate-600 bg-slate-800/40 p-12 cursor-pointer hover:border-indigo-500 hover:bg-slate-800/60 transition-colors"
        >
          <Upload className="h-8 w-8 text-slate-500" />
          <p className="text-slate-400 text-sm">클릭하거나 파일을 드래그하세요</p>
          <p className="text-xs text-slate-600">.csv · .xlsx · .xls · .json · .txt</p>
          <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls,.json,.txt" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
        </div>
      )}

      {file && !result && (
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-300">
              <FileText className="h-4 w-4 text-indigo-400" />
              <span className="text-sm font-medium">{file.name}</span>
              {isCsv && preview.length > 0 && <span className="text-xs text-slate-500">{preview.length}건</span>}
              <span className="text-xs bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded font-mono">
                {EXT_LABELS[fileExt] ?? fileExt}
              </span>
            </div>
            <button onClick={reset} className="text-slate-500 hover:text-slate-300"><X className="h-4 w-4" /></button>
          </div>

          {parseError && <p className="text-xs text-red-400 flex items-center gap-1"><AlertCircle className="h-3.5 w-3.5" />{parseError}</p>}

          {isCsv && preview.length > 0 && (
            <div className="overflow-x-auto rounded-md border border-slate-700">
              <table className="w-full text-xs">
                <thead><tr className="bg-slate-900 border-b border-slate-700">
                  <th className="text-left px-3 py-2 text-slate-500 font-medium w-32">content_id</th>
                  <th className="text-left px-3 py-2 text-slate-500 font-medium">text</th>
                </tr></thead>
                <tbody>
                  {preview.slice(0, 5).map((row, i) => (
                    <tr key={i} className="border-b border-slate-700/50 last:border-0">
                      <td className="px-3 py-2 font-mono text-slate-400">{row.content_id}</td>
                      <td className="px-3 py-2 text-slate-300 truncate max-w-xs">{row.text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {preview.length > 5 && <p className="text-xs text-slate-500 px-3 py-2 border-t border-slate-700">... 외 {preview.length - 5}건</p>}
            </div>
          )}

          {!isCsv && (
            <p className="text-xs text-slate-500">서버에서 파일을 파싱합니다. 업로드 후 결과를 확인하세요.</p>
          )}

          {uploadError && <p className="text-xs text-red-400 flex items-center gap-1"><AlertCircle className="h-3.5 w-3.5" />{uploadError}</p>}

          <div className="flex gap-2">
            <Button onClick={upload} disabled={!canUpload}>
              {uploading ? "분석 중..." : isCsv && preview.length > 0 ? `${preview.length}건 분석 시작` : "분석 시작"}
            </Button>
            <Button variant="ghost" onClick={reset} disabled={uploading}>취소</Button>
          </div>
        </div>
      )}

      {result && (
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-6 space-y-5">
          <div className="flex items-center gap-2"><CheckCircle className="h-5 w-5 text-emerald-400" /><span className="text-slate-100 font-medium">업로드 완료</span></div>
          <div className="grid grid-cols-3 gap-3">
            {[{ label: "전체", value: result.total, color: "text-slate-100" },
              { label: "저장됨", value: result.saved, color: "text-emerald-400" },
              { label: "중복 건너뜀", value: result.skipped, color: "text-slate-400" }]
              .map(({ label, value, color }) => (
                <div key={label} className="rounded-md bg-slate-900 p-4 text-center">
                  <p className={`text-2xl font-bold ${color}`}>{value}</p>
                  <p className="text-xs text-slate-500 mt-1">{label}</p>
                </div>
              ))}
          </div>
          {result.errors.length > 0 && (
            <div className="rounded-md bg-slate-900 p-3 space-y-1.5">
              <div className="flex items-center gap-1.5 text-amber-400 text-xs font-medium"><AlertCircle className="h-3.5 w-3.5" />오류 {result.errors.length}건</div>
              {result.errors.slice(0, 5).map((e, i) => (
                <p key={i} className="text-xs text-slate-400 pl-5">Row {e.row} · <span className="font-mono">{e.content_id || "(없음)"}</span> · {e.reason}</p>
              ))}
            </div>
          )}
          <Button variant="ghost" onClick={reset} className="text-sm">다른 파일 업로드</Button>
        </div>
      )}
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
      const res = await fetch("/api/crawl", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Secret": ADMIN_SECRET },
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
  const [tab, setTab]         = useState<Tab>("api")
  const [crawling, setCrawling] = useState(false)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">데이터 수집</h1>

      <TabBar active={tab} crawling={crawling} onChange={setTab} />

      <div className={tab !== "api"   ? "hidden" : ""}><ApiTab /></div>
      <div className={tab !== "file"  ? "hidden" : ""}><FileTab /></div>
      <div className={tab !== "crawl" ? "hidden" : ""}><CrawlTab onCrawlingChange={setCrawling} /></div>
    </div>
  )
}
