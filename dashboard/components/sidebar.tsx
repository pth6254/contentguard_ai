"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { LayoutDashboard, ClipboardList, Search, History, Shield, DatabaseZap, Settings, LogOut } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

const NAV = [
  { href: "/",        label: "대시보드",    icon: LayoutDashboard },
  { href: "/queue",   label: "심사 큐",     icon: ClipboardList },
  { href: "/analyze", label: "콘텐츠 분석", icon: Search },
  { href: "/history",  label: "전체 이력",   icon: History },
  { href: "/collect",  label: "데이터 수집",  icon: DatabaseZap },
  { href: "/admin",    label: "API 키 관리",  icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const [connected, setConnected] = useState<boolean | null>(null)

  useEffect(() => {
    api.health()
      .then(() => setConnected(true))
      .catch(() => setConnected(false))
  }, [])

  return (
    <aside className="fixed left-0 top-0 h-screen w-56 border-r border-slate-700 bg-slate-900 flex flex-col">
      <div className="flex items-center gap-2 px-5 py-5 border-b border-slate-700">
        <Shield className="h-5 w-5 text-indigo-400" />
        <span className="font-semibold text-slate-100 text-sm">ContentGuard AI</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-indigo-600/20 text-indigo-400 font-medium"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>

      <div className="px-3 py-4 border-t border-slate-700 space-y-3">
        {/* API 연결 상태 */}
        <div className="flex items-center gap-2 px-2 text-xs">
          <span className={cn("h-2 w-2 rounded-full shrink-0", connected === true ? "bg-emerald-400" : connected === false ? "bg-red-400" : "bg-slate-500")} />
          <span className="text-slate-400">
            {connected === true ? "API 연결됨" : connected === false ? "API 연결 안됨" : "확인 중..."}
          </span>
        </div>

        {/* 로그아웃 */}
        <button
          onClick={() => api.logout()}
          className="flex items-center gap-3 w-full rounded-md px-3 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-red-400 transition-colors"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          로그아웃
        </button>
      </div>
    </aside>
  )
}
