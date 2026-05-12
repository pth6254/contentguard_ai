"use client"
import { useEffect, useState } from "react"
import { Plus, Trash2, Copy, Check, KeyRound, AlertCircle, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api, ApiKey, ApiKeyCreated } from "@/lib/api"
import { toKSTDate } from "@/lib/utils"

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button onClick={copy} className="text-slate-400 hover:text-slate-100 transition-colors">
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

export default function MyKeysPage() {
  const [keys, setKeys]         = useState<ApiKey[]>([])
  const [keyName, setKeyName]   = useState("")
  const [issuedKey, setIssuedKey] = useState<ApiKeyCreated | null>(null)
  const [error, setError]       = useState<string | null>(null)
  const [loading, setLoading]   = useState(true)

  const loadKeys = async () => {
    try {
      const data = await api.getMyKeys()
      setKeys(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "키 목록을 불러올 수 없습니다.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadKeys() }, [])

  const createKey = async () => {
    if (!keyName.trim()) return
    try {
      const created = await api.createMyKey(keyName.trim())
      setIssuedKey(created)
      setKeyName("")
      setError(null)
      loadKeys()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "키 발급에 실패했습니다.")
    }
  }

  const revokeKey = async (keyId: number) => {
    try {
      await api.revokeMyKey(keyId)
      setError(null)
      loadKeys()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "키 삭제에 실패했습니다.")
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">내 API 키</h1>
          <p className="text-sm text-slate-400 mt-1">
            발급된 API 키를 <code className="text-indigo-400">Authorization: Bearer &lt;key&gt;</code> 헤더로 사용하세요.
          </p>
        </div>
        <button
          onClick={() => api.logout()}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm text-slate-400 hover:bg-slate-800 hover:text-red-400 transition-colors"
        >
          <LogOut className="h-4 w-4" />
          로그아웃
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-950/30 px-4 py-3 rounded-md">
          <AlertCircle className="h-4 w-4 shrink-0" />{error}
        </div>
      )}

      {/* 발급된 키 알림 */}
      {issuedKey && (
        <div className="rounded-md border border-amber-700 bg-amber-950/40 p-4 space-y-2">
          <p className="text-amber-400 text-sm font-medium">
            API 키가 발급되었습니다. 지금 복사하세요 — 다시 표시되지 않습니다.
          </p>
          <div className="flex items-center gap-2 bg-slate-900 rounded px-3 py-2 font-mono text-sm text-slate-200">
            <span className="flex-1 break-all">{issuedKey.key}</span>
            <CopyButton text={issuedKey.key} />
          </div>
          <Button variant="ghost" className="text-xs h-7" onClick={() => setIssuedKey(null)}>닫기</Button>
        </div>
      )}

      {/* 새 키 발급 */}
      <Card>
        <CardHeader><CardTitle className="text-base">새 API 키 발급</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="키 이름 (예: production-key)"
              value={keyName}
              onChange={e => setKeyName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && createKey()}
              className="flex-1"
            />
            <Button onClick={createKey} disabled={!keyName.trim()}>
              <Plus className="h-4 w-4 mr-1" />발급
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 키 목록 */}
      <Card>
        <CardHeader><CardTitle className="text-base">발급된 키 목록</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-slate-500 text-sm">불러오는 중...</p>
          ) : keys.length === 0 ? (
            <p className="text-slate-500 text-sm">발급된 API 키가 없습니다.</p>
          ) : (
            <div className="rounded-md border border-slate-700 overflow-hidden">
              {keys.map(k => (
                <div key={k.id} className="flex items-center gap-3 px-3 py-2.5 border-b border-slate-700 last:border-0">
                  <KeyRound className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                  <span className="font-mono text-xs text-slate-300">{k.key_prefix}...</span>
                  <span className="text-xs text-slate-400 flex-1">{k.name}</span>
                  {k.is_active
                    ? <Badge variant="LOW" className="text-xs">활성</Badge>
                    : <span className="text-xs text-slate-600">비활성</span>}
                  {k.last_used_at && (
                    <span className="text-xs text-slate-600">
                      최근 사용: {toKSTDate(k.last_used_at)}
                    </span>
                  )}
                  {k.is_active && (
                    <button
                      onClick={() => revokeKey(k.id)}
                      className="text-slate-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
