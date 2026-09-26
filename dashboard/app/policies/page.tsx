"use client"
import { useEffect, useState } from "react"
import { api, type CustomerPolicy, type PolicyPreview } from "@/lib/api"
import { Button } from "@/components/ui/button"

const CATEGORIES = ["profanity", "threat", "sexual", "privacy", "spam", "self_harm", "policy_violation"]
const DEFAULT_POLICY: CustomerPolicy = { client_id: 0, version: 0, trigger_score: 60,
  category_min_levels: {}, review_categories: [], updated_at: null }

export default function PoliciesPage() {
  const [clients, setClients] = useState<{ id: number; name: string }[]>([])
  const [clientId, setClientId] = useState<number | null>(null)
  const [policy, setPolicy] = useState<CustomerPolicy>(DEFAULT_POLICY)
  const [preview, setPreview] = useState<PolicyPreview | null>(null)
  const [message, setMessage] = useState("")
  useEffect(() => { api.getClients().then(setClients).catch(() => setMessage("고객 목록을 불러오지 못했습니다.")) }, [])
  useEffect(() => {
    if (clientId == null) return
    api.getPolicy(clientId).then(value => { setPolicy(value); setPreview(null); setMessage("") })
      .catch(() => setMessage("정책을 불러오지 못했습니다."))
  }, [clientId])
  const body = { expected_version: policy.version, trigger_score: policy.trigger_score,
                 category_min_levels: policy.category_min_levels, review_categories: policy.review_categories }
  const simulate = async () => {
    if (clientId == null) return
    try { setPreview(await api.previewPolicy(clientId, body)); setMessage("") }
    catch { setMessage("미리보기에 실패했습니다.") }
  }
  const save = async () => {
    if (clientId == null) return
    try { setPolicy(await api.savePolicy(clientId, body)); setPreview(null); setMessage("정책을 저장했습니다. 이후 분석과 재분석부터 적용됩니다.") }
    catch { setMessage("정책 저장에 실패했습니다. 버전을 다시 조회해 주세요.") }
  }
  return <div className="space-y-5">
    <h1 className="text-2xl font-bold text-slate-100">고객별 정책</h1>
    <p className="text-sm text-slate-400">고객 정책은 위험 등급을 올리거나 추가 검토를 요구할 수 있습니다. 기본 안전 규칙을 낮추지 않습니다.</p>
    <select aria-label="고객 선택" value={clientId ?? ""} onChange={e => setClientId(e.target.value ? Number(e.target.value) : null)} className="rounded bg-slate-800 p-2 text-slate-100">
      <option value="">고객 선택</option>{clients.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}
    </select>
    {clientId != null && <div className="space-y-4 rounded border border-slate-700 bg-slate-800 p-4">
      <p className="text-sm text-slate-300">현재 버전 {policy.version || "기본"}</p>
      <label className="block text-sm text-slate-300">유형 점수 발동 기준 (0–100)
        <input type="number" min={1} max={100} value={policy.trigger_score} onChange={e => setPolicy({ ...policy, trigger_score: Number(e.target.value) })} className="ml-3 w-20 rounded bg-slate-900 p-2" />
      </label>
      {CATEGORIES.map(category => <div key={category} className="flex flex-wrap items-center gap-3 text-sm text-slate-200">
        <span className="w-36 font-mono">{category}</span>
        <select aria-label={`${category} 최소 등급`} value={policy.category_min_levels[category] ?? ""} onChange={e => {
          const next = { ...policy.category_min_levels }
          if (e.target.value) next[category] = e.target.value as "MEDIUM" | "HIGH" | "CRITICAL"; else delete next[category]
          setPolicy({ ...policy, category_min_levels: next })
        }} className="rounded bg-slate-900 p-2"><option value="">추가 등급 없음</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select>
        <label className="flex items-center gap-1"><input type="checkbox" checked={policy.review_categories.includes(category)} onChange={e => setPolicy({ ...policy, review_categories: e.target.checked ? [...policy.review_categories, category] : policy.review_categories.filter(value => value !== category) })} /> 직접 검토</label>
      </div>)}
      <div className="flex gap-2"><Button onClick={simulate}>최근 100건 미리보기</Button><Button onClick={save}>정책 저장</Button></div>
    </div>}
    {message && <p role="status" className="text-sm text-slate-300">{message}</p>}
    {preview && <div className="space-y-2 rounded border border-slate-700 bg-slate-800 p-4 text-sm text-slate-300">
      <p>최근 {preview.sampled}건 중 {preview.changed}건의 예상 결과가 달라집니다. {preview.notice}</p>
      {preview.changes.map(item => <p key={item.record_id}>{item.content_id}: {item.before} → {item.after}{item.review_required ? " · 직접 검토" : ""}</p>)}
    </div>}
  </div>
}
