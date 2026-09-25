const TOKEN_KEY = "cg_token"

export function getToken(): string | null {
  if (typeof window === "undefined") return null
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token) return null
  const payload = decodePayload(token)
  if (typeof payload?.exp !== "number" || payload.exp * 1000 <= Date.now() || !["operator", "client"].includes(String(payload.role))) {
    clearToken()
    return null
  }
  return token
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function isLoggedIn(): boolean {
  return !!getToken()
}

export type Role = "operator" | "client" | null

function decodePayload(token: string): Record<string, unknown> | null {
  try {
    const encoded = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")
    const bytes = Uint8Array.from(atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, "=")), c => c.charCodeAt(0))
    return JSON.parse(new TextDecoder().decode(bytes))
  } catch {
    return null
  }
}

export async function authenticatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, init)
  if (response.status === 401 && typeof window !== "undefined") {
    clearToken()
    if (window.location.pathname !== "/login") window.location.assign("/login")
  }
  return response
}

export function getRole(): Role {
  const token = getToken()
  if (!token) return null
  const payload = decodePayload(token)
  return (payload?.role as Role) ?? null
}

export function getUserName(): string {
  const token = getToken()
  if (!token) return ""
  const payload = decodePayload(token)
  return (payload?.name as string) ?? ""
}
