"use client"
import { useEffect, useState } from "react"
import { api, type Content, type EvaluationSummary, type RiskLevel } from "@/lib/api"
import { EvaluationEditor } from "@/components/evaluation-editor"
import { AnalysisStatus } from "@/components/analysis-status"

const LEVELS: RiskLevel[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
const percent = (value: number | null) => value == null ? "자료 없음" : `${(value * 100).toFixed(1)}%`

export default function EvaluationPage() {
  const [summary, setSummary] = useState<EvaluationSummary | null>(null)
  const [contents, setContents] = useState<Content[]>([])
  const [error, setError] = useState("")
  const [page, setPage] = useState(0)
  const load = () => {
    Promise.all([api.getEvaluationSummary(), api.getContents({ limit: 20, offset: page * 20 })])
      .then(([stats, records]) => { setSummary(stats); setContents(records.items); setError("") })
      .catch(() => setError("평가 데이터를 불러오지 못했습니다."))
  }
  useEffect(() => { load() }, [page])

  return <div className="space-y-5">
    <h1 className="text-2xl font-bold text-slate-100">AI 품질 평가</h1>
    <p className="text-sm text-slate-400">운영자의 삭제·승인 조치와 별도로 정답을 기록합니다. 정확도는 정상 완료된 분석과 명시적으로 등록한 정답만 비교합니다.</p>
    {error && <p role="alert" className="text-red-400">{error} <button className="underline" onClick={load}>재시도</button></p>}
    {summary && <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          ["정답 등록", `${summary.labeled}건`], ["평가 가능", `${summary.evaluated}건`],
          ["정확도", percent(summary.accuracy)], ["고위험 정밀도", percent(summary.precision_high)],
          ["고위험 재현율", percent(summary.recall_high)],
        ].map(([label, value]) => <div key={label} className="rounded border border-slate-700 bg-slate-800 p-3"><p className="text-xs text-slate-400">{label}</p><p className="text-lg font-bold text-slate-100">{value}</p></div>)}
      </div>
      <p className="text-sm text-slate-400">평가 제외 {summary.skipped}건 · 고위험 오탐 {summary.false_positives}건 · 고위험 미탐 {summary.false_negatives}건</p>
      <div className="overflow-x-auto rounded border border-slate-700 bg-slate-800 p-3 text-sm text-slate-300">
        <p className="mb-2 font-medium">정답 등급(행)과 AI 등급(열)</p>
        <table className="w-full text-center"><thead><tr><th>정답</th>{LEVELS.map(level => <th key={level}>{level}</th>)}</tr></thead><tbody>{LEVELS.map(actual => <tr key={actual}><th>{actual}</th>{LEVELS.map(predicted => <td key={predicted}>{summary.confusion[actual][predicted]}</td>)}</tr>)}</tbody></table>
      </div>
      {Object.keys(summary.by_category).length > 0 && <p className="text-sm text-slate-400">유형별 일치: {Object.entries(summary.by_category).map(([name, value]) => `${name} ${value.correct}/${value.total}`).join(" · ")}</p>}
    </>}
    <div className="space-y-3">{contents.map(content => <div key={content.id} className="rounded border border-slate-700 bg-slate-800 p-4 space-y-2">
      <div className="flex items-center gap-2 text-sm text-slate-200"><span className="font-mono">{content.content_id}</span><span>AI: {content.risk_level}</span><AnalysisStatus content={content} /></div>
      <p className="line-clamp-2 text-sm text-slate-400">{content.text}</p>
      <EvaluationEditor content={content} onSaved={load} />
    </div>)}</div>
    <div className="flex gap-2 text-sm text-slate-300"><button disabled={page === 0} onClick={() => setPage(page - 1)} className="disabled:opacity-40">이전</button><span>{page + 1}페이지</span><button disabled={contents.length < 20} onClick={() => setPage(page + 1)} className="disabled:opacity-40">다음</button></div>
  </div>
}
