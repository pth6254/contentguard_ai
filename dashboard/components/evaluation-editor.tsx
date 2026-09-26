"use client"
import { useEffect, useState } from "react"
import { api, type Content, type RiskLevel } from "@/lib/api"
import { Button } from "@/components/ui/button"

const LEVELS: RiskLevel[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

export function EvaluationEditor({ content, onSaved }: { content: Content; onSaved?: () => void }) {
  const [level, setLevel] = useState<RiskLevel>(content.risk_level)
  const [category, setCategory] = useState("")
  const [reason, setReason] = useState("")
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")

  useEffect(() => {
    let current = true
    api.getEvaluationLabel(content.id).then(label => {
      if (current) { setLevel(label.expected_level); setCategory(label.category ?? ""); setReason(label.reason ?? ""); setSaved(true) }
    }).catch(error => { if (current && !(error instanceof Error && error.message.startsWith("404"))) setMessage("등록된 정답을 불러오지 못했습니다.") })
    return () => { current = false }
  }, [content.id])

  const save = async () => {
    setBusy(true)
    setMessage("")
    try {
      await api.putEvaluationLabel(content.id, { expected_level: level, category: category.trim() || null, reason: reason.trim() || null })
      setSaved(true)
      setMessage("평가 정답을 저장했습니다.")
      onSaved?.()
    } catch {
      setMessage("평가 정답 저장에 실패했습니다.")
    } finally { setBusy(false) }
  }

  return <div className="space-y-2 rounded border border-slate-700 bg-slate-900 p-3 text-sm">
    <p className="font-medium text-slate-200">AI 평가용 정답 {saved ? "· 등록됨" : "· 미등록"}</p>
    <p className="text-xs text-slate-400">심사 조치와 별개로 실제 위험 등급을 지정합니다.</p>
    <div className="flex flex-wrap gap-2">
      <select aria-label="정답 위험 등급" value={level} onChange={e => setLevel(e.target.value as RiskLevel)} className="rounded bg-slate-800 p-2 text-slate-100">
        {LEVELS.map(value => <option key={value}>{value}</option>)}
      </select>
      <input aria-label="위반 유형" value={category} onChange={e => setCategory(e.target.value)} maxLength={40} placeholder="위반 유형 (선택)" className="rounded bg-slate-800 p-2 text-slate-100" />
    </div>
    <input aria-label="정답 근거" value={reason} onChange={e => setReason(e.target.value)} maxLength={1000} placeholder="판단 근거 (선택)" className="w-full rounded bg-slate-800 p-2 text-slate-100" />
    <Button type="button" onClick={save} disabled={busy} size="sm">정답 저장</Button>
    {message && <p role="status" className="text-xs text-slate-300">{message}</p>}
  </div>
}
