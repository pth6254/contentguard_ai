"use client"
import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
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
              />
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <Button type="submit" disabled={loading || !text.trim()} className="w-full">
              {loading ? "분석 중..." : "분석 시작"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4">
          {/* 분석 결과 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-slate-100 text-base font-semibold">분석 결과</CardTitle>
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
              </div>
              {result.explanation && (
                <div className="rounded-md bg-slate-900 p-4 text-sm text-slate-300 leading-relaxed">
                  {result.explanation}
                </div>
              )}
            </CardContent>
          </Card>

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
