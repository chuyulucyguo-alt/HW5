import type { Ticket } from '../api'

const PIN_COLORS = ['#c0392b', '#2e6fb7', '#d4a017', '#2f8f5b']
const TILTS = [-2.2, 1.6, -1.1, 2]

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price request',
}

function stamp(t: Ticket): { text: string; cls: string } {
  if (t.state === 'working') return { text: 'Team on it', cls: 'stamp--working' }
  if (t.state === 'resolved') return { text: 'Resolved', cls: 'stamp--resolved' }
  return { text: 'Open', cls: 'stamp--open' }
}

function time(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function latestNote(notes: string | null): string | null {
  if (!notes) return null
  const lines = notes.split('\n').filter(Boolean)
  return lines[lines.length - 1].replace(/^\[\d{4}-\d{2}-\d{2}\]\s*/, '')
}

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  busy: boolean
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

export function Corkboard({ tickets, selectedId, busy, onSelect, onRun }: Props) {
  return (
    <section className="corkboard" aria-label="Ticket board">
      <h2 className="corkboard__title">
        <span>Ticket board</span>
        <small>{tickets.filter((t) => t.state !== 'resolved').length} still open</small>
      </h2>
      <div className="corkboard__pins">
        {tickets.map((t, i) => {
          const st = stamp(t)
          const selected = t.id === selectedId
          const note = latestNote(t.notes)
          return (
            <article
              key={t.id}
              className={`ticket ${selected ? 'ticket--selected' : ''} ticket--${t.state}`}
              style={{ '--tilt': `${TILTS[i % TILTS.length]}deg`, '--pin': PIN_COLORS[i % PIN_COLORS.length] } as React.CSSProperties}
              onClick={() => onSelect(t.id)}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect(t.id)}
              tabIndex={0}
              role="button"
              aria-pressed={selected}
              aria-label={`Ticket ${t.id}: ${t.subject}`}
            >
              <span className="ticket__pin" aria-hidden />
              <header className="ticket__head">
                <span className="ticket__no">No. {t.id}</span>
                <span className="ticket__type">{TYPE_LABEL[t.type] ?? t.type}</span>
              </header>
              <h3 className="ticket__subject">{t.subject}</h3>
              <dl className="ticket__meta">
                <div>
                  <dt>From</dt>
                  <dd>{t.requester}</dd>
                </div>
                {t.sku && (
                  <div>
                    <dt>Item</dt>
                    <dd>
                      {t.qty} × {t.sku} · {t.size}
                    </dd>
                  </div>
                )}
                {t.lease_id !== null && (
                  <div>
                    <dt>Lease</dt>
                    <dd>#{t.lease_id}</dd>
                  </div>
                )}
                {t.invoice_id !== null && (
                  <div>
                    <dt>Invoice</dt>
                    <dd>#{t.invoice_id}</dd>
                  </div>
                )}
                <div>
                  <dt>In</dt>
                  <dd>{time(t.created_at)}</dd>
                </div>
              </dl>
              {note && <p className="ticket__note">“{note}”</p>}
              <div className={`stamp ${st.cls}`}>{st.text}</div>
              <footer className="ticket__foot">
                <span className="ticket__status">
                  {t.status.replaceAll('_', ' ')}
                  {t.pending_approvals > 0 && (
                    <em className="ticket__sign"> · {t.pending_approvals} awaiting your signature</em>
                  )}
                </span>
                <button
                  className="btn btn--ink"
                  disabled={busy}
                  onClick={(e) => {
                    e.stopPropagation()
                    onRun(t.id)
                  }}
                  title={busy ? 'The team is busy with another ticket' : 'Send this ticket to the agent team'}
                >
                  {t.state === 'working' ? 'Working…' : t.state === 'resolved' ? 'Run again' : 'Send to the team →'}
                </button>
              </footer>
            </article>
          )
        })}
      </div>
    </section>
  )
}
