"use client"
import { useEffect, useState } from "react"
import { RefreshCw } from "lucide-react"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AnalysisStatus } from "@/components/analysis-status"
import { api, type Content, type RiskLevel, type ReviewStatus, type Stats, type Operations } from "@/lib/api"

const REFRESH_INTERVAL = 30_000

const LEVEL_COLOR: Record<RiskLevel, string> = {
  LOW: "#22c55e", MEDIUM: "#eab308", HIGH: "#f97316", CRITICAL: "#ef4444",
}

const STATUS_LABEL: Record<ReviewStatus, string> = {
  PENDING: "대기", APPROVED: "승인", REMOVED: "삭제", HELD: "보류", MONITORED: "모니터링",
}

export default function DashboardPage() {
  const [recent, setRecent]       = useState<Content[]>([])
  const [stats, setStats]         = useState<Stats | null>(null)
  const [operations, setOperations] = useState<Operations | null>(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshTick, setRefreshTick] = useState(0)

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      api.getStats(),
      api.getContents({ limit: 5 }),
      api.getOperations(),
    ]).then(([s, recentR, operationsR]) => {
      setStats(s)
      setOperations(operationsR)
      setRecent(recentR.items)
    }).catch((e: unknown) => {
      setError(e instanceof Error ? e.message : String(e))
    }).finally(() => setLoading(false))
  }, [refreshTick])

  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => setRefreshTick(t => t + 1), REFRESH_INTERVAL)
    return () => clearInterval(id)
  }, [autoRefresh])

  const levelData = (["LOW", "MEDIUM", "HIGH", "CRITICAL"] as RiskLevel[]).map(level => ({
    level,
    count: stats?.by_level[level] ?? 0,
    fill: LEVEL_COLOR[level],
  }))

  const pending = stats?.by_status["PENDING"] ?? 0
  const metrics = [
    { label: "전체 콘텐츠", value: stats?.total ?? 0 },
    { label: "심사 대기",   value: pending,  highlight: pending > 0 },
    { label: "재심사 필요", value: stats?.re_review_required ?? 0 },
    { label: "승인",        value: stats?.by_status["APPROVED"] ?? 0 },
    { label: "삭제",        value: stats?.by_status["REMOVED"]  ?? 0 },
    { label: "보류",        value: stats?.by_status["HELD"]     ?? 0 },
  ]

  return (
    <div className="space-y-6">
      {error && <p role="alert" className="rounded border border-red-800 bg-red-950 p-3 text-sm text-red-300">대시보드를 불러오지 못했습니다. <button onClick={() => setRefreshTick(t => t + 1)} className="underline">재시도</button></p>}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">대시보드</h1>
        <button
          onClick={() => setAutoRefresh(a => !a)}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
            autoRefresh ? "bg-slate-800 text-emerald-400" : "bg-slate-800 text-slate-500"
          }`}
        >
          <RefreshCw className={`h-3 w-3 ${autoRefresh && loading ? "animate-spin" : ""}`} />
          자동 새로고침
        </button>
      </div>

      {operations && <section className="space-y-2 rounded border border-slate-700 bg-slate-800 p-4 text-sm text-slate-300">
        <h2 className="font-semibold text-slate-100">처리 상태</h2>
        <p>분석 워커: {operations.workers.analysis === "ok" ? "정상" : "응답 없음"} · 웹훅 워커: {operations.workers.webhook === "ok" ? "정상" : "응답 없음"} · 최근 24시간 실패·임시 분석 비율: {operations.failure_rate_24h == null ? "자료 없음" : `${(operations.failure_rate_24h * 100).toFixed(1)}%`}</p>
        {operations.alerts.length ? <div role="status" className="text-amber-300">{operations.alerts.map(alert => <p key={alert}>{alert}</p>)}<a href="/jobs" className="underline">작업 확인</a></div> : <p className="text-emerald-400">확인이 필요한 작업 경고가 없습니다.</p>}
      </section>}

      {/* 지표 카드 */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {metrics.map(({ label, value, highlight }) => (
          <Card key={label}>
            <CardHeader><CardTitle>{label}</CardTitle></CardHeader>
            <CardContent>
              <p className={`text-3xl font-bold ${highlight ? "text-amber-400" : "text-slate-100"}`}>
                {loading ? "—" : value}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* 위험 등급 분포 */}
        <Card>
          <CardHeader><CardTitle className="text-slate-100 text-base font-semibold">위험 등급 분포</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={levelData} barSize={40}>
                <XAxis dataKey="level" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                  labelStyle={{ color: "#f1f5f9" }}
                  itemStyle={{ color: "#94a3b8" }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {levelData.map(d => <Cell key={d.level} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* 최근 분석 내역 */}
        <Card>
          <CardHeader><CardTitle className="text-slate-100 text-base font-semibold">최근 분석 내역</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {loading ? (
              <p className="text-slate-500 text-sm">불러오는 중...</p>
            ) : recent.map(c => (
              <div key={c.id} className="flex items-center gap-3 py-1.5 border-b border-slate-700 last:border-0">
                <Badge variant={c.risk_level}>{c.risk_level}</Badge>
                <AnalysisStatus content={c} />
                <p className="flex-1 text-sm text-slate-300 truncate">{c.text}</p>
                <Badge variant={c.review_status}>{STATUS_LABEL[c.review_status]}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
