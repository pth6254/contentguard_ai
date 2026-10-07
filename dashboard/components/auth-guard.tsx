"use client"
import { useEffect, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import { Sidebar } from "@/components/sidebar"
import { isLoggedIn, getRole } from "@/lib/auth"
import { api } from "@/lib/api"

// 인증 없이 접근 가능한 페이지
const PUBLIC_PATHS = ["/login", "/signup"]

// 클라이언트 역할만 접근하는 페이지 (사이드바 없이 단순 레이아웃)
const CLIENT_PATHS = ["/my-keys", "/my-dashboard", "/my-batches", "/my-jobs"]

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [checked, setChecked] = useState(false)

  const isPublic = PUBLIC_PATHS.includes(pathname)
  const isClientPage = CLIENT_PATHS.includes(pathname)

  useEffect(() => {
    if (isPublic) {
      setChecked(true)
      return
    }

    if (!isLoggedIn()) {
      router.replace("/login")
      return
    }

    const role = getRole()

    // 클라이언트가 운영자 전용 페이지 접근 시 → 내 키 관리로
    if (role === "client" && !isClientPage) {
      router.replace("/my-dashboard")
      return
    }

    // 운영자가 클라이언트 전용 페이지 접근 시 → 대시보드로
    if (role === "operator" && isClientPage) {
      router.replace("/")
      return
    }

    setChecked(true)
  }, [isPublic, isClientPage, router, pathname])

  // 공개 페이지(로그인, 회원가입): 사이드바 없이 렌더링
  if (isPublic) {
    return <>{children}</>
  }

  // 인증 확인 전: 깜빡임 방지
  if (!checked) return null

  // 클라이언트 페이지: 사이드바 없이 단순 레이아웃
  if (isClientPage) {
    return (
      <main className="min-h-screen p-8 max-w-3xl mx-auto">
        <nav className="mb-6 flex flex-wrap gap-4 text-sm text-indigo-300"><a href="/my-dashboard">내 대시보드</a><a href="/my-keys">API 키</a><a href="/my-batches">대량 분석</a><a href="/my-jobs">작업 관리</a><button onClick={() => api.logout()} className="ml-auto">로그아웃</button></nav>
        {children}
      </main>
    )
  }

  // 운영자 페이지: 사이드바 포함
  return (
    <>
      <Sidebar />
      <main className="ml-56 min-h-screen p-8">
        {children}
      </main>
    </>
  )
}
