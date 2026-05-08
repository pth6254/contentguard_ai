"use client"
import { useEffect, useState } from "react"
import { Plus, Trash2, Copy, Check, KeyRound, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

const ADMIN_SECRET = process.env.NEXT_PUBLIC_ADMIN_SECRET ?? ""

interface Client  { id: number; name: string; created_at: string }
interface ApiKey  { id: number; client_id: number; name: string; key_prefix: string; is_active: boolean; created_at: string; last_used_at: string | null }
interface NewKey  extends ApiKey { key: string }

async function adminFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Admin-Secret": ADMIN_SECRET, ...options?.headers },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }
  return (
    <button onClick={copy} className="text-slate-400 hover:text-slate-100 transition-colors">
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

export default function AdminPage() {
  const [clients, setClients]       = useState<Client[]>([])
  const [keys, setKeys]             = useState<Record<number, ApiKey[]>>({})
  const [newClient, setNewClient]   = useState("")
  const [newKeyName, setNewKeyName] = useState<Record<number, string>>({})
  const [issuedKey, setIssuedKey]   = useState<NewKey | null>(null)
  const [error, setError]           = useState<string | null>(null)
  const [loading, setLoading]       = useState(true)

  const loadClients = async () => {
    try {
      const data = await adminFetch<Client[]>("/admin/clients")
      setClients(data)
      const keyMap: Record<number, ApiKey[]> = {}
      await Promise.all(data.map(async c => {
        keyMap[c.id] = await adminFetch<ApiKey[]>(`/admin/clients/${c.id}/keys`)
      }))
      setKeys(keyMap)
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setLoading(false) }
  }

  useEffect(() => { loadClients() }, [])

  const createClient = async () => {
    if (!newClient.trim()) return
    try {
      await adminFetch("/admin/clients", { method: "POST", body: JSON.stringify({ name: newClient.trim() }) })
      setNewClient(""); setError(null); loadClients()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  const createKey = async (clientId: number) => {
    const name = (newKeyName[clientId] || "").trim()
    if (!name) return
    try {
      const key = await adminFetch<NewKey>(`/admin/clients/${clientId}/keys`, {
        method: "POST", body: JSON.stringify({ name }),
      })
      setIssuedKey(key)
      setNewKeyName(prev => ({ ...prev, [clientId]: "" }))
      setError(null); loadClients()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  const revokeKey = async (keyId: number) => {
    try {
      await adminFetch(`/admin/keys/${keyId}`, { method: "DELETE" })
      setError(null); loadClients()
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-slate-100">API 키 관리</h1>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-950/30 px-4 py-3 rounded-md">
          <AlertCircle className="h-4 w-4 shrink-0" />{error}
        </div>
      )}

      {/* 발급된 키 알림 */}
      {issuedKey && (
        <div className="rounded-md border border-amber-700 bg-amber-950/40 p-4 space-y-2">
          <p className="text-amber-400 text-sm font-medium">API 키가 발급되었습니다. 지금 복사하세요 — 다시 표시되지 않습니다.</p>
          <div className="flex items-center gap-2 bg-slate-900 rounded px-3 py-2 font-mono text-sm text-slate-200">
            <span className="flex-1 break-all">{issuedKey.key}</span>
            <CopyButton text={issuedKey.key} />
          </div>
          <Button variant="ghost" className="text-xs h-7" onClick={() => setIssuedKey(null)}>닫기</Button>
        </div>
      )}

      {/* 클라이언트 추가 */}
      <Card>
        <CardHeader><CardTitle className="text-base">새 클라이언트 등록</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="클라이언트 이름 (예: 쇼핑몰A)"
              value={newClient}
              onChange={e => setNewClient(e.target.value)}
              onKeyDown={e => e.key === "Enter" && createClient()}
              className="flex-1"
            />
            <Button onClick={createClient} disabled={!newClient.trim()}>
              <Plus className="h-4 w-4 mr-1" />등록
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 클라이언트 목록 */}
      {loading ? (
        <p className="text-slate-500 text-sm">불러오는 중...</p>
      ) : clients.length === 0 ? (
        <p className="text-slate-500 text-sm">등록된 클라이언트가 없습니다.</p>
      ) : (
        clients.map(client => (
          <Card key={client.id}>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                {client.name}
                <span className="text-xs text-slate-500 font-normal">ID: {client.id}</span>
                <span className="text-xs text-slate-600 font-normal ml-auto">{client.created_at.slice(0, 10)}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 기존 키 목록 */}
              {(keys[client.id] ?? []).length > 0 ? (
                <div className="rounded-md border border-slate-700 overflow-hidden">
                  {keys[client.id].map(k => (
                    <div key={k.id} className="flex items-center gap-3 px-3 py-2.5 border-b border-slate-700 last:border-0">
                      <KeyRound className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                      <span className="font-mono text-xs text-slate-300">{k.key_prefix}...</span>
                      <span className="text-xs text-slate-400 flex-1">{k.name}</span>
                      {k.is_active
                        ? <Badge variant="LOW" className="text-xs">활성</Badge>
                        : <span className="text-xs text-slate-600">비활성</span>}
                      {k.last_used_at && <span className="text-xs text-slate-600">최근 사용: {k.last_used_at.slice(0, 10)}</span>}
                      {k.is_active && (
                        <button onClick={() => revokeKey(k.id)} className="text-slate-500 hover:text-red-400 transition-colors">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">발급된 키가 없습니다.</p>
              )}

              {/* 새 키 발급 */}
              <div className="flex gap-2">
                <Input
                  placeholder="키 이름 (예: production-key)"
                  value={newKeyName[client.id] ?? ""}
                  onChange={e => setNewKeyName(prev => ({ ...prev, [client.id]: e.target.value }))}
                  onKeyDown={e => e.key === "Enter" && createKey(client.id)}
                  className="flex-1 h-8 text-sm"
                />
                <Button size="sm" onClick={() => createKey(client.id)} disabled={!newKeyName[client.id]?.trim()}>
                  키 발급
                </Button>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  )
}
