import { useEffect, useRef } from 'react'
import type { AgentEvent } from '../api'
import { describeTool, PERSONAS } from '../agents'

function clock(iso: string) {
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' })
}

function line(e: AgentEvent): { text: string; tone?: string } | null {
  const who = e.agent ? PERSONAS[e.agent] : null
  switch (e.kind) {
    case 'team_run_start':
      return { text: 'Ticket handed to the team.', tone: 'system' }
    case 'team_run_end':
      return { text: e.said === 'ok' ? 'Team finished the run.' : `Run ended: ${e.said}`, tone: 'system' }
    case 'agent_start': {
      const m = e.said?.match(/^Request from ([a-z ]+):\s*([\s\S]*)/i)
      if (!m) return null
      const from = PERSONAS[m[1].trim().replace(' ', '_') as keyof typeof PERSONAS]
      return { text: `${from?.role ?? m[1]} → ${who?.role}: “${m[2].replace(/\s+/g, ' ').slice(0, 220)}”`, tone: 'handoff' }
    }
    case 'model_response': {
      const parts: string[] = []
      if (e.said) parts.push(e.said.replace(/\s+/g, ' ').slice(0, 220))
      e.tools.forEach((t) => parts.push(describeTool(t)))
      if (e.delegated_to.length) parts.push(`asks ${e.delegated_to.map((a) => PERSONAS[a]?.role ?? a).join(' & ')}`)
      return parts.length ? { text: parts.join(' · ') } : null
    }
    case 'final':
      return { text: `✔ ${e.said ?? 'Done.'}`, tone: 'done' }
    case 'delegation_refused':
      return { text: e.said ?? 'Hand-off refused.', tone: 'warn' }
    case 'error':
      return { text: `Problem: ${e.said}`, tone: 'warn' }
    default:
      return null
  }
}

export function DeskLog({ events, live }: { events: AgentEvent[]; live: boolean }) {
  const paper = useRef<HTMLDivElement>(null)
  // follow new entries inside the notebook only (never scroll the whole page)
  useEffect(() => {
    const el = paper.current
    if (live && el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [events.length, live])

  const rows = events.map((e) => ({ e, l: line(e) })).filter((r) => r.l)
  return (
    <section className="log" aria-label="Desk log">
      <h2 className="section-title">
        <span>Desk log</span>
        <small>{live ? 'writing as they work…' : rows.length ? `${rows.length} entries` : 'empty'}</small>
      </h2>
      <div className="log__paper" ref={paper}>
        {rows.length === 0 ? (
          <p className="log__empty">Nothing written yet. Send a ticket to the team and their notes will appear here.</p>
        ) : (
          <ol>
            {rows.map(({ e, l }) => {
              const p = e.agent ? PERSONAS[e.agent] : null
              return (
                <li key={e.seq} className={`log__row log__row--${l!.tone ?? 'say'}`} style={{ '--agent': p?.color ?? '#6b5b4a', '--indent': e.depth ?? 0 } as React.CSSProperties}>
                  <time>{clock(e.ts)}</time>
                  <span className="log__who">{p ? `${p.icon} ${p.role}` : '📌 Desk'}</span>
                  <span className="log__text">{l!.text}</span>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </section>
  )
}
