"use client"
import { useEffect, useRef, useState } from "react"
import { api, type EvaluationDataset, type EvaluationReport } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { toKSTDateTime } from "@/lib/utils"

const percent = (value: number | null) => value == null ? "자료 없음" : `${(value * 100).toFixed(1)}%`

export function EvaluationReports() {
  const [datasets, setDatasets] = useState<EvaluationDataset[]>([])
  const [datasetId, setDatasetId] = useState<number | null>(null)
  const [reports, setReports] = useState<EvaluationReport[]>([])
  const [datasetName, setDatasetName] = useState("")
  const [name, setName] = useState("")
  const [model, setModel] = useState("")
  const [provider, setProvider] = useState("")
  const [prompt, setPrompt] = useState("")
  const [policy, setPolicy] = useState("")
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const currentDataset = useRef<number | null>(null)
  useEffect(() => { api.getEvaluationDatasets().then(setDatasets).catch(() => setMessage("저장된 데이터셋을 불러오지 못했습니다.")) }, [])
  useEffect(() => {
    currentDataset.current = datasetId; setReports([])
    if (datasetId != null) api.getEvaluationReports(datasetId).then(rows => { if (currentDataset.current === datasetId) setReports(rows) }).catch(() => setMessage("평가 보고서를 불러오지 못했습니다."))
  }, [datasetId])
  const freezeDataset = async () => {
    setBusy(true)
    try {
      const value = await api.freezeEvaluationDataset(datasetName)
      setDatasets(previous => [value, ...previous]); setDatasetId(value.id); setDatasetName(""); setMessage(`${value.size}건의 정답을 데이터셋으로 저장했습니다.`)
    } catch { setMessage("데이터셋을 저장하지 못했습니다. 등록된 정답이 있는지 확인하세요.") }
    finally { setBusy(false) }
  }
  const freezeReport = async () => {
    if (datasetId == null) return
    setBusy(true)
    try {
      const value = await api.freezeEvaluationReport(datasetId, { name, provider, model, prompt_version: prompt, policy_version: policy })
      setReports(previous => [value, ...previous]); setMessage("평가 보고서를 저장했습니다. 이후 분석이나 정답 변경의 영향을 받지 않습니다.")
    } catch { setMessage("평가 보고서를 저장하지 못했습니다.") }
    finally { setBusy(false) }
  }
  return <section className="space-y-3 rounded border border-slate-700 bg-slate-800 p-4">
    <h2 className="text-lg font-semibold text-slate-100">고정 데이터셋 · 버전별 평가 비교</h2>
    <p className="text-sm text-slate-400">등록된 정답을 고정한 후, 조건에 맞는 콘텐츠별 최근 분석으로 보고서를 저장합니다. 분석이 없거나 임시 결과이면 평가에서 제외되므로 평가 건수도 함께 비교하세요.</p>
    <div className="flex flex-wrap gap-2"><input aria-label="평가 데이터셋 이름" maxLength={100} placeholder="데이터셋 이름" value={datasetName} onChange={e => setDatasetName(e.target.value)} className="rounded bg-slate-900 p-2 text-slate-100" /><Button disabled={busy || !datasetName.trim()} onClick={freezeDataset}>현재 정답 고정</Button></div>
    <select aria-label="평가 데이터셋 선택" disabled={busy} value={datasetId ?? ""} onChange={e => setDatasetId(e.target.value ? Number(e.target.value) : null)} className="max-w-full rounded bg-slate-900 p-2 text-slate-100"><option value="">데이터셋 선택</option>{datasets.map(item => <option key={item.id} value={item.id}>{item.name} · {item.size}건 · {toKSTDateTime(item.created_at)}</option>)}</select>
    {datasetId != null && <>
      <div className="flex flex-wrap gap-2">
        {[["보고서 이름", name, setName], ["공급자 (선택)", provider, setProvider], ["모델 (선택)", model, setModel], ["프롬프트 버전 (선택)", prompt, setPrompt], ["정책 버전 (선택)", policy, setPolicy]].map(([label, value, setter]) => <input key={label as string} aria-label={label as string} placeholder={label as string} maxLength={100} value={value as string} onChange={e => (setter as (value: string) => void)(e.target.value)} className="rounded bg-slate-900 p-2 text-sm text-slate-100" />)}
        <Button disabled={busy || !name.trim()} onClick={freezeReport}>평가 보고서 저장</Button>
      </div>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm text-slate-300"><thead><tr><th className="p-2">보고서 / 조건</th><th className="p-2">평가 / 제외</th><th className="p-2">정확도</th><th className="p-2">고위험 재현율</th><th className="p-2">고위험 정밀도</th></tr></thead>
        <tbody>{reports.map(report => <tr key={report.id} className="border-t border-slate-700"><td className="p-2">{report.name}<p className="text-xs text-slate-400">{Object.values(report.filters).join(" · ") || "저장 시점의 최근 분석"}</p><p className="text-xs text-slate-500">{toKSTDateTime(report.created_at)}</p></td><td className="p-2">{report.metrics.evaluated} / {report.metrics.skipped}</td><td className="p-2">{percent(report.metrics.accuracy)}</td><td className="p-2">{percent(report.metrics.recall_high)}</td><td className="p-2">{percent(report.metrics.precision_high)}</td></tr>)}</tbody></table></div>
    </>}
    {message && <p role="status" className="text-sm text-slate-300">{message}</p>}
  </section>
}
