"use client"
import { useEffect, useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { api, type Content, type ReviewStatus, type RiskLevel } from "@/lib/api"

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "전체" },
  { value: "PENDING",   label: "대기" },
  { value: "APPROVED",  label: "승인" },
  { value: "REMOVED",   label: "삭제" },
  { value: "HELD",      label: "보류" },
  { value: "MONITORED", label: "모니터링" },
]

function ExpandRow({ item }: { item: Content }) {
  const [open, setOpen] = useState(false)
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
        <span className="text-xs text-slate-600">{item.created_at.slice(0, 10)}</span>
        {open ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
      </div>
      {open && (
        <div className="px-4 pb-4 space-y-2">
          {item.explanation && (
            <div className="rounded-md bg-slate-900 p-3 text-xs text-slate-400 leading-relaxed">
              <p className="text-slate-500 mb-1 font-medium">AI 설명</p>
              {item.explanation}
            </div>
          )}
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

export default function HistoryPage() {
  const [items, setItems]   = useState<Content[]>([])
  const [status, setStatus] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getContents({ status: status || undefined })
      .then(setItems)
      .finally(() => setLoading(false))
  }, [status])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">전체 이력</h1>

      {/* 상태 필터 */}
      <div className="flex items-center gap-2">
        {STATUS_OPTIONS.map(opt => (
          <button
            key={opt.value}
            onClick={() => setStatus(opt.value)}
            className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
              status === opt.value
                ? "bg-indigo-600 text-white"
                : "bg-slate-800 text-slate-400 hover:text-slate-100"
            }`}
          >
            {opt.label}
          </button>
        ))}
        <span className="ml-auto text-sm text-slate-500">총 {items.length}건</span>
      </div>

      {/* 테이블 */}
      <div className="rounded-lg border border-slate-700 bg-slate-800 overflow-hidden">
        {loading ? (
          <p className="p-6 text-slate-500 text-sm">불러오는 중...</p>
        ) : items.length === 0 ? (
          <p className="p-6 text-slate-500 text-sm text-center">데이터가 없습니다.</p>
        ) : (
          items.map(item => <ExpandRow key={item.content_id} item={item} />)
        )}
      </div>
    </div>
  )
}
