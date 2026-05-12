"use client"
import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { CategoryScoreBars } from "@/components/category-score-bars"
import { HighlightedText } from "@/components/highlighted-text"
import { api, type Content, type ModelPrediction, type RiskLevel } from "@/lib/api"

export default function AnalyzePage() {
  const [contentId, setContentId] = useState(() => `C${Math.random().toString(36).slice(2, 8).toUpperCase()}`)
  const [text, setText]           = useState("")
  const [result, setResult]       = useState<Content | null>(null)
  const [preds, setPreds]         = useState<ModelPrediction[]>([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState("")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    setLoading(true)
    setError("")
    setResult(null)
    setPreds([])
    try {
      const res = await api.analyze(contentId, text)
      setResult(res)
      const predictions = await api.getPredictions(contentId)
      setPreds(predictions)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg.includes("400") ? "이미 존재하는 content_id입니다." : `오류: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setResult(null)
    setPreds([])
    setText("")
    setError("")
    setContentId(`C${Math.random().toString(36).slice(2, 8).toUpperCase()}`)
  }

  const SCORE_COLOR: Record<RiskLevel, string> = {
    LOW: "text-emerald-400", MEDIUM: "text-yellow-400", HIGH: "text-orange-400", CRITICAL: "text-red-400",
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">콘텐츠 분석</h1>

      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm text-slate-400">Content ID</label>
              <Input value={contentId} onChange={e => setContentId(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm text-slate-400">분석할 텍스트</label>
              <Textarea
                placeholder="분석할 내용을 입력하세요..."
                value={text}
                onChange={e => setText(e.target.value)}
                rows={4}
              />
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <div className="flex gap-2">
              <Button type="submit" disabled={loading || !text.trim()} className="flex-1">
                {loading ? "분석 중..." : "분석 시작"}
              </Button>
              {result && (
                <Button type="button" variant="ghost" onClick={reset}>
                  초기화
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4">
          {/* 판정 결과 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-slate-100 text-base font-semibold">판정 결과</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-6">
                <div>
                  <p className="text-xs text-slate-500 mb-1">위험 점수</p>
                  <p className={`text-4xl font-bold ${SCORE_COLOR[result.risk_level]}`}>
                    {result.risk_score.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">등급</p>
                  <Badge variant={result.risk_level} className="text-sm px-3 py-1">{result.risk_level}</Badge>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">권장 조치</p>
                  <p className="text-sm font-medium text-slate-200">{result.recommended_action}</p>
                </div>
                {result.calibrated_score != null && result.raw_model_score != null && (
                  <div className="ml-auto text-right">
                    <p className="text-xs text-slate-500 mb-1">ML → 보정</p>
                    <p className="text-xs font-mono text-slate-400">
                      {result.raw_model_score.toFixed(3)} → {result.calibrated_score.toFixed(3)}
                    </p>
                  </div>
                )}
              </div>

              {/* 원문 + evidence 하이라이트 */}
              <div className="rounded-md bg-slate-900 p-3">
                <p className="text-slate-500 text-xs font-medium mb-1.5">원문</p>
                {result.evidence_spans && result.evidence_spans.length > 0 ? (
                  <HighlightedText text={result.text} spans={result.evidence_spans} />
                ) : (
                  <p className="text-sm text-slate-200">{result.text}</p>
                )}
              </div>

              {/* 카테고리별 점수 */}
              {result.category_scores && (
                <div>
                  <p className="text-xs text-slate-500 font-medium mb-2">카테고리별 위험 점수</p>
                  <CategoryScoreBars scores={result.category_scores} />
                </div>
              )}
            </CardContent>
          </Card>

          {/* 강제 승격 규칙 */}
          {result.triggered_rules && result.triggered_rules.length > 0 && (
            <div className="rounded-md bg-amber-950/40 border border-amber-800/40 p-3">
              <p className="text-amber-400 text-xs font-medium mb-1.5">강제 승격 규칙 적용됨</p>
              <div className="space-y-1">
                {result.triggered_rules.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-amber-300/80">
                    <span className="font-mono bg-amber-900/40 px-1 rounded">{r.rule_id}</span>
                    <span>{r.description}</span>
                    <span className="ml-auto text-amber-500">최소 {r.min_grade}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* HIGH/CRITICAL 심층 분석 */}
          {result.explanation_json?.deep_analysis && (
            <div className="rounded-md bg-red-950/30 border border-red-800/40 p-3 space-y-2">
              <p className="text-red-400 text-xs font-medium">심층 위험 분석</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <span className="text-slate-500">특정 대상 위협</span>
                <span className={result.explanation_json.deep_analysis.is_targeted ? "text-red-400" : "text-slate-400"}>
                  {result.explanation_json.deep_analysis.is_targeted ? "예" : "아니오"}
                </span>
                <span className="text-slate-500">즉각적 위험</span>
                <span className={result.explanation_json.deep_analysis.is_immediate ? "text-red-400" : "text-slate-400"}>
                  {result.explanation_json.deep_analysis.is_immediate ? "예" : "아니오"}
                </span>
                <span className="text-slate-500">실행 가능성</span>
                <span className={
                  result.explanation_json.deep_analysis.actionability === "high" ? "text-red-400" :
                  result.explanation_json.deep_analysis.actionability === "medium" ? "text-yellow-400" : "text-slate-400"
                }>
                  {result.explanation_json.deep_analysis.actionability}
                </span>
                <span className="text-slate-500">위협 대상</span>
                <span className="text-slate-300">{result.explanation_json.deep_analysis.target_description}</span>
              </div>
              <p className="text-xs text-red-300/80 border-t border-red-800/30 pt-2">
                권장 조치: {result.explanation_json.deep_analysis.suggested_action}
              </p>
            </div>
          )}

          {/* AI 설명 */}
          {result.explanation_json ? (
            <div className="rounded-md bg-slate-800 border border-slate-700 p-4 text-xs text-slate-400 space-y-2">
              <p className="text-slate-300 font-medium text-sm">{result.explanation_json.summary}</p>
              {result.explanation_json.main_reasons.length > 0 && (
                <ul className="list-disc list-inside space-y-0.5 text-slate-500">
                  {result.explanation_json.main_reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
              {result.explanation_json.evidence.length > 0 && (
                <div className="space-y-1 border-t border-slate-700 pt-2">
                  {result.explanation_json.evidence.map((ev, i) => (
                    <div key={i} className="flex gap-2">
                      <span className="text-slate-600 shrink-0">•</span>
                      <span>
                        <span className="text-slate-300 font-mono">"{ev.quote}"</span>
                        <span className="text-slate-500"> — {ev.why_it_matters}</span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-slate-600 border-t border-slate-700 pt-2">
                {result.explanation_json.recommended_operator_check}
              </p>
            </div>
          ) : result.explanation ? (
            <div className="rounded-md bg-slate-800 border border-slate-700 p-4 text-sm text-slate-300 leading-relaxed">
              {result.explanation}
            </div>
          ) : null}

          {/* 모델별 예측 */}
          {preds.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-slate-100 text-base font-semibold">모델별 예측</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {preds.map(p => (
                  <div key={p.id} className="flex items-center gap-4 py-2 border-b border-slate-700 last:border-0">
                    <div className="flex-1">
                      <span className={`text-sm font-medium ${p.is_selected ? "text-indigo-400" : "text-slate-300"}`}>
                        {p.model_name}
                      </span>
                      {p.is_selected && <span className="ml-2 text-xs text-indigo-500">primary</span>}
                    </div>
                    <span className="font-mono text-slate-200">{p.risk_score.toFixed(2)}</span>
                    <Badge variant={p.risk_level as RiskLevel}>{p.risk_level}</Badge>
                    {p.confidence != null && (
                      <span className="text-xs text-slate-400">신뢰도 {(p.confidence * 100).toFixed(0)}%</span>
                    )}
                    {p.latency_ms != null && (
                      <span className="text-xs text-slate-500">{p.latency_ms}ms</span>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
