"use client"
import { useState } from "react"
import { DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api, type Content, type ReviewAction, type ReviewStatus } from "@/lib/api"

const STATUS_LABEL: Record<ReviewStatus, string> = {
  PENDING: "대기", APPROVED: "승인", REMOVED: "삭제", HELD: "보류", MONITORED: "모니터링",
}

export function ReviewDialog({ content, onDone }: { content: Content; onDone: () => void }) {
  const [comment, setComment] = useState(content.reviewer_comment ?? "")
  const [loading, setLoading] = useState(false)

  const isRereview = content.review_status !== "PENDING"

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
        <DialogTitle>
          {isRereview ? "심사 재변경" : "운영자 판단"} — {content.content_id}
        </DialogTitle>
      </DialogHeader>
      <div className="space-y-4">
        <p className="text-sm text-slate-300 leading-relaxed">{content.text}</p>
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
