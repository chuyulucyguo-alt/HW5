import { useState } from 'react'
import { money, type AgentName, type Approval } from '../api'
import { PERSONAS } from '../agents'

function title(a: Approval) {
  if (a.kind === 'rent') return `Rent · lease #${a.ref_id}`
  if (a.kind === 'invoice') return `Invoice #${a.ref_id}`
  return `Restock · ${a.qty} × ${a.sku} ${a.size}`
}

interface Props {
  pending: Approval[]
  decided: Approval[]
  signer: string
  onSigner: (name: string) => void
  onDecide: (a: Approval, decision: 'approve' | 'reject') => Promise<void>
}

export function SignatureTray({ pending, decided, signer, onSigner, onDecide }: Props) {
  const [working, setWorking] = useState<number | null>(null)
  const canSign = signer.trim().length > 1

  const decide = async (a: Approval, d: 'approve' | 'reject') => {
    setWorking(a.id)
    try {
      await onDecide(a, d)
    } finally {
      setWorking(null)
    }
  }

  return (
    <section className="tray" aria-label="Payments waiting for approval">
      <header className="tray__head">
        <span>Needs your signature</span>
        <small>{pending.length ? `${pending.length} waiting` : 'all clear'}</small>
      </header>

      <label className="signer">
        <span>Signing as</span>
        <input
          value={signer}
          onChange={(e) => onSigner(e.target.value)}
          placeholder="Your name"
          aria-label="Your name for signing approvals"
        />
      </label>

      {pending.length === 0 && (
        <p className="tray__empty">
          No payments or orders waiting. Agents can only <em>draft</em> them; nothing moves until you sign here.
        </p>
      )}

      <div className="checks">
        {pending.map((a) => {
          const by = PERSONAS[a.requested_by as AgentName]
          return (
            <article key={a.id} className="check">
              <header className="check__head">
                <span className="check__bank">Campus Customs · {a.account}</span>
                <span className="check__no">No. {String(a.id).padStart(4, '0')}</span>
              </header>
              <div className="check__pay">
                <span>Pay to</span>
                <strong>{a.payee ?? '—'}</strong>
                <b className="check__amount">{money(a.amount)}</b>
              </div>
              <p className="check__memo">
                <span>Memo</span> {title(a)}
                {a.ticket_id ? ` · ticket ${a.ticket_id}` : ''}
              </p>
              <p className="check__reason">{a.reason}</p>
              <footer className="check__foot">
                <span className="check__by" style={{ color: by?.color }}>
                  drafted by {by ? `${by.icon} ${by.role}` : a.requested_by}
                </span>
                <div className="check__actions">
                  <button className="btn btn--ghost" disabled={!canSign || working === a.id} onClick={() => decide(a, 'reject')}>
                    Void
                  </button>
                  <button
                    className="btn btn--sign"
                    disabled={!canSign || working === a.id}
                    onClick={() => decide(a, 'approve')}
                    title={canSign ? '' : 'Type your name above to sign'}
                  >
                    {working === a.id ? 'Signing…' : `Sign & ${a.kind === 'purchase' ? 'order' : 'pay'}`}
                  </button>
                </div>
              </footer>
              {!canSign && <span className="check__hint">Type your name above to sign</span>}
            </article>
          )
        })}
      </div>

      {decided.length > 0 && (
        <details className="tray__history">
          <summary>Signed &amp; voided ({decided.length})</summary>
          <ul>
            {decided.map((a) => (
              <li key={a.id} className={a.status}>
                <span>{a.status === 'approved' ? '✔' : '✕'}</span> {title(a)}, {money(a.amount)}, {a.status} by {a.decided_by}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
