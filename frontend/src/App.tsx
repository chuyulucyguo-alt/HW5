import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { API_BASE, api, money, type AgentEvent, type Approval, type Cash, type Ticket } from './api'
import { deskStates } from './agents'
import { CashDrawer } from './components/CashDrawer'
import { Corkboard } from './components/Corkboard'
import { DeskFloor } from './components/DeskFloor'
import { DeskLog } from './components/DeskLog'
import { RunReport } from './components/RunReport'
import { SignatureTray } from './components/SignatureTray'

const SLOW_POLL = 4000 // tickets, cash, approvals
const FAST_POLL = 1200 // agent events while a run is live

interface Toast {
  id: number
  text: string
  tone: 'ok' | 'warn' | 'info'
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [cash, setCash] = useState<Cash | null>(null)
  const [lastDelta, setLastDelta] = useState<number | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [offline, setOffline] = useState<string | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [signer, setSigner] = useState(() => localStorage.getItem('desk.signer') ?? '')

  const viewRun = useRef<string | null>(null)
  const lastSeq = useRef(-1)
  const prevStates = useRef<Record<number, Ticket['state']>>({})
  const prevBalance = useRef<number | null>(null)

  const toast = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, text, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000)
  }, [])

  // ---------- slow refresh: tickets, cash, approvals ----------
  const refresh = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals('all')])
      setOffline(null)
      setTickets(t)
      setApprovals(a)
      if (prevBalance.current !== null && c.balance !== prevBalance.current) {
        setLastDelta(c.balance - prevBalance.current)
      }
      prevBalance.current = c.balance
      setCash(c)
      // a ticket that just went working -> resolved: the run finished
      t.forEach((x) => {
        const before = prevStates.current[x.id]
        if (before === 'working' && x.state === 'resolved') {
          toast(`Ticket ${x.id} resolved by the team${x.pending_approvals ? `, with ${x.pending_approvals} item(s) for your signature` : ''}.`, 'ok')
        }
        prevStates.current[x.id] = x.state
      })
      setSelectedId((cur) => cur ?? t[0]?.id ?? null)
    } catch (e) {
      setOffline((e as Error).message)
    }
  }, [toast])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, SLOW_POLL)
    return () => clearInterval(id)
  }, [refresh])

  const selected = tickets.find((t) => t.id === selectedId) ?? null
  const running = tickets.find((t) => t.state === 'working') ?? null
  const runId = selected?.running_run_id ?? selected?.last_run?.run_id ?? null
  const live = !!selected?.running_run_id

  // ---------- events for the run being viewed ----------
  useEffect(() => {
    if (viewRun.current !== runId) {
      viewRun.current = runId
      lastSeq.current = -1
      setEvents([])
    }
    if (!runId) return
    let stop = false
    const pull = async () => {
      try {
        const res = await api.events({ run_id: runId, after: lastSeq.current, limit: 500 })
        if (stop || viewRun.current !== runId) return
        if (res.events.length) {
          lastSeq.current = res.events[res.events.length - 1].seq
          setEvents((prev) => [...prev, ...res.events])
        }
      } catch {
        /* the slow poll reports offline */
      }
    }
    pull()
    const id = live ? setInterval(pull, FAST_POLL) : undefined
    return () => {
      stop = true
      if (id) clearInterval(id)
    }
  }, [runId, live])

  // keep polling tickets quickly while a run is live, so 'resolved' appears right when it ends
  useEffect(() => {
    if (!running) return
    const id = setInterval(refresh, FAST_POLL * 2)
    return () => clearInterval(id)
  }, [running, refresh])

  const states = useMemo(() => deskStates(events), [events])

  // ---------- actions ----------
  const runTicket = async (id: number) => {
    setSelectedId(id)
    try {
      await api.runTicket(id)
      toast(`Ticket ${id} handed to the Boss.`, 'info')
      await refresh()
    } catch (e) {
      toast((e as Error).message, 'warn')
    }
  }

  const decide = async (a: Approval, decision: 'approve' | 'reject') => {
    try {
      const res = decision === 'approve' ? await api.approve(a.id, signer.trim()) : await api.reject(a.id, signer.trim())
      toast(
        decision === 'approve' ? `Signed. ${money(a.amount)} out; checking is now ${money(res.checking.balance)}.` : `Voided request #${a.id}.`,
        decision === 'approve' ? 'ok' : 'info',
      )
      await refresh()
    } catch (e) {
      toast((e as Error).message, 'warn')
    }
  }

  const reset = async () => {
    if (!window.confirm('Start a fresh day? This restores the original database (tickets, cash, stock). The audit trail is kept.')) return
    try {
      await api.reset()
      prevBalance.current = null
      setLastDelta(null)
      setEvents([])
      toast('Fresh day. Database restored to the original.', 'info')
      await refresh()
    } catch (e) {
      toast((e as Error).message, 'warn')
    }
  }

  const onSigner = (v: string) => {
    setSigner(v)
    localStorage.setItem('desk.signer', v)
  }

  const pending = approvals.filter((a) => a.status === 'pending')
  const decided = approvals.filter((a) => a.status !== 'pending')
  const floorTitle = !selected
    ? ''
    : live
      ? `working ticket ${selected.id} live`
      : runId
        ? `last run on ticket ${selected.id}`
        : `ticket ${selected.id} hasn't been sent yet`

  return (
    <div className="desk-app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden>
            CC
          </span>
          <div>
            <h1>Campus Customs</h1>
            <p>Front desk · Chapel Street, New Haven</p>
          </div>
        </div>
        <div className="topbar__right">
          <span className="calendar" title="The shop's date from the database">
            <small>Shop date</small>
            {cash?.today ?? '…'}
          </span>
          <span className={`conn ${offline ? 'conn--off' : ''}`} title={offline ?? 'Connected to the backend'}>
            <i />
            {offline ? 'Backend offline' : running ? `Team on ticket ${running.id}` : 'Team ready'}
          </span>
          <button className="btn btn--paper" onClick={reset} disabled={!!running}>
            ↺ Fresh day
          </button>
        </div>
      </header>

      {offline && (
        <div className="banner">
          Can't reach the backend at <code>{API_BASE}</code> ({offline}). Start it from <code>backend/</code> with{' '}
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <main className="layout">
        <aside className="layout__board">
          <Corkboard tickets={tickets} selectedId={selectedId} busy={!!running} onSelect={setSelectedId} onRun={runTicket} />
        </aside>

        <div className="layout__main">
          <DeskFloor states={states} live={live} title={floorTitle} />
          {selected && <RunReport events={events} ticketId={selected.id} live={live} />}
          <DeskLog events={events} live={live} />
        </div>

        <aside className="layout__side">
          <CashDrawer cash={cash} pending={pending} lastDelta={lastDelta} />
          <SignatureTray pending={pending} decided={decided} signer={signer} onSigner={onSigner} onDecide={decide} />
        </aside>
      </main>

      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.tone}`}>
            {t.text}
          </div>
        ))}
      </div>
    </div>
  )
}
