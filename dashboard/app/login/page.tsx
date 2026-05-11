"use client"
import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Shield, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import Link from "next/link"
import { api } from "@/lib/api"
import { isLoggedIn, getRole } from "@/lib/auth"

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail]       = useState("")
  const [password, setPassword] = useState("")
  const [error, setError]       = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    if (isLoggedIn()) {
      router.replace(getRole() === "client" ? "/my-keys" : "/")
    }
  }, [router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) return
    setLoading(true)
    setError(null)
    try {
      await api.login(email, password)
      router.replace(getRole() === "client" ? "/my-keys" : "/")
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-full max-w-sm space-y-6">
        {/* 로고 */}
        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center gap-2">
            <Shield className="h-7 w-7 text-indigo-400" />
            <span className="text-xl font-semibold text-slate-100">ContentGuard AI</span>
          </div>
          <p className="text-sm text-slate-400">운영자 로그인</p>
        </div>

        {/* 폼 */}
        <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-700 rounded-xl p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-2 text-sm text-red-400 bg-red-950/30 px-3 py-2.5 rounded-md">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">이메일</label>
            <Input
              type="email"
              placeholder="admin@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">비밀번호</label>
            <Input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          <Button type="submit" className="w-full" disabled={loading || !email || !password}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            로그인
          </Button>
        </form>

        <p className="text-center text-xs text-slate-500">
          API 사용 계정이 없으신가요?{" "}
          <Link href="/signup" className="text-indigo-400 hover:underline">회원가입</Link>
        </p>
      </div>
    </div>
  )
}
