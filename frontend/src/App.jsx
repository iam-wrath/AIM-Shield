import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const sid = () => Math.random().toString(36).slice(2, 10)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function api(path, body) {
  try {
    const res = await fetch(path, body
      ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
      : undefined)
    const data = await res.json().catch(() => ({}))
    return { ok: res.ok, status: res.status, data }
  } catch (e) {
    return { ok: false, status: 0, data: { error: 'network', detail: String(e) } }
  }
}

const tone = (d) => (d === 'BLOCK' ? 'red' : d === 'WARN' || d === 'REDACT' ? 'amber' : 'green')

function usageText(u) {
  if (!u) return 'quota: …'
  if (u.error) return 'quota: unavailable'
  const pick = (...keys) => keys.map((k) => u[k]).find((v) => typeof v === 'number')
  const used = pick('used_today', 'used', 'requests_today', 'count')
  const limit = pick('daily_limit', 'limit', 'day_limit', 'max')
  const left = pick('remaining', 'remaining_today', 'day_remaining')
  if (used !== undefined && limit !== undefined) return `quota: ${used}/${limit} today`
  if (left !== undefined) return `quota: ${left} left today`
  return 'quota: ' + JSON.stringify(u).slice(0, 60)
}

export default function App() {
  const [tab, setTab] = useState('lab')
  const [attacks, setAttacks] = useState([])
  const [replay, setReplay] = useState(null)
  const [useReplay, setUseReplay] = useState(false)
  const [usage, setUsage] = useState(null)
  const [selected, setSelected] = useState('')
  const [text, setText] = useState('')
  const [left, setLeft] = useState([])
  const [right, setRight] = useState([])
  const [busy, setBusy] = useState(false)
  const [session, setSession] = useState(sid())
  const [persona, setPersona] = useState('anonymous') // trust level the session starts at
  const [fault, setFault] = useState('') // '' | 'outage' | 'partial': demo switch that makes the Guard fail
  const runId = useRef(0)

  useEffect(() => {
    api('/attacks').then((r) => r.ok && setAttacks(r.data))
    api('/replay').then((r) => r.ok && setReplay(r.data))
  }, [])

  const pollUsage = useCallback(() => api('/usage').then((r) => setUsage(r.ok ? r.data : { error: true })), [])
  useEffect(() => {
    if (useReplay) return
    pollUsage()
    const t = setInterval(pollUsage, 15000)
    return () => clearInterval(t)
  }, [useReplay, pollUsage])

  const grouped = useMemo(() => {
    const g = {}
    attacks.forEach((a) => (g[a.moment || a.weakness] ||= []).push(a))  // grouped by demo moment
    return g
  }, [attacks])

  const current = attacks.find((a) => a.id === selected)

  function onSelect(id) {
    setSelected(id)
    const a = attacks.find((x) => x.id === id)
    if (a) {
      setText(a.turns.length === 1 ? a.turns[0] : a.turns.join('\n---\n'))
      setFault(a.simulate || '')
      setPersona(a.persona || 'anonymous')
    }
  }

  function reset() {
    runId.current++
    setLeft([]); setRight([]); setSession(sid()); setBusy(false)
  }

  const addLeft = (m) => setLeft((l) => [...l, m])
  const addRight = (m) => setRight((l) => [...l, m])

  function leftFromGuardOnly({ ok, status, data }) {
    if (!ok) return { role: 'bot', kind: 'error', text: `Guard error ${status}: ${data.error || ''} ${data.detail || ''}`.trim(), raw: null }
    if (data.blocked) return { role: 'bot', kind: 'blocked', text: `Blocked by the Guard at the ${data.stage} check.`, raw: data }
    return { role: 'bot', kind: 'ok', text: data.reply, raw: data }
  }

  function rightFromShielded({ ok, status, data }) {
    if (!ok) return { role: 'bot', kind: 'error', text: `Error ${status}: ${data.error || ''} ${data.detail || ''}`.trim(), raw: null }
    return { role: 'bot', kind: data.blocked ? 'blocked' : 'ok', text: data.reply, raw: data }
  }

  async function sendLive(messages) {
    const my = ++runId.current
    setBusy(true)
    for (let i = 0; i < messages.length; i++) {
      if (runId.current !== my) return
      const m = messages[i]
      addLeft({ role: 'user', text: m }); addRight({ role: 'user', text: m })
      const body = { session_id: session, message: m, persona, ...(fault ? { simulate: fault } : {}) }
      const [g, s] = await Promise.all([api('/chat/guard-only', body), api('/chat/shielded', body)])
      if (runId.current !== my) return
      addLeft(leftFromGuardOnly(g)); addRight(rightFromShielded(s))
      if (i < messages.length - 1) await sleep(600)
    }
    setBusy(false)
    pollUsage()
  }

  async function showReplay(attackId) {
    const c = replay?.cases?.find((x) => x.id === attackId)
    if (!c) { addRight({ role: 'bot', kind: 'error', text: 'No recorded run for this attack.' }); return }
    const my = ++runId.current
    setBusy(true)
    for (const t of c.turns) {
      if (runId.current !== my) return
      addLeft({ role: 'user', text: t.message }); addRight({ role: 'user', text: t.message })
      await sleep(400)
      addLeft(leftFromGuardOnly({ ok: !t.guard_only.error, status: t.guard_only.error, data: t.guard_only }))
      addRight(rightFromShielded({ ok: !t.shielded.error, status: t.shielded.error, data: t.shielded }))
      await sleep(400)
    }
    setBusy(false)
  }

  function send() {
    if (busy) return
    const trimmed = text.trim()
    if (!trimmed && !current) return
    const isLibrary = current && text === (current.turns.length === 1 ? current.turns[0] : current.turns.join('\n---\n'))
    const messages = isLibrary ? current.turns : [trimmed]
    if (useReplay) {
      if (isLibrary) showReplay(current.id)
      else addRight({ role: 'bot', kind: 'error', text: 'Replay mode only plays recorded attacks from the library.' })
      return
    }
    sendLive(messages)
  }

  const lastRight = [...right].reverse().find((m) => m.role === 'bot' && m.raw)
  const lastLeft = [...left].reverse().find((m) => m.role === 'bot' && m.raw)

  return (
    <div className="app">
      <header>
        <div>
          <h1>Aim Shield <span>Attack Lab</span></h1>
          <p className="sub">Same message, two defences: the Guard alone vs Guard + Aim Shield.</p>
        </div>
        <div className="head-right">
          <nav>
            <button className={tab === 'lab' ? 'on' : ''} onClick={() => setTab('lab')}>Lab</button>
            <button className={tab === 'score' ? 'on' : ''} onClick={() => setTab('score')}>Scoreboard</button>
          </nav>
          <label className="toggle">
            <input type="checkbox" checked={useReplay} onChange={(e) => { setUseReplay(e.target.checked); reset() }} />
            Replay recorded run
          </label>
          <span className="quota" title="Guard quota (GET /v1/usage)">{useReplay ? 'offline replay' : usageText(usage)}</span>
        </div>
      </header>

      {tab === 'score' ? <Scoreboard replay={replay} /> : (
        <>
          <section className="controls">
            <select value={selected} onChange={(e) => onSelect(e.target.value)} aria-label="Attack library">
              <option value="">Attack library…</option>
              {Object.entries(grouped).map(([w, list]) => (
                <optgroup key={w} label={w}>
                  {list.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
                </optgroup>
              ))}
            </select>
            <textarea
              value={text}
              onChange={(e) => { setText(e.target.value); setSelected(selected && attacks.find((a) => a.id === selected) ? selected : '') }}
              placeholder="Type your own attack (or a normal question) and press Send"
              rows={3}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send() }}
            />
            <div className="btns">
              <select value={persona} onChange={(e) => { setPersona(e.target.value); reset() }} aria-label="Customer session"
                      title="Who is using the support chat: sets the session's trust level">
                <option value="anonymous">Customer: anonymous (level 0)</option>
                <option value="ama">Customer: logged in as Ama (level 1)</option>
                <option value="ama_verified">Customer: Ama, verified (level 2)</option>
              </select>
              <select value={fault} onChange={(e) => setFault(e.target.value)} aria-label="Guard fault"
                      title="Demo only: make the Guard fail, to show what each side does (no quota used)">
                <option value="">Guard: working</option>
                <option value="outage">Guard: outage (502)</option>
                <option value="partial">Guard: partial result</option>
              </select>
              <button className="primary" onClick={send} disabled={busy || (!text.trim())}>{busy ? 'Running…' : 'Send'}</button>
              <button onClick={reset}>New session</button>
            </div>
          </section>

          <main className="panes">
            <Pane title="Guard only" subtitle="What the app does today" messages={left} side="left"
                  tools={left.flatMap((m) => m.raw?.tool_log || [])} trust={lastLeft?.raw?.trust_level}>
              {lastLeft && <GuardRaw data={lastLeft.raw} />}
            </Pane>
            <Pane title="Guard + Aim Shield" subtitle="Our layers beside the Guard" messages={right} side="right"
                  tools={right.flatMap((m) => m.raw?.tool_log || [])} trust={lastRight?.raw?.trust_level}>
              {lastRight && <ShieldTrace data={lastRight.raw} />}
            </Pane>
          </main>
        </>
      )}
    </div>
  )
}

const LEVELS = ['anonymous', 'logged in as Ama', 'verified']

function ToolLog({ events }) {
  return (
    <div className="tools">
      <h3>Tool log <small>(mock KwikPay)</small></h3>
      {events.length === 0 && <p className="empty">No tool was called.</p>}
      {events.map((e, i) => {
        const bad = e.status === 'executed' && !e.authorised
        const cls = e.status === 'denied' ? 'amber' : bad ? 'red' : 'green'
        return (
          <div className="row" key={i}>
            <span className={`dot ${cls}`} />
            <b>{e.tool}</b>
            <code>{Object.values(e.args || {}).join(', ')}</code>
            <span className={`pill ${cls}`}>{e.status === 'denied' ? 'DENIED' : bad ? 'EXECUTED, NOT AUTHORISED' : 'executed'}</span>
            <span className="why">{e.detail}</span>
          </div>
        )
      })}
    </div>
  )
}

function Pane({ title, subtitle, messages, side, children, tools = [], trust }) {
  const end = useRef(null)
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [messages])
  return (
    <section className={`pane ${side}`}>
      <h2>{title} <small>{subtitle}</small>{trust !== undefined && <span className="trust">trust {trust}: {LEVELS[trust]}</span>}</h2>
      <div className="chat">
        {messages.length === 0 && <p className="empty">Pick an attack or type a message.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role} ${m.kind || ''}`}>
            {m.role === 'bot' && m.kind && m.kind !== 'ok' && <b className="tag">{m.kind === 'blocked' ? 'BLOCKED' : 'ERROR'}</b>}
            <span>{m.text && m.text.length > 700 ? m.text.slice(0, 700) + '…' : m.text}</span>
          </div>
        ))}
        <div ref={end} />
      </div>
      <ToolLog events={tools} />
      {children}
    </section>
  )
}

function GuardRaw({ data }) {
  const rows = [['prompt', data.guard_prompt], ['response', data.guard_response]].filter(([, r]) => r)
  return (
    <div className="strip">
      <h3>Raw Guard results</h3>
      {rows.map(([name, r]) => (
        <div className="row" key={name}>
          <span className={`dot ${r.allowed ? 'green' : 'red'}`} />
          <b>{name}</b>
          <span>allowed: {String(r.allowed)}</span>
          <span>flags: {r.flags?.length ? r.flags.join(', ') : 'none'}</span>
          <span>status: {r.status}</span>
          <code>{r.request_id}</code>
        </div>
      ))}
    </div>
  )
}

function ShieldTrace({ data }) {
  const iv = data.input_verdict, ov = data.output_verdict
  const steps = [...(iv?.trace || []).map((t) => ({ ...t, side: 'in' })), ...(ov?.trace || []).map((t) => ({ ...t, side: 'out' }))]
  const headline = (ov && ov.decision !== 'ALLOW') ? ov : iv
  const calls = (iv?.guard_calls || 0) + (ov?.guard_calls || 0)
  return (
    <div className="strip">
      {headline && (
        <div className={`banner ${tone(headline.decision)}`}>
          <b>{headline.decision}</b>
          {headline.fired_layer && <span> · {headline.fired_layer}</span>}
          <p>{headline.reason}</p>
          {headline.next_step && <p className="next">Next step: {headline.next_step}</p>}
        </div>
      )}
      {iv?.sanitized_text && (
        <p className="saw"><b>What the model actually saw:</b> {iv.sanitized_text}</p>
      )}
      <h3>Layer trace <small>{calls} Guard call(s) · {data.total_latency_ms} ms</small></h3>
      {steps.map((t, i) => (
        <div className="row" key={i}>
          <span className={`dot ${tone(t.decision)}`} />
          <b>{t.side === 'out' ? 'out · ' : ''}{t.layer}</b>
          <span className="lat">{t.latency_ms} ms</span>
          {t.reason && <span className="why">{t.reason}</span>}
        </div>
      ))}
    </div>
  )
}

function Scoreboard({ replay }) {
  if (!replay) return <p className="empty big">No recorded results yet. Run <code>python eval/run_suite.py</code>.</p>
  const s = replay.summary || {}
  const per = s.per_weakness || {}
  return (
    <main className="score">
      {replay.synthetic && <div className="banner amber"><b>PLACEHOLDER DATA</b><p>These numbers are synthetic, not measurements. Run eval/run_suite.py to replace them.</p></div>}
      <table>
        <thead><tr><th>Weakness</th><th>Attacks</th><th>Guard alone caught</th><th>Guard + Aim caught</th></tr></thead>
        <tbody>
          {Object.entries(per).map(([w, v]) => (
            <tr key={w}><td>{w}</td><td>{v.n}</td><td>{v.guard_only_caught}/{v.n}</td><td className="good">{v.shielded_caught}/{v.n}</td></tr>
          ))}
        </tbody>
      </table>
      <div className="facts">
        <div><b>{s.benign?.guard_only_wrongly_blocked ?? '–'} vs {s.benign?.shielded_wrongly_blocked ?? '–'}</b><span>harmless messages wrongly blocked (Guard / Aim), of {s.benign?.n ?? '–'}</span></div>
        <div><b>{s.added_screening_ms?.median ?? '–'} ms</b><span>median added screening time on messages that pass (p95 {s.added_screening_ms?.p95 ?? '–'} ms), excluding the LLM</span></div>
        <div><b>{s.harmful_replies?.guard_only ?? '–'} vs {s.harmful_replies?.shielded ?? '–'}</b><span>harmful replies shown to the user (Guard only / Aim): leaked the canary or asked for a PIN</span></div>
        <div><b>{s.guard_calls_per_case?.guard_only ?? '–'} → {s.guard_calls_per_case?.shielded ?? '–'}</b><span>Guard calls per case (Guard / Aim)</span></div>
      </div>
      <h3>Still missed by Aim</h3>
      <p>{s.known_misses?.length ? s.known_misses.join(', ') : 'none in this run'}</p>
      <p className="muted">Recorded {replay.generated_at}</p>
    </main>
  )
}
