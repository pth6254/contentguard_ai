"use client"
import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Shield, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { isLoggedIn } from "@/lib/auth"

export default function SignupPage() {
  const router = useRouter()
  const [name, setName]         = useState("")
  const [email, setEmail]       = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm]   = useState("")
  const [error, setError]       = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    if (isLoggedIn()) router.replace("/my-keys")
  }, [router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirm) {
      setError("비밀번호가 일치하지 않습니다.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      await api.signup(name, email, password)
      router.replace("/my-keys")
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "회원가입에 실패했습니다.")
    } finally {
      setLoading(false)
    }
  }

  const valid = name.trim() && email.trim() && password.length >= 8 && confirm.length > 0

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-full max-w-sm space-y-6">
        {/* 로고 */}
        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center gap-2">
            <Shield className="h-7 w-7 text-indigo-400" />
            <span className="text-xl font-semibold text-slate-100">ContentGuard AI</span>
          </div>
          <p className="text-sm text-slate-400">클라이언트 회원가입</p>
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
            <label className="text-xs font-medium text-slate-400">이름 / 서비스명</label>
            <Input
              placeholder="홍길동 또는 쇼핑몰A"
              value={name}
              onChange={e => setName(e.target.value)}
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">이메일</label>
            <Input
              type="email"
              placeholder="user@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">비밀번호 (8자 이상)</label>
            <Input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">비밀번호 확인</label>
            <Input
              type="password"
              placeholder="••••••••"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>

          <Button type="submit" className="w-full" disabled={loading || !valid}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            가입하기
          </Button>
        </form>

        <p className="text-center text-xs text-slate-500">
          이미 계정이 있으신가요?{" "}
          <Link href="/login" className="text-indigo-400 hover:underline">로그인</Link>
        </p>
      </div>
    </div>
  )
}
