"use client"
import { useEffect, useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { api, type Content, type ModelPrediction, type RiskLevel, type ReviewAction } from "@/lib/api"

const LEVEL_COUNT_COLOR: Record<RiskLevel, string> = {
  LOW: "text-emerald-400", MEDIUM: "text-yellow-400", HIGH: "text-orange-400", CRITICAL: "text-red-400",
}

function ReviewDialog({ content, onDone }: { content: Content; onDone: () => void }) {
  const [comment, setComment] = useState("")
  const [loading, setLoading] = useState(false)

  const act = async (action: ReviewAction) => {
    setLoading(true)
    try {
      await api.review(content.content_id, action, comment)
      onDone()
    } finally {
      setLoading(false)
    }
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>운영자 판단 — {content.content_id}</DialogTitle>
      </DialogHeader>
      <div className="space-y-4">
        <p className="text-sm text-slate-300 leading-relaxed">{content.text}</p>
        {content.explanation && (
          <div className="rounded-md bg-slate-900 p-3 text-xs text-slate-400 leading-relaxed">
            {content.explanation}
          </div>
        )}
        <Textarea
          placeholder="메모 (선택)"
          value={comment}
          onChange={e => setComment(e.target.value)}
          className="h-20"
        />
        <div className="grid grid-cols-2 gap-2">
          <Button variant="success"     onClick={() => act("approve")} disabled={loading}>승인</Button>
          <Button variant="ghost"       onClick={() => act("monitor")} disabled={loading}>모니터링</Button>
          <Button variant="warning"     onClick={() => act("hold")}    disabled={loading}>보류</Button>
          <Button variant="destructive" onClick={() => act("remove")}  disabled={loading}>삭제</Button>
        </div>
      </div>
    </DialogContent>
  )
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

export default function QueuePage() {
  const [items, setItems]       = useState<Content[]>([])
  const [sortBy, setSortBy]     = useState<"risk_score" | "created_at">("risk_score")
  const [levelFilter, setLevel] = useState<string>("")
  const [loading, setLoading]   = useState(true)

  const load = () => {
    setLoading(true)
    api.getContents({ status: "PENDING", sort_by: sortBy, risk_level: levelFilter || undefined })
      .then(setItems)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [sortBy, levelFilter])

  const counts = (["CRITICAL", "HIGH", "MEDIUM", "LOW"] as RiskLevel[]).map(l => ({
    level: l, count: items.filter(c => c.risk_level === l).length,
  }))

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">심사 큐</h1>

      {/* 긴급도 요약 */}
      <div className="flex items-center gap-6">
        <span className="text-slate-400 text-sm">대기 {items.length}건</span>
        {counts.map(({ level, count }) => (
          <span key={level} className={`text-sm font-semibold ${LEVEL_COUNT_COLOR[level]}`}>
            {level} {count}
          </span>
        ))}
      </div>

      {/* 컨트롤 */}
      <div className="flex items-center gap-3">
        {[
          { value: "risk_score", label: "위험도 높은 순" },
          { value: "created_at", label: "최신 순" },
        ].map(opt => (
          <button
            key={opt.value}
            onClick={() => setSortBy(opt.value as typeof sortBy)}
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
            onClick={() => setLevel(l)}
            className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
              levelFilter === l ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:text-slate-100"
            }`}
          >
            {l || "전체"}
          </button>
        ))}
      </div>

      {/* 목록 */}
      {loading ? (
        <p className="text-slate-500">불러오는 중...</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-12 text-center text-slate-400">
          심사 대기 중인 콘텐츠가 없습니다.
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
                      <span className="text-xs text-slate-500">{item.created_at.slice(0, 16)}</span>
                    </div>
                    <p className="text-sm text-slate-200">{item.text}</p>
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
                      <ReviewDialog content={item} onDone={load} />
                    </Dialog>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
