// Typed client for the FastAPI routes in backend/main.py.
// The backend runs at http://localhost:8000 (override with VITE_API_BASE in frontend/.env).

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const BASE = API_BASE.replace(/\/$/, '')

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string // database status: open | in_progress | waiting_on_approval | resolved
  notes: string | null
  created_at: string
  state: 'open' | 'working' | 'resolved' // board view
  last_run: { run_id: string; finished_at: string } | null
  running_run_id: string | null
  pending_approvals: number
}

export interface RunInfo {
  run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'failed'
  started_at: string
  finished_at: string | null
  result: { output: BossBrief; delegations: Delegation[]; requests_used: number; tool_calls_used: number } | null
  error: string | null
}

export interface Delegation {
  depth: number
  from_agent: AgentName
  to_agent: AgentName
  request: string
  result_summary: string | null
  refused: string | null
}

export interface ToolUse {
  tool: string
  args?: Record<string, unknown>
  result?: unknown
}

export interface AgentEvent {
  seq: number
  ts: string
  run_id: string | null
  ticket_id: number | null
  agent: AgentName | null
  depth: number | null
  kind:
    | 'team_run_start'
    | 'team_run_end'
    | 'agent_start'
    | 'model_response'
    | 'tool_results'
    | 'final'
    | 'delegation_refused'
    | 'error'
    | 'human_decision'
    | 'database_reset'
  said: string | null
  tools: ToolUse[]
  delegated_to: AgentName[]
  output?: AgentReport | BossBrief
  detail?: Record<string, unknown>
}

export interface ProposedAction {
  action: string
  owner: AgentName
  tool: string | null
  needs_human_approval: boolean
  reason: string
}

export interface AgentReport {
  agent: AgentName
  summary: string
  facts?: { statement: string; source_tool: string }[]
  actions_taken?: string[]
  proposed_actions?: ProposedAction[]
  customer_message?: string | null
  questions_for_human?: string[]
}

export interface TicketPlan {
  ticket_id: number
  owner: AgentName
  consulted: AgentName[]
  finding: string
  plan: string
  recommended_status: string
  needs_human_approval: boolean
  approval_request: string | null
}

export interface BossBrief {
  summary: string
  tickets?: TicketPlan[]
  cash_position?: string | null
  approvals_needed?: string[]
  actions_taken?: string[]
}

export interface Approval {
  id: number
  kind: 'invoice' | 'rent' | 'purchase'
  ref_id: number | null
  ticket_id: number | null
  vendor_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  amount: number
  account: string
  reason: string
  requested_by: string
  resolves_ticket: boolean
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  decided_by: string | null
  decided_at: string | null
  result: string | null
  payee: string | null
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  today: string
}

export interface Decided {
  ok: boolean
  message: string
  checking: Cash
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* not JSON */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  tickets: () => call<Ticket[]>('/api/tickets'),
  runTicket: (id: number) => call<RunInfo>(`/api/tickets/${id}/run`, { method: 'POST' }),
  run: (runId: string) => call<RunInfo>(`/api/runs/${runId}`),
  events: (params: { after?: number; limit?: number; run_id?: string; ticket_id?: number }) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v !== undefined && q.set(k, String(v)))
    return call<{ last_seq: number; events: AgentEvent[] }>(`/api/events?${q}`)
  },
  approvals: (status: 'pending' | 'approved' | 'rejected' | 'all' = 'pending') =>
    call<Approval[]>(`/api/approvals?status=${status}`),
  approve: (id: number, decided_by: string) =>
    call<Decided>(`/api/approvals/${id}/approve`, { method: 'POST', body: JSON.stringify({ decided_by }) }),
  reject: (id: number, decided_by: string, note = '') =>
    call<Decided>(`/api/approvals/${id}/reject`, { method: 'POST', body: JSON.stringify({ decided_by, note }) }),
  cash: () => call<Cash>('/api/cash'),
  reset: () => call<{ ok: boolean; tickets: Ticket[]; checking: Cash }>('/api/reset', { method: 'POST' }),
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
