"use client"
import { useEffect, useRef, useState } from "react"
import { ChevronDown, ChevronUp, RefreshCw, Search, X } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { api, type Content, type ModelPrediction, type RiskLevel } from "@/lib/api"
import { toKSTDateTime } from "@/lib/utils"
import { Pagination } from "@/components/ui/pagination"
import { ReviewDialog } from "@/components/review-dialog"
import { CategoryScoreBars } from "@/components/category-score-bars"
import { HighlightedText } from "@/components/highlighted-text"

const LEVEL_COUNT_COLOR: Record<RiskLevel, string> = {
  LOW: "text-emerald-400", MEDIUM: "text-yellow-400", HIGH: "text-orange-400", CRITICAL: "text-red-400",
}


function PredictionsRow({ contentId }: { contentId: string }) {
  const [preds, setPreds] = useState<ModelPrediction[] | null>(null)
  const [open, setOpen] = useState(false)

  const load = () => {
    if (preds) { setOpen(o => !o); return }
    api.getPredictions(contentId).then(p => { setPreds(p); setOpen(true) })
  }

  return (
    <div>
      <button onClick={load} className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors mt-2">
        모델별 예측 {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && preds && (
        <div className="mt-2 space-y-1">
          {preds.map(p => (
            <div key={p.id} className="flex items-center gap-3 text-xs text-slate-400 pl-1">
              <span className={p.is_selected ? "text-indigo-400 font-medium" : ""}>{p.model_name}</span>
              <span className="font-mono">{p.risk_score.toFixed(2)}</span>
              <Badge variant={p.risk_level as RiskLevel} className="text-[10px] py-0">{p.risk_level}</Badge>
              {p.confidence != null && <span>신뢰도 {(p.confidence * 100).toFixed(0)}%</span>}
              {p.latency_ms != null && <span>{p.latency_ms}ms</span>}
              {p.is_selected && <span className="text-indigo-400">✓ 선택</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const PAGE_SIZE_OPTIONS = [10, 30, 50, 100] as const
const REFRESH_INTERVAL = 30_000

export default function QueuePage() {
  const [items, setItems]       = useState<Content[]>([])
  const [sortBy, setSortBy]     = useState<"risk_score" | "created_at">("risk_score")
  const [levelFilter, setLevel] = useState<string>("")
  const [search, setSearch]     = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [loading, setLoading]   = useState(true)
  const [page, setPage]         = useState(0)
  const [total, setTotal]       = useState(0)
  const [pageSize, setPageSize] = useState(30)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshTick, setRefreshTick] = useState(0)

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const mounted = useRef(false)
  useEffect(() => {
    if (!mounted.current) { mounted.current = true; return }
    setPage(0)
  }, [debouncedSearch])

  const load = () => {
    setLoading(true)
    api.getContents({
      status: "PENDING",
      sort_by: sortBy,
      risk_level: levelFilter || undefined,
      search: debouncedSearch || undefined,
      limit: pageSize,
      offset: page * pageSize,
    })
      .then(({ items, total }) => { setItems(items); setTotal(total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, sortBy, levelFilter, pageSize, debouncedSearch, refreshTick])

  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => setRefreshTick(t => t + 1), REFRESH_INTERVAL)
    return () => clearInterval(id)
  }, [autoRefresh])

  const counts = (["CRITICAL", "HIGH", "MEDIUM", "LOW"] as RiskLevel[]).map(l => ({
    level: l, count: items.filter(c => c.risk_level === l).length,
  }))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">심사 큐</h1>
        <button
          onClick={() => setAutoRefresh(a => !a)}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
            autoRefresh ? "bg-slate-800 text-emerald-400" : "bg-slate-800 text-slate-500"
          }`}
        >
          <RefreshCw className={`h-3 w-3 ${autoRefresh && loading ? "animate-spin" : ""}`} />
          자동 새로고침
        </button>
      </div>

      {/* 긴급도 요약 */}
      <div className="flex items-center gap-6">
        <span className="text-slate-400 text-sm">대기 {items.length}건</span>
        {counts.map(({ level, count }) => (
          <span key={level} className={`text-sm font-semibold ${LEVEL_COUNT_COLOR[level]}`}>
            {level} {count}
          </span>
        ))}
      </div>

      {/* 검색 */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
        <Input
          placeholder="텍스트 또는 ID 검색..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="pl-9 pr-9"
        />
        {search && (
          <button
            onClick={() => setSearch("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* 컨트롤 */}
      <div className="flex items-center gap-3">
        {[
          { value: "risk_score", label: "위험도 높은 순" },
          { value: "created_at", label: "최신 순" },
        ].map(opt => (
          <button
            key={opt.value}
            onClick={() => { setSortBy(opt.value as typeof sortBy); setPage(0) }}
            className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
              sortBy === opt.value ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:text-slate-100"
            }`}
          >
            {opt.label}
          </button>
        ))}
        <div className="w-px h-5 bg-slate-700" />
        {(["", "CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map(l => (
          <button
            key={l}
            onClick={() => { setLevel(l); setPage(0) }}
            className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
              levelFilter === l ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:text-slate-100"
            }`}
          >
            {l || "전체"}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1">
          {PAGE_SIZE_OPTIONS.map(n => (
            <button
              key={n}
              onClick={() => { setPageSize(n); setPage(0) }}
              className={`px-2.5 py-1.5 rounded-md text-sm transition-colors ${
                pageSize === n ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:text-slate-100"
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {/* 목록 */}
      {loading ? (
        <p className="text-slate-500">불러오는 중...</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-12 text-center text-slate-400">
          {debouncedSearch ? `"${debouncedSearch}" 검색 결과가 없습니다.` : "심사 대기 중인 콘텐츠가 없습니다."}
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => (
            <Card key={item.content_id}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={item.risk_level}>{item.risk_level}</Badge>
                      <span className="text-xs text-slate-500 font-mono">{item.content_id}</span>
                      <span className="text-xs text-slate-500">{toKSTDateTime(item.created_at)}</span>
                    </div>
                    {/* 텍스트: evidence_spans 있으면 하이라이트, 없으면 일반 출력 */}
                    {item.evidence_spans && item.evidence_spans.length > 0 ? (
                      <HighlightedText text={item.text} spans={item.evidence_spans} />
                    ) : (
                      <p className="text-sm text-slate-200">{item.text}</p>
                    )}

                    {/* 카테고리별 위험 점수 막대 */}
                    {item.category_scores && (
                      <div className="pt-1">
                        <CategoryScoreBars scores={item.category_scores} />
                      </div>
                    )}

                    {/* HIGH/CRITICAL 심층 분석 */}
                    {item.explanation_json?.deep_analysis && (
                      <div className="rounded-md bg-red-950/30 border border-red-800/40 p-3 space-y-1.5">
                        <p className="text-red-400 text-xs font-medium">심층 위험 분석</p>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs">
                          <span className="text-slate-500">특정 대상 위협</span>
                          <span className={item.explanation_json.deep_analysis.is_targeted ? "text-red-400" : "text-slate-400"}>
                            {item.explanation_json.deep_analysis.is_targeted ? "예" : "아니오"}
                          </span>
                          <span className="text-slate-500">즉각적 위험</span>
                          <span className={item.explanation_json.deep_analysis.is_immediate ? "text-red-400" : "text-slate-400"}>
                            {item.explanation_json.deep_analysis.is_immediate ? "예" : "아니오"}
                          </span>
                          <span className="text-slate-500">실행 가능성</span>
                          <span className={
                            item.explanation_json.deep_analysis.actionability === "high" ? "text-red-400" :
                            item.explanation_json.deep_analysis.actionability === "medium" ? "text-yellow-400" : "text-slate-400"
                          }>
                            {item.explanation_json.deep_analysis.actionability}
                          </span>
                          <span className="text-slate-500">위협 대상</span>
                          <span className="text-slate-300">{item.explanation_json.deep_analysis.target_description}</span>
                        </div>
                        <p className="text-xs text-red-300/80 border-t border-red-800/30 pt-1.5">
                          권장 조치: {item.explanation_json.deep_analysis.suggested_action}
                        </p>
                      </div>
                    )}

                    {item.explanation && (
                      <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">{item.explanation}</p>
                    )}
                    <PredictionsRow contentId={item.content_id} />
                  </div>

                  <div className="flex flex-col items-end gap-3 shrink-0">
                    <p className="text-2xl font-bold text-slate-100">{item.risk_score.toFixed(2)}</p>
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button size="sm">심사하기</Button>
                      </DialogTrigger>
                      <ReviewDialog
                        content={item}
                        onDone={() => {
                          if (items.length <= 1 && page > 0) setPage(p => p - 1)
                          else load()
                        }}
                      />
                    </Dialog>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  )
}
