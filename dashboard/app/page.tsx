"use client"
import { useEffect, useState } from "react"
import { RefreshCw } from "lucide-react"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api, type Content, type RiskLevel, type ReviewStatus } from "@/lib/api"

const REFRESH_INTERVAL = 30_000

const LEVEL_COLOR: Record<RiskLevel, string> = {
  LOW: "#22c55e", MEDIUM: "#eab308", HIGH: "#f97316", CRITICAL: "#ef4444",
}

const STATUS_LABEL: Record<ReviewStatus, string> = {
  PENDING: "대기", APPROVED: "승인", REMOVED: "삭제", HELD: "보류", MONITORED: "모니터링",
}

export default function DashboardPage() {
  const [recent, setRecent]       = useState<Content[]>([])
  const [stats, setStats]         = useState({ total: 0, pending: 0, approved: 0, removed: 0, held: 0 })
  const [levelCounts, setLevelCounts] = useState<Record<RiskLevel, number>>({ LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 })
  const [loading, setLoading]     = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshTick, setRefreshTick] = useState(0)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getContents({ limit: 5 }),
      api.getContents({ limit: 1 }),
      api.getContents({ status: "PENDING",  limit: 1 }),
      api.getContents({ status: "APPROVED", limit: 1 }),
      api.getContents({ status: "REMOVED",  limit: 1 }),
      api.getContents({ status: "HELD",     limit: 1 }),
      api.getContents({ risk_level: "LOW",      limit: 1 }),
      api.getContents({ risk_level: "MEDIUM",   limit: 1 }),
      api.getContents({ risk_level: "HIGH",     limit: 1 }),
      api.getContents({ risk_level: "CRITICAL", limit: 1 }),
    ]).then(([recentR, totalR, pendingR, approvedR, removedR, heldR, lowR, medR, highR, critR]) => {
      setRecent(recentR.items)
      setStats({ total: totalR.total, pending: pendingR.total, approved: approvedR.total, removed: removedR.total, held: heldR.total })
      setLevelCounts({ LOW: lowR.total, MEDIUM: medR.total, HIGH: highR.total, CRITICAL: critR.total })
    }).finally(() => setLoading(false))
  }, [refreshTick])

  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => setRefreshTick(t => t + 1), REFRESH_INTERVAL)
    return () => clearInterval(id)
  }, [autoRefresh])

  const levelData = (["LOW", "MEDIUM", "HIGH", "CRITICAL"] as RiskLevel[]).map(level => ({
    level,
    count: levelCounts[level],
    fill: LEVEL_COLOR[level],
  }))

  const metrics = [
    { label: "전체 콘텐츠", value: stats.total },
    { label: "심사 대기",   value: stats.pending,  highlight: stats.pending > 0 },
    { label: "승인",        value: stats.approved },
    { label: "삭제",        value: stats.removed },
    { label: "보류",        value: stats.held },
  ]

  return (
    <div className="space-y-6">
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

      {/* 지표 카드 */}
      <div className="grid grid-cols-5 gap-4">
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
              <div key={c.content_id} className="flex items-center gap-3 py-1.5 border-b border-slate-700 last:border-0">
                <Badge variant={c.risk_level}>{c.risk_level}</Badge>
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
