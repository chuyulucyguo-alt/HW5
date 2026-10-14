import { useState } from 'react'
import type { AgentEvent, AgentName, AgentReport, BossBrief } from '../api'
import { ORDER, PERSONAS, TOOL_LABEL } from '../agents'

interface AgentSummary {
  agent: AgentName
  summaries: string[]
  tools: Record<string, number>
  asked: AgentName[]
  askedBy: string[]
  customerMessage: string | null
  prepared: string[]
}

function summarize(events: AgentEvent[]): AgentSummary[] {
  const map = new Map<AgentName, AgentSummary>()
  const get = (a: AgentName) => {
    if (!map.has(a)) map.set(a, { agent: a, summaries: [], tools: {}, asked: [], askedBy: [], customerMessage: null, prepared: [] })
    return map.get(a)!
  }
  for (const e of events) {
    if (!e.agent) continue
    const s = get(e.agent)
    if (e.kind === 'model_response') {
      e.tools.forEach((t) => (s.tools[t.tool] = (s.tools[t.tool] ?? 0) + 1))
      e.delegated_to.forEach((a) => !s.asked.includes(a) && s.asked.push(a))
    }
    if (e.kind === 'tool_results') {
      e.tools
        .filter((t) => t.tool === 'prepare_payment' || t.tool === 'prepare_purchase')
        .forEach((t) => {
          const msg = (t.result as { message?: string } | undefined)?.message
          if (msg) s.prepared.push(msg)
        })
    }
    if (e.kind === 'agent_start') {
      const m = e.said?.match(/^Request from ([a-z ]+):/i)
      const from = m ? PERSONAS[m[1].trim().replace(' ', '_') as AgentName]?.role ?? m[1] : 'you'
      if (!s.askedBy.includes(from)) s.askedBy.push(from)
    }
    if (e.kind === 'final' && e.said) {
      s.summaries.push(e.said)
      const out = e.output as AgentReport | undefined
      if (out?.customer_message) s.customerMessage = out.customer_message
    }
  }
  return ORDER.filter((a) => map.has(a)).map((a) => map.get(a)!)
}

export function RunReport({ events, ticketId, live }: { events: AgentEvent[]; ticketId: number; live: boolean }) {
  const agents = summarize(events)
  const bossFinal = [...events].reverse().find((e) => e.kind === 'final' && e.agent === 'boss' && e.depth === 0)
  const brief = bossFinal?.output as BossBrief | undefined
  const end = events.find((e) => e.kind === 'team_run_end')
  const usage = end?.detail?.usage as { requests?: number; tool_calls?: number; input_tokens?: number; output_tokens?: number } | undefined
  const start = events.find((e) => e.kind === 'team_run_start')
  const secs = start && end ? Math.round((+new Date(end.ts) - +new Date(start.ts)) / 1000) : null

  if (!agents.length) return null
  return (
    <section className="report" aria-label="Run report">
      <h2 className="section-title">
        <span>Who did what · ticket {ticketId}</span>
        <small>
          {live
            ? 'still working…'
            : [
                secs !== null && `${Math.floor(secs / 60)}m ${secs % 60}s`,
                usage?.requests !== undefined && `${usage.requests} model calls`,
                usage?.tool_calls !== undefined && `${usage.tool_calls} tool calls`,
                usage?.input_tokens !== undefined && `${Math.round(((usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)) / 1000)}k tokens`,
              ]
                .filter(Boolean)
                .join(' · ')}
        </small>
      </h2>

      {brief && (
        <article className="memo" style={{ '--agent': PERSONAS.boss.color } as React.CSSProperties}>
          <header>
            <span>{PERSONAS.boss.icon} Memo from {PERSONAS.boss.name}</span>
            <small>To: you</small>
          </header>
          <p className="memo__summary">{brief.summary}</p>
          {brief.cash_position && <p className="memo__cash">💵 {brief.cash_position}</p>}
          {!!brief.approvals_needed?.length && (
            <>
              <h4>I need you to decide</h4>
              <ul>
                {brief.approvals_needed.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </>
          )}
        </article>
      )}

      <div className="cards">
        {agents.map((s) => {
          const p = PERSONAS[s.agent]
          return (
            <article key={s.agent} className="index-card" style={{ '--agent': p.color, '--agent-tint': p.tint } as React.CSSProperties}>
              <header>
                <span className="index-card__icon">{p.icon}</span>
                <div>
                  <strong>{p.role}</strong>
                  <small>
                    {s.askedBy.length ? `asked by ${s.askedBy.join(', ')}` : ''}
                    {s.askedBy.length > 1 ? ` (${s.askedBy.length}×)` : ''}
                  </small>
                </div>
              </header>
              {s.agent === 'boss' && brief ? (
                <p className="index-card__summary">
                  Routed it to {s.asked.map((a) => PERSONAS[a].role).join(' and ') || 'nobody (handled it alone)'}, then checked the
                  whole cash picture and wrote the memo above.
                </p>
              ) : s.summaries.length ? (
                <Clamp text={s.summaries[s.summaries.length - 1]} />
              ) : (
                <p className="index-card__summary muted">{live ? 'Still at it…' : 'No final report.'}</p>
              )}
              {s.prepared.length > 0 && (
                <ul className="index-card__prepared">
                  {s.prepared.map((m, i) => (
                    <li key={i}>✍️ {m.split('. ')[0]}.</li>
                  ))}
                </ul>
              )}
              {s.customerMessage && (
                <blockquote className="index-card__reply">
                  <span>Draft reply</span>
                  {s.customerMessage}
                </blockquote>
              )}
              <footer>
                {Object.entries(s.tools).map(([t, n]) => (
                  <span key={t} className="tool-chip">
                    {TOOL_LABEL[t] ?? t}
                    {n > 1 ? ` ×${n}` : ''}
                  </span>
                ))}
                {s.asked.map((a) => (
                  <span key={a} className="chip" style={{ '--chip': PERSONAS[a].color } as React.CSSProperties}>
                    → {PERSONAS[a].role}
                  </span>
                ))}
              </footer>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function Clamp({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const long = text.length > 260
  return (
    <>
      <p className={`index-card__summary ${long && !open ? 'index-card__summary--clamp' : ''}`}>{text}</p>
      {long && (
        <button className="linkish" onClick={() => setOpen(!open)}>
          {open ? 'show less' : 'read the rest'}
        </button>
      )}
    </>
  )
}
