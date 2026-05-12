"use client"
import { useEffect, useRef, useState } from "react"
import { ChevronDown, ChevronUp, Search, Trash2, X } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogTrigger } from "@/components/ui/dialog"
import { api, type Content, type ReviewStatus } from "@/lib/api"
import { toKSTDate } from "@/lib/utils"
import { Pagination } from "@/components/ui/pagination"
import { ReviewDialog } from "@/components/review-dialog"
import { CategoryScoreBars } from "@/components/category-score-bars"
import { HighlightedText } from "@/components/highlighted-text"

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "전체" },
  { value: "PENDING",   label: "대기" },
  { value: "APPROVED",  label: "승인" },
  { value: "REMOVED",   label: "삭제" },
  { value: "HELD",      label: "보류" },
  { value: "MONITORED", label: "모니터링" },
]

function ExpandRow({ item, onReload }: { item: Content; onReload: () => void }) {
  const [open, setOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`'${item.content_id}' 를 삭제하시겠습니까?`)) return
    setDeleting(true)
    try {
      await api.deleteContent(item.content_id)
      onReload()
    } catch {
      setDeleting(false)
    }
  }

  return (
    <div className="border-b border-slate-700 last:border-0">
      <div
        className="flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-slate-700/30 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <Badge variant={item.risk_level}>{item.risk_level}</Badge>
        <span className="text-xs font-mono text-slate-500">{item.content_id}</span>
        <p className="flex-1 text-sm text-slate-300 truncate">{item.text}</p>
        <span className="font-mono text-sm text-slate-400">{item.risk_score.toFixed(2)}</span>
        <Badge variant={item.review_status as ReviewStatus}>{item.review_status}</Badge>
        <span className="text-xs text-slate-600">{toKSTDate(item.created_at)}</span>
        <Dialog>
          <DialogTrigger asChild onClick={e => e.stopPropagation()}>
            <Button size="sm" variant="ghost" className="text-xs text-slate-400 hover:text-slate-100 h-7 px-2">
              재변경
            </Button>
          </DialogTrigger>
          <ReviewDialog content={item} onDone={onReload} />
        </Dialog>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="text-slate-500 hover:text-red-400 transition-colors disabled:opacity-40"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
        {open ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
      </div>
      {open && (
        <div className="px-4 pb-4 space-y-3">
          {/* 전문 + evidence 하이라이트 */}
          <div className="rounded-md bg-slate-900 p-3">
            <p className="text-slate-500 text-xs font-medium mb-1.5">원문</p>
            {item.evidence_spans && item.evidence_spans.length > 0 ? (
              <HighlightedText text={item.text} spans={item.evidence_spans} />
            ) : (
              <p className="text-sm text-slate-200">{item.text}</p>
            )}
          </div>

          {/* 카테고리 점수 */}
          {item.category_scores && (
            <div className="rounded-md bg-slate-900 p-3">
              <p className="text-slate-500 text-xs font-medium mb-2">카테고리별 위험 점수</p>
              <CategoryScoreBars scores={item.category_scores} />
            </div>
          )}

          {/* 강제 승격 규칙 */}
          {item.triggered_rules && item.triggered_rules.length > 0 && (
            <div className="rounded-md bg-amber-950/40 border border-amber-800/40 p-3">
              <p className="text-amber-400 text-xs font-medium mb-1.5">강제 승격 규칙 적용됨</p>
              <div className="space-y-1">
                {item.triggered_rules.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-amber-300/80">
                    <span className="font-mono bg-amber-900/40 px-1 rounded">{r.rule_id}</span>
                    <span>{r.description}</span>
                    <span className="ml-auto text-amber-500">최소 {r.min_grade}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI 설명 */}
          {item.explanation_json ? (
            <div className="rounded-md bg-slate-900 p-3 text-xs text-slate-400 space-y-2">
              <p className="text-slate-400 font-medium">{item.explanation_json.summary}</p>
              {item.explanation_json.main_reasons.length > 0 && (
                <ul className="list-disc list-inside space-y-0.5 text-slate-500">
                  {item.explanation_json.main_reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
              <p className="text-slate-600 border-t border-slate-800 pt-2">
                {item.explanation_json.recommended_operator_check}
              </p>
            </div>
          ) : item.explanation ? (
            <div className="rounded-md bg-slate-900 p-3 text-xs text-slate-400 leading-relaxed">
              <p className="text-slate-500 mb-1 font-medium">AI 설명</p>
              {item.explanation}
            </div>
          ) : null}

          {item.reviewer_comment && (
            <div className="rounded-md bg-slate-900 p-3 text-xs text-slate-400">
              <p className="text-slate-500 mb-1 font-medium">운영자 메모</p>
              {item.reviewer_comment}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const PAGE_SIZE_OPTIONS = [10, 30, 50, 100] as const

export default function HistoryPage() {
  const [items, setItems]       = useState<Content[]>([])
  const [status, setStatus]     = useState("")
  const [search, setSearch]     = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [loading, setLoading]   = useState(true)
  const [page, setPage]         = useState(0)
  const [total, setTotal]       = useState(0)
  const [pageSize, setPageSize] = useState(30)

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  // 300ms 디바운스
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  // 검색어 변경 시 1페이지로 리셋 (초기 마운트 제외)
  const mounted = useRef(false)
  useEffect(() => {
    if (!mounted.current) { mounted.current = true; return }
    setPage(0)
  }, [debouncedSearch])

  const load = () => {
    setLoading(true)
    api.getContents({
      status: status || undefined,
      search: debouncedSearch || undefined,
      limit: pageSize,
      offset: page * pageSize,
    })
      .then(({ items, total }) => { setItems(items); setTotal(total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [status, page, pageSize, debouncedSearch])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">전체 이력</h1>

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

      {/* 상태 필터 */}
      <div className="flex items-center gap-2">
        {STATUS_OPTIONS.map(opt => (
          <button
            key={opt.value}
            onClick={() => { setStatus(opt.value); setPage(0) }}
            className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
              status === opt.value
                ? "bg-indigo-600 text-white"
                : "bg-slate-800 text-slate-400 hover:text-slate-100"
            }`}
          >
            {opt.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-1">
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
          <span className="text-sm text-slate-500">총 {total}건</span>
        </div>
      </div>

      {/* 테이블 */}
      <div className="rounded-lg border border-slate-700 bg-slate-800 overflow-hidden">
        {loading ? (
          <p className="p-6 text-slate-500 text-sm">불러오는 중...</p>
        ) : items.length === 0 ? (
          <p className="p-6 text-slate-500 text-sm text-center">
            {debouncedSearch ? `"${debouncedSearch}" 검색 결과가 없습니다.` : "데이터가 없습니다."}
          </p>
        ) : (
          items.map(item => <ExpandRow key={item.content_id} item={item} onReload={load} />)
        )}
      </div>

      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  )
}
