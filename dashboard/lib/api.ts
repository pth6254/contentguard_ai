import { getToken, setToken, clearToken, authenticatedFetch } from "@/lib/auth"

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken()
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  }
}

function buildUrl(path: string, params?: Record<string, string>): string {
  const qs = params
    ? new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
    : ""
  return qs ? `${path}?${qs}` : path
}

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
export type ReviewStatus = "PENDING" | "APPROVED" | "REMOVED" | "HELD" | "MONITORED"
export type ReviewAction = "approve" | "remove" | "hold" | "monitor"

export interface EvidenceSpan {
  text: string
  category: string
  severity: "low" | "medium" | "high" | "critical"
  start_index: number
  end_index: number
}

export interface CategoryScores {
  profanity: number
  threat: number
  sexual: number
  privacy: number
  spam: number
  self_harm: number
  policy_violation: number
}

export interface DeepAnalysis {
  is_targeted: boolean
  is_immediate: boolean
  actionability: "low" | "medium" | "high"
  target_description: string
  suggested_action: string
}

export interface ExplanationJson {
  analysis_status?: "completed" | "fallback"
  review_required?: boolean
  summary: string
  score_explanation: string
  main_reasons: string[]
  evidence: { quote: string; category: string; why_it_matters: string }[]
  recommended_operator_check: string
  confidence_note: string
  deep_analysis?: DeepAnalysis
}

export interface Content {
  id: number
  client_id: number | null
  review_version: number
  needs_re_review: boolean
  content_id: string
  text: string
  risk_score: number
  risk_level: RiskLevel
  recommended_action: string
  explanation: string | null
  review_status: ReviewStatus
  review_action: string | null
  reviewer_comment: string | null
  reviewed_at: string | null
  created_at: string
  // v2 분석 세부 정보
  raw_model_score: number | null
  calibrated_score: number | null
  category_scores: CategoryScores | null
  triggered_rules: { rule_id: string; description: string; min_grade: string; category: string; matched_text: string; review_only?: boolean }[] | null
  evidence_spans: EvidenceSpan[] | null
  explanation_json: ExplanationJson | null
}

export interface ModelPrediction {
  id: number
  content_id: string
  model_name: string
  model_version: string
  model_type: string
  risk_score: number
  risk_level: RiskLevel
  recommended_action: string
  confidence: number | null
  latency_ms: number | null
  is_selected: boolean
  is_shadow: boolean
  created_at: string
}

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const res = await authenticatedFetch(buildUrl(path, params), { cache: "no-store", headers: authHeaders() })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

async function getPaginated<T>(path: string, params?: Record<string, string>): Promise<{ items: T[]; total: number }> {
  const res = await authenticatedFetch(buildUrl(path, params), { cache: "no-store", headers: authHeaders() })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  const items: T[] = await res.json()
  const total = parseInt(res.headers.get("X-Total-Count") ?? "0", 10)
  return { items, total }
}

async function post<T>(path: string, body: unknown, extraHeaders?: Record<string, string>): Promise<T> {
  const res = await authenticatedFetch(path, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json", ...extraHeaders }),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

export interface Stats {
  total: number
  by_status: Record<string, number>
  by_level: Record<string, number>
  re_review_required: number
}

export interface AnalysisJob {
  id: string
  kind: "new" | "reanalysis"
  content_id: string
  content_record_id: number | null
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED"
  attempts: number
  last_error: string | null
  created_at: string
  finished_at: string | null
}

export interface CustomerPolicy {
  client_id: number
  version: number
  category_min_levels: Record<string, "MEDIUM" | "HIGH" | "CRITICAL">
  review_categories: string[]
  trigger_score: number
  updated_at: string | null
}

export interface PolicyPreview {
  sampled: number
  changed: number
  changes: { record_id: number; content_id: string; before: RiskLevel; after: RiskLevel; review_required: boolean }[]
  notice: string
}

export interface ClientDashboard {
  client: { id: number; name: string }
  total: number
  by_status: Record<string, number>
  jobs: Record<string, number>
  webhooks: Record<string, number>
  policy_version: number
}

export interface ClientWebhook {
  event_id: string
  content_id: string
  review_version: number
  status: string
  attempts: number
  delivered_at: string | null
}

export interface BatchPreview {
  format: string
  columns: string[]
  rows: number
  sample: Record<string, string>[]
}

export interface BatchImport {
  id: string
  format: string
  rows_total: number
  accepted: number
  skipped: number
  by_status: Record<string, number>
  created_at: string
}

export interface ApiKey {
  id: number
  client_id: number
  name: string
  key_prefix: string
  is_active: boolean
  created_at: string
  last_used_at: string | null
}

export interface ApiKeyCreated extends ApiKey {
  key: string
}

export interface AnalysisRun {
  id: number
  source: string
  status: string
  risk_score: number
  risk_level: RiskLevel
  provider: string | null
  model: string | null
  prompt_version: string
  policy_version: string
  latency_ms: number | null
  created_at: string
}

export interface EvaluationLabel {
  content_record_id: number
  expected_level: RiskLevel
  category: string | null
  reason: string | null
  operator_id: number | null
  updated_at: string
}

export interface EvaluationSummary {
  labeled: number
  evaluated: number
  skipped: number
  accuracy: number | null
  precision_high: number | null
  recall_high: number | null
  false_positives: number
  false_negatives: number
  confusion: Record<RiskLevel, Record<RiskLevel, number>>
  by_category: Record<string, { total: number; correct: number }>
}

export interface ReviewEvent {
  id: number
  version: number
  actor: string
  previous_status: string
  status: string
  comment: string | null
  created_at: string
}

export const api = {
  health: () => get<{ status: string }>("/health"),

  login: async (email: string, password: string, role: "operator" | "client" = "operator"): Promise<void> => {
    const res = await fetch(role === "client" ? "/auth/login" : "/auth/operator/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? "로그인 실패")
    }
    const data = await res.json()
    setToken(data.access_token)
  },

  signup: async (name: string, email: string, password: string): Promise<void> => {
    const res = await fetch("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? "회원가입 실패")
    }
    const data = await res.json()
    setToken(data.access_token)
  },

  logout: () => {
    clearToken()
    window.location.href = "/login"
  },

  // 클라이언트 자신의 API 키 관리
  getMyKeys: () => get<ApiKey[]>("/auth/keys"),
  getMyDashboard: () => get<ClientDashboard>("/auth/dashboard"),
  getMyContents: (offset = 0, search = "") => getPaginated<Content>("/auth/contents", { limit: "20", offset: String(offset), search }),
  getMyWebhooks: () => get<ClientWebhook[]>("/auth/webhooks"),
  getClients: () => get<{ id: number; name: string }[]>("/admin/clients"),
  getPolicy: (clientId: number) => get<CustomerPolicy>(`/api/policies/${clientId}`),
  savePolicy: async (clientId: number, body: Pick<CustomerPolicy, "category_min_levels" | "review_categories" | "trigger_score"> & { expected_version: number }): Promise<CustomerPolicy> => {
    const response = await authenticatedFetch(`/api/policies/${clientId}`, { method: "PUT", headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body) })
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
    return response.json()
  },
  previewPolicy: (clientId: number, body: Pick<CustomerPolicy, "category_min_levels" | "review_categories" | "trigger_score"> & { expected_version: number }) => post<PolicyPreview>(`/api/policies/${clientId}/preview`, body),
  previewBatch: async (file: File): Promise<BatchPreview> => {
    const form = new FormData(); form.append("file", file)
    const response = await authenticatedFetch("/api/batches/preview", { method: "POST", headers: authHeaders(), body: form })
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
    return response.json()
  },
  submitBatch: async (file: File, contentIdColumn: string, textColumn: string): Promise<{ id: string; accepted: number; skipped: number; errors: { row: number; reason: string }[] }> => {
    const form = new FormData(); form.append("file", file); form.append("content_id_column", contentIdColumn); form.append("text_column", textColumn)
    const response = await authenticatedFetch("/api/batches", { method: "POST", headers: authHeaders(), body: form })
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
    return response.json()
  },
  listBatches: () => get<BatchImport[]>("/api/batches"),
  createMyKey: async (name: string): Promise<ApiKeyCreated> => {
    const res = await authenticatedFetch("/auth/keys", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ name }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? `${res.status}`)
    }
    return res.json()
  },
  revokeMyKey: async (keyId: number): Promise<void> => {
    const res = await authenticatedFetch(`/auth/keys/${keyId}`, {
      method: "DELETE",
      headers: authHeaders(),
    })
    if (!res.ok) throw new Error(`${res.status}`)
  },

  getStats: () => get<Stats>("/api/stats"),
  getContents: (params?: { status?: string; risk_level?: string; sort_by?: string; search?: string; limit?: number; offset?: number }) => {
    const p: Record<string, string> = {}
    if (params?.status)     p.status     = params.status
    if (params?.risk_level) p.risk_level = params.risk_level
    if (params?.sort_by)    p.sort_by    = params.sort_by
    if (params?.search)     p.search     = params.search
    if (params?.limit  != null) p.limit  = String(params.limit)
    if (params?.offset != null) p.offset = String(params.offset)
    return getPaginated<Content>("/api/contents", p)
  },
  getContent: (id: string, recordId: number) => get<Content>(`/api/contents/${encodeURIComponent(id)}`, { record_id: String(recordId) }),
  getPredictions: (id: string, recordId: number) => get<ModelPrediction[]>(`/api/contents/${encodeURIComponent(id)}/predictions`, { record_id: String(recordId) }),
  getAnalysisRuns: (content: Content) => get<AnalysisRun[]>(`/api/contents/${encodeURIComponent(content.content_id)}/analyses`, { record_id: String(content.id) }),
  getEvaluationSummary: () => get<EvaluationSummary>("/api/evaluations/summary"),
  getEvaluationLabel: (recordId: number) => get<EvaluationLabel>(`/api/evaluations/labels/${recordId}`),
  listJobs: () => get<AnalysisJob[]>("/api/jobs"),
  submitJob: (content_id: string, text: string) => post<AnalysisJob>("/api/jobs/analyze", { content_id, text }),
  reanalyze: (content: Content) => post<AnalysisJob>(`/api/contents/${encodeURIComponent(content.content_id)}/reanalyze?record_id=${content.id}`, {}),
  retryJob: (id: string) => post<AnalysisJob>(`/api/jobs/${encodeURIComponent(id)}/retry`, {}),
  cancelJob: (id: string) => post<AnalysisJob>(`/api/jobs/${encodeURIComponent(id)}/cancel`, {}),
  putEvaluationLabel: async (recordId: number, body: { expected_level: RiskLevel; category: string | null; reason: string | null }): Promise<EvaluationLabel> => {
    const response = await authenticatedFetch(`/api/evaluations/labels/${recordId}`, {
      method: "PUT", headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body),
    })
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
    return response.json()
  },
  analyze: (content_id: string, text: string) =>
    post<Content>("/api/analyze", { content_id, text }),
  review: (content: Content, action: ReviewAction, comment?: string) =>
    post<Content>(`/api/reviews/${encodeURIComponent(content.content_id)}?record_id=${content.id}`, { action, comment: comment || null, expected_version: content.review_version }),
  reviewHistory: (content: Content) => get<ReviewEvent[]>(`/api/reviews/${encodeURIComponent(content.content_id)}/history`, { record_id: String(content.id) }),
  deleteContent: async (content: Content): Promise<void> => {
    const res = await authenticatedFetch(`/api/contents/${encodeURIComponent(content.content_id)}?record_id=${content.id}`, {
      method: "DELETE",
      headers: authHeaders(),
    })
    if (!res.ok) throw new Error(`${res.status}`)
  },
}
