"use client"
import { useEffect, useRef, useState } from "react"
import { ChevronDown, ChevronUp, Loader2, RefreshCw, Search, Trash2, X } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { api, type Content, type ModelPrediction, type ReviewAction, type RiskLevel } from "@/lib/api"
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

const BULK_ACTIONS: { action: ReviewAction; label: string; className: string }[] = [
  { action: "approve", label: "승인",       className: "bg-emerald-700 hover:bg-emerald-600 text-white" },
  { action: "hold",    label: "보류",       className: "bg-amber-700 hover:bg-amber-600 text-white" },
  { action: "monitor", label: "모니터링",   className: "bg-blue-700 hover:bg-blue-600 text-white" },
  { action: "remove",  label: "삭제",       className: "bg-red-700 hover:bg-red-600 text-white" },
]

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
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const allSelected = items.length > 0 && items.every(i => selected.has(i.content_id))
  const someSelected = selected.size > 0

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

  // 페이지/필터 변경 시 선택 초기화
  useEffect(() => { setSelected(new Set()) }, [page, sortBy, levelFilter, pageSize, debouncedSearch])

  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => setRefreshTick(t => t + 1), REFRESH_INTERVAL)
    return () => clearInterval(id)
  }, [autoRefresh])

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    setSelected(allSelected ? new Set() : new Set(items.map(i => i.content_id)))
  }

  const bulkReview = async (action: ReviewAction) => {
    if (!confirm(`선택한 ${selected.size}건을 일괄 처리하시겠습니까?`)) return
    setBulkLoading(true)
    try {
      await Promise.all([...selected].map(id => api.review(id, action)))
      setSelected(new Set())
      if (items.length <= selected.size && page > 0) setPage(p => p - 1)
      else load()
    } finally {
      setBulkLoading(false)
    }
  }

  const counts = (["CRITICAL", "HIGH", "MEDIUM", "LOW"] as RiskLevel[]).map(l => ({
    level: l, count: items.filter(c => c.risk_level === l).length,
  }))

  return (
    <div className="space-y-6 pb-24">
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
        {/* 전체 선택 */}
        <label className="flex items-center gap-1.5 cursor-pointer select-none text-sm text-slate-400 hover:text-slate-200 transition-colors">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={toggleSelectAll}
            className="w-4 h-4 rounded accent-indigo-500 cursor-pointer"
          />
          전체
        </label>
        <div className="w-px h-5 bg-slate-700" />
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
          {items.map(item => {
            const isSelected = selected.has(item.content_id)
            return (
              <Card key={item.content_id} className={isSelected ? "ring-1 ring-indigo-500" : ""}>
                <CardContent className="p-5">
                  <div className="flex items-start gap-3">
                    {/* 체크박스 */}
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(item.content_id)}
                      className="mt-1 w-4 h-4 rounded accent-indigo-500 cursor-pointer shrink-0"
                    />

                    <div className="flex flex-1 items-start justify-between gap-4 min-w-0">
                      <div className="flex-1 min-w-0 space-y-2">
                        <div className="flex items-center gap-2">
                          <Badge variant={item.risk_level}>{item.risk_level}</Badge>
                          <span className="text-xs text-slate-500 font-mono">{item.content_id}</span>
                          <span className="text-xs text-slate-500">{toKSTDateTime(item.created_at)}</span>
                        </div>
                        {item.evidence_spans && item.evidence_spans.length > 0 ? (
                          <HighlightedText text={item.text} spans={item.evidence_spans} />
                        ) : (
                          <p className="text-sm text-slate-200">{item.text}</p>
                        )}
                        {item.category_scores && (
                          <div className="pt-1">
                            <CategoryScoreBars scores={item.category_scores} />
                          </div>
                        )}
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
                        {item.explanation_json ? (
                          <div className="rounded-md bg-slate-900 p-3 text-xs text-slate-400 space-y-2">
                            <p className="text-slate-400 font-medium">{item.explanation_json.summary}</p>
                            {item.explanation_json.score_explanation && (
                              <p className="text-slate-500 leading-relaxed">{item.explanation_json.score_explanation}</p>
                            )}
                            {item.explanation_json.main_reasons.length > 0 && (
                              <ul className="list-disc list-inside space-y-0.5 text-slate-500">
                                {item.explanation_json.main_reasons.map((r, i) => <li key={i}>{r}</li>)}
                              </ul>
                            )}
                            {item.explanation_json.evidence.length > 0 && (
                              <div className="space-y-1 border-t border-slate-800 pt-2">
                                {item.explanation_json.evidence.map((ev, i) => (
                                  <div key={i} className="flex gap-2">
                                    <span className="text-slate-600 shrink-0">•</span>
                                    <span>
                                      <span className="font-mono text-slate-300">"{ev.quote}"</span>
                                      <span className="text-slate-500"> — {ev.why_it_matters}</span>
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                            <p className="text-slate-600 border-t border-slate-800 pt-2">
                              {item.explanation_json.recommended_operator_check}
                            </p>
                          </div>
                        ) : item.explanation ? (
                          <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">{item.explanation}</p>
                        ) : null}
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
                        <button
                          onClick={async () => {
                            if (!confirm(`'${item.content_id}' 를 삭제하시겠습니까?`)) return
                            await api.deleteContent(item.content_id)
                            if (items.length <= 1 && page > 0) setPage(p => p - 1)
                            else load()
                          }}
                          className="text-slate-500 hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />

      {/* 일괄 처리 바 */}
      {someSelected && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 rounded-xl border border-slate-600 bg-slate-800 px-5 py-3 shadow-2xl">
          <span className="text-sm text-slate-300 font-medium shrink-0">
            {selected.size}건 선택됨
          </span>
          <div className="w-px h-5 bg-slate-600" />
          {BULK_ACTIONS.map(({ action, label, className }) => (
            <button
              key={action}
              onClick={() => bulkReview(action)}
              disabled={bulkLoading}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors disabled:opacity-50 ${className}`}
            >
              {label}
            </button>
          ))}
          <div className="w-px h-5 bg-slate-600" />
          <button
            onClick={() => setSelected(new Set())}
            disabled={bulkLoading}
            className="text-slate-400 hover:text-slate-200 transition-colors disabled:opacity-50"
          >
            {bulkLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
          </button>
        </div>
      )}
    </div>
  )
}
