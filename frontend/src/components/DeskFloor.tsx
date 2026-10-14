import type { AgentName } from '../api'
import { PERSONAS, TOOL_LABEL, type DeskState } from '../agents'

const STATUS_LABEL: Record<DeskState['status'], string> = {
  idle: 'At desk',
  thinking: 'Thinking',
  tool: 'Working',
  asking: 'Waiting on a teammate',
  done: 'Done',
  error: 'Stuck',
}

function Desk({ agent, state, live, hasRun, wide }: { agent: AgentName; state: DeskState; live: boolean; hasRun: boolean; wide?: boolean }) {
  const p = PERSONAS[agent]
  const active = live && (state.status === 'thinking' || state.status === 'tool' || state.status === 'asking')
  const benched = hasRun && !live && !state.involved
  const standingBy = live && !state.involved
  return (
    <article
      className={`desk desk--${state.status} ${active ? 'desk--active' : ''} ${wide ? 'desk--wide' : ''} ${
        benched ? 'desk--benched' : ''
      }`}
      style={{ '--agent': p.color, '--agent-tint': p.tint } as React.CSSProperties}
      aria-label={`${p.role} desk`}
    >
      <div className="desk__top">
        <div className="desk__avatar" aria-hidden>
          <span>{p.icon}</span>
          {active && <i className="desk__ring" />}
        </div>
        <div className="nameplate">
          <strong>{p.name}</strong>
          <span>{p.role}</span>
        </div>
        <span className={`lamp lamp--${state.status}`} title={STATUS_LABEL[state.status]}>
          <i />
          {STATUS_LABEL[state.status]}
        </span>
      </div>
      <div className="bubble" aria-live={active ? 'polite' : 'off'}>
        {state.status === 'thinking' && live && (
          <span className="dots" aria-label="thinking">
            <i />
            <i />
            <i />
          </span>
        )}
        <p>{benched ? 'Not needed on this ticket.' : standingBy ? 'Standing by in case I’m called…' : state.line}</p>
        {state.asking.length > 0 && (
          <div className="bubble__handoff">
            {state.asking.map((a) => (
              <span key={a} className="chip" style={{ '--chip': PERSONAS[a].color } as React.CSSProperties}>
                → {PERSONAS[a].icon} {PERSONAS[a].role}
              </span>
            ))}
          </div>
        )}
      </div>
      <footer className="desk__foot">
        {state.tools.length ? (
          state.tools.map((t) => (
            <span key={t} className="tool-chip">
              {TOOL_LABEL[t] ?? t}
            </span>
          ))
        ) : (
          <span className="desk__motto">{p.motto}</span>
        )}
      </footer>
    </article>
  )
}

export function DeskFloor({ states, live, title }: { states: Record<AgentName, DeskState>; live: boolean; title: string }) {
  const hasRun = Object.values(states).some((s) => s.involved)
  return (
    <section className="floor" aria-label="Agent desks">
      <h2 className="section-title">
        <span>The desks</span>
        <small>{title}</small>
      </h2>
      <div className="floor__boss">
        <Desk agent="boss" state={states.boss} live={live} hasRun={hasRun} wide />
      </div>
      <div className="floor__grid">
        {(['inventory', 'accounting', 'facilities', 'customer_service'] as AgentName[]).map((a) => (
          <Desk key={a} agent={a} state={states[a]} live={live} hasRun={hasRun} />
        ))}
      </div>
    </section>
  )
}
