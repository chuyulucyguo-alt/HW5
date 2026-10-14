import { useEffect, useRef, useState } from 'react'
import { money, type Approval, type Cash } from '../api'

const CUSHION = 500

/** Tween a number toward its new value so a drop in cash is visible, not just swapped.
 * The first real value appears instantly; only later changes animate. */
function useTween(target: number | null, ms = 1100) {
  const [value, setValue] = useState(target ?? 0)
  const from = useRef<number | null>(target)
  useEffect(() => {
    if (target === null) return
    if (from.current === null) {
      from.current = target
      setValue(target)
      return
    }
    const start = performance.now()
    const begin = from.current
    let raf = 0
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / ms)
      const eased = 1 - Math.pow(1 - k, 3)
      setValue(begin + (target - begin) * eased)
      if (k < 1) raf = requestAnimationFrame(step)
      else from.current = target
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return value
}

export function CashDrawer({ cash, pending, lastDelta }: { cash: Cash | null; pending: Approval[]; lastDelta: number | null }) {
  const balance = cash?.balance ?? 0
  const shown = useTween(cash ? cash.balance : null)
  const owedPending = pending.reduce((sum, a) => sum + a.amount, 0)
  const after = balance - owedPending
  const pct = (n: number) => `${Math.max(0, Math.min(100, (n / Math.max(balance, CUSHION * 2, 1)) * 100))}%`

  return (
    <section className="drawer" aria-label="Checking balance">
      <header className="drawer__head">
        <span>Cash drawer</span>
        <small>checking · as of {cash?.as_of ?? '…'}</small>
      </header>
      <div className={`drawer__amount ${lastDelta && lastDelta < 0 ? 'drawer__amount--drop' : ''}`} key={balance}>
        {cash ? money(shown) : '—'}
        {lastDelta !== null && lastDelta !== 0 && (
          <span className={`drawer__delta ${lastDelta < 0 ? 'neg' : 'pos'}`}>
            {lastDelta < 0 ? '−' : '+'}
            {money(Math.abs(lastDelta))}
          </span>
        )}
      </div>
      <div className="drawer__bar" aria-hidden>
        <i className="drawer__fill" style={{ width: pct(balance) }} />
        {owedPending > 0 && <i className="drawer__pending" style={{ left: pct(after), width: `calc(${pct(balance)} - ${pct(after)})` }} />}
        <i className="drawer__cushion" style={{ left: pct(CUSHION) }} title="$500 cushion" />
      </div>
      <dl className="drawer__lines">
        <div>
          <dt>Waiting for your signature</dt>
          <dd>{owedPending ? money(owedPending) : 'nothing'}</dd>
        </div>
        <div className={after < CUSHION ? 'warn' : ''}>
          <dt>If you sign everything</dt>
          <dd>{money(after)}</dd>
        </div>
      </dl>
      {owedPending > 0 && after < CUSHION && (
        <p className="drawer__warn">That would dip under the $500 cushion. Sign what matters most first.</p>
      )}
    </section>
  )
}
