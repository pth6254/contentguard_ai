"use client"
import { useState } from "react"
import { DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { AnalysisStatus } from "@/components/analysis-status"
import { AnalysisHistory } from "@/components/analysis-history"
import { EvaluationEditor } from "@/components/evaluation-editor"
import { api, type Content, type ReviewAction, type ReviewStatus, type ReviewEvent } from "@/lib/api"
import { toKSTDateTime } from "@/lib/utils"

const STATUS_LABEL: Record<ReviewStatus, string> = {
  PENDING: "대기", APPROVED: "승인", REMOVED: "삭제", HELD: "보류", MONITORED: "모니터링",
}

export function ReviewDialog({ content, onDone }: { content: Content; onDone: () => void }) {
  const [comment, setComment] = useState(content.reviewer_comment ?? "")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [history, setHistory] = useState<ReviewEvent[] | null>(null)
  const [jobMessage, setJobMessage] = useState("")

  const isRereview = content.review_status !== "PENDING"

  const act = async (action: ReviewAction) => {
    setLoading(true)
    setError("")
    try {
      await api.review(content, action, comment)
      onDone()
    } catch (err) {
      setError(err instanceof Error && err.message.includes("409") ? "다른 운영자가 변경했습니다. 목록을 새로고침해 주세요." : "심사 저장에 실패했습니다. 다시 시도해 주세요.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <DialogContent className="max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>
          {isRereview ? "심사 재변경" : "운영자 판단"} — {content.content_id}
        </DialogTitle>
      </DialogHeader>
      <div className="space-y-4">
        {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
        <p className="text-sm text-slate-300 leading-relaxed">{content.text}</p>
        <AnalysisStatus content={content} />
        <AnalysisHistory content={content} />
        <button type="button" className="text-xs text-indigo-400" onClick={async () => {
          try { const job = await api.reanalyze(content); setJobMessage(`재분석 작업 ${job.id} 접수됨. 작업 현황에서 상태를 확인하세요.`) }
          catch { setJobMessage("재분석 접수에 실패했습니다.") }
        }}>재분석 요청</button>
        {jobMessage && <p role="status" className="text-xs text-slate-300">{jobMessage}</p>}
        <EvaluationEditor content={content} />
        {content.explanation && (
          <div className="rounded-md bg-slate-900 p-3 text-xs text-slate-400 leading-relaxed">
            {content.explanation}
          </div>
        )}
        {isRereview && (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span>현재 상태</span>
            <Badge variant={content.review_status}>{STATUS_LABEL[content.review_status]}</Badge>
          </div>
        )}
        <Textarea
          placeholder="메모 (선택)"
          value={comment}
          onChange={e => setComment(e.target.value)}
          className="h-20"
          maxLength={2000}
        />
        <button className="text-xs text-indigo-400" onClick={async () => {
          try { setHistory(await api.reviewHistory(content)) }
          catch { setError("변경 이력을 불러오지 못했습니다.") }
        }}>심사 변경 이력 보기</button>
        {history && <div className="max-h-40 overflow-y-auto space-y-2 text-xs text-slate-400">
          {history.length === 0 && <p>변경 이력이 없습니다.</p>}
          {history.map(event => <div key={event.id}>
            <p>{toKSTDateTime(event.created_at)} · {event.actor} · {event.previous_status} → {event.status}</p>
            {event.comment && <p>{event.comment}</p>}
          </div>)}
        </div>}
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
