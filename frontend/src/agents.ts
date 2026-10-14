// The five desks. Each agent has its own color, icon, and personality.
import type { AgentEvent, AgentName, ToolUse } from './api'

export interface Persona {
  key: AgentName
  name: string // nameplate
  role: string
  icon: string
  color: string // ink color for the nameplate and bubble accent
  tint: string // soft paper tint for the desk
  motto: string
  idle: string // what they say when nothing is happening
  done: string // short sign-off before their summary
}

export const PERSONAS: Record<AgentName, Persona> = {
  boss: {
    key: 'boss',
    name: 'Margaret Hale',
    role: 'The Boss',
    icon: '🧭',
    color: '#1f3a68',
    tint: '#e9eef7',
    motto: 'Calm, decisive. Sees the whole shop.',
    idle: 'Desk is quiet. Pick a ticket and I will route it.',
    done: 'Here is where we landed.',
  },
  inventory: {
    key: 'inventory',
    name: 'Theo Park',
    role: 'Inventory',
    icon: '📦',
    color: '#4d6b22',
    tint: '#eef3e2',
    motto: 'Counts twice. Knows every aisle.',
    idle: 'Aisles A through D, all counted.',
    done: 'Counts are in.',
  },
  accounting: {
    key: 'accounting',
    name: 'Priya Desai',
    role: 'Accounting',
    icon: '🧮',
    color: '#0f6a6e',
    tint: '#e3f1f0',
    motto: 'Precise to the cent. Nothing leaves without a signature.',
    idle: 'Ledger balanced. Drawer closed.',
    done: 'Numbers reconciled.',
  },
  facilities: {
    key: 'facilities',
    name: 'Gus Moreno',
    role: 'Facilities',
    icon: '🔑',
    color: '#a2491f',
    tint: '#f8ebe2',
    motto: 'Keeps the lights on and the landlord happy.',
    idle: 'Lights on, doors open, lease in the drawer.',
    done: 'Building side is sorted.',
  },
  customer_service: {
    key: 'customer_service',
    name: 'Bea Lindqvist',
    role: 'Customer Service',
    icon: '💬',
    color: '#9b3a62',
    tint: '#f8e7ee',
    motto: 'Warm, upbeat, a little Bulldog spirit.',
    idle: 'Ready to make somebody’s day!',
    done: 'Reply drafted!',
  },
}

export const ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

const s = (v: unknown) => (v === undefined || v === null ? '' : String(v))

/** Plain-language description of an MCP tool call, in the agent's voice. */
export function describeTool(t: ToolUse): string {
  const a = t.args ?? {}
  switch (t.tool) {
    case 'list_open_tickets':
      return 'Scanning the open tickets'
    case 'get_ticket':
      return `Pulling ticket #${s(a.ticket_id)} and everything it links to`
    case 'check_stock_and_price':
      return `Counting ${s(a.sku)}${a.size ? ` · size ${s(a.size)}` : ''}`
    case 'get_cash_and_bills':
      return 'Opening the cash drawer and the bill folder'
    case 'list_vendors':
      return 'Flipping through the vendor cards'
    case 'quote_bulk_price':
      return `Pricing ${s(a.qty)} × ${s(a.sku)} at ${s(a.discount_pct ?? 0)}% off`
    case 'update_ticket':
      return `Marking ticket #${s(a.ticket_id)} “${s(a.status).replaceAll('_', ' ')}”`
    case 'adjust_inventory':
      return `Adjusting ${s(a.sku)} ${s(a.size)} by ${s(a.change)}`
    case 'prepare_payment':
      return `Drafting ${a.kind === 'invoice' ? `an invoice #${s(a.ref_id)}` : 'a rent'} payment for your signature`
    case 'prepare_purchase':
      return `Drafting a restock order: ${s(a.qty)} × ${s(a.sku)} ${s(a.size)}`
    case 'list_approvals':
      return 'Checking the signature tray'
    default:
      return `Using ${t.tool}`
  }
}

export const TOOL_LABEL: Record<string, string> = {
  list_open_tickets: 'open tickets',
  get_ticket: 'ticket file',
  check_stock_and_price: 'stock & price',
  get_cash_and_bills: 'cash & bills',
  list_vendors: 'vendors',
  quote_bulk_price: 'bulk quote',
  update_ticket: 'ticket status',
  adjust_inventory: 'stock change',
  prepare_payment: 'payment draft',
  prepare_purchase: 'restock draft',
  list_approvals: 'signature tray',
}

export type DeskStatus = 'idle' | 'thinking' | 'tool' | 'asking' | 'done' | 'error'

export interface DeskState {
  status: DeskStatus
  line: string
  tools: string[] // tool names used this run, in order, unique
  askedBy: AgentName | 'you' | null
  asking: AgentName[]
  involved: boolean
  lastSeq: number
}

/** Who sent a delegated request, from the "Request from X:" prefix written by ask_teammate. */
function requester(prompt: string | null): AgentName | 'you' {
  const m = prompt?.match(/^Request from ([a-z ]+):/i)
  if (!m) return 'you'
  return m[1].trim().replace(' ', '_') as AgentName
}

function firstLine(text: string | null, max = 180): string {
  const t = (text ?? '').replace(/^Request from [a-z ]+:\s*/i, '').replace(/\s+/g, ' ').trim()
  return t.length > max ? `${t.slice(0, max - 1)}…` : t
}

/** Fold one run's events into what each desk is doing right now. */
export function deskStates(events: AgentEvent[]): Record<AgentName, DeskState> {
  const out = Object.fromEntries(
    ORDER.map((k) => [
      k,
      { status: 'idle', line: PERSONAS[k].idle, tools: [], askedBy: null, asking: [], involved: false, lastSeq: -1 },
    ]),
  ) as unknown as Record<AgentName, DeskState>

  for (const e of events) {
    if (!e.agent || !(e.agent in out)) continue
    const d = out[e.agent]
    d.involved = true
    d.lastSeq = e.seq
    switch (e.kind) {
      case 'agent_start': {
        const from = requester(e.said)
        d.askedBy = from
        d.status = 'thinking'
        d.asking = []
        d.line = from === 'you' ? `On it: ${firstLine(e.said, 120)}` : `${PERSONAS[from]?.role ?? from} asked: “${firstLine(e.said, 150)}”`
        break
      }
      case 'model_response': {
        const tools = e.tools.map((t) => t.tool)
        tools.forEach((t) => !d.tools.includes(t) && d.tools.push(t))
        if (e.delegated_to.length) {
          d.status = 'asking'
          d.asking = e.delegated_to
          d.line = `Asking ${e.delegated_to.map((a) => PERSONAS[a]?.role ?? a).join(' and ')}…`
          if (e.tools.length) d.line += ` (and ${describeTool(e.tools[0]).toLowerCase()})`
        } else if (e.tools.length) {
          d.status = 'tool'
          d.line = e.tools.map(describeTool).join(' · ')
        } else if (e.said) {
          d.status = 'thinking'
          d.line = firstLine(e.said)
        }
        break
      }
      case 'tool_results':
        d.status = 'thinking'
        d.asking = []
        d.line = `Reading the ${e.tools.map((t) => TOOL_LABEL[t.tool] ?? t.tool).join(', ')}…`
        break
      case 'final':
        d.status = 'done'
        d.asking = []
        d.line = firstLine(e.said, 220)
        break
      case 'delegation_refused':
        d.line = e.said ?? 'Hand-off refused.'
        break
      case 'error':
        d.status = 'error'
        d.line = firstLine(e.said)
        break
    }
  }
  return out
}
