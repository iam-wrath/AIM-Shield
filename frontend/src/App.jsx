import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, sid, sleep, store } from './lib/api.js'
import { momentName, momentNumber } from './lib/moments.js'
import { aimOutcome, guardOutcome } from './lib/outcome.js'
import TopBar from './components/TopBar.jsx'
import ScenarioRail from './components/ScenarioRail.jsx'
import Composer from './components/Composer.jsx'
import Pane from './components/Pane.jsx'
import Pipeline from './components/Pipeline.jsx'
import GuardSummary from './components/GuardSummary.jsx'
import Scoreboard from './components/Scoreboard.jsx'

const joinTurns = (turns) => (turns.length === 1 ? turns[0] : turns.join('\n---\n'))
const lastBot = (list) => [...list].reverse().find((m) => m.role === 'bot')
const lastRaw = (list) => [...list].reverse().find((m) => m.role === 'bot' && m.raw)

function fromGuardOnly({ ok, status, data }, replayHarm = false) {
  if (!ok) return { role: 'bot', kind: 'error', text: `Guard error ${status}: ${data.error || ''} ${data.detail || ''}`.trim(), raw: null }
  if (data.blocked) return { role: 'bot', kind: 'blocked', text: `Blocked by the Guard at the ${data.stage} check.`, raw: data }
  return { role: 'bot', kind: 'ok', text: data.reply, raw: data, replayHarm }
}

function fromShielded({ ok, status, data }) {
  if (!ok) return { role: 'bot', kind: 'error', text: `Error ${status}: ${data.error || ''} ${data.detail || ''}`.trim(), raw: null }
  return { role: 'bot', kind: data.blocked ? 'blocked' : 'ok', text: data.reply, raw: data }
}

export default function App() {
  const [tab, setTab] = useState('lab')
  const [live, setLive] = useState(true)
  const [attacks, setAttacks] = useState([])
  const [replay, setReplay] = useState(null)
  const [usage, setUsage] = useState(null)
  const [moment, setMoment] = useState('')
  const [selected, setSelected] = useState('')
  const [text, setText] = useState('')
  const [persona, setPersona] = useState('anonymous') // the trust level the session starts at
  const [demo, setDemo] = useState('') // '' | outage | partial | rag_off: the one demo switch the API supports
  const [left, setLeft] = useState([])
  const [right, setRight] = useState([])
  const [pending, setPending] = useState({ left: false, right: false })
  const [progress, setProgress] = useState(null)
  const [busy, setBusy] = useState(false)
  const [session, setSession] = useState(sid())
  const [theme, setTheme] = useState(() => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'))
  const [present, setPresent] = useState(() => document.documentElement.dataset.present === 'on')
  const runId = useRef(0)
  const ranLibrary = useRef(false) // the last run was a library attack, so typed text should start fresh

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    store.set('aim-theme', theme)
  }, [theme])
  useEffect(() => {
    if (present) document.documentElement.dataset.present = 'on'
    else delete document.documentElement.dataset.present
    store.set('aim-present', present ? 'on' : 'off')
  }, [present])

  useEffect(() => {
    api('/attacks').then((r) => r.ok && setAttacks(r.data))
    api('/replay').then((r) => r.ok && setReplay(r.data))
  }, [])

  const pollUsage = useCallback(() => api('/usage').then((r) => setUsage(r.ok ? r.data : { error: true })), [])
  useEffect(() => {
    if (!live) return
    pollUsage()
    const t = setInterval(pollUsage, 15000)
    return () => clearInterval(t)
  }, [live, pollUsage])

  const groups = useMemo(() => {
    const map = new Map()
    attacks.forEach((a) => {
      const label = a.moment || a.weakness
      if (!map.has(label)) map.set(label, { label, number: momentNumber(label), name: momentName(label), attacks: [] })
      map.get(label).attacks.push(a)
    })
    return [...map.values()].sort((a, b) => (a.number || 99) - (b.number || 99) || a.label.localeCompare(b.label))
  }, [attacks])

  const current = attacks.find((a) => a.id === selected)
  const libraryText = current ? joinTurns(current.turns) : null
  const isLibrary = current && text === libraryText

  function reset(newSession) {
    ranLibrary.current = false
    runId.current++
    setLeft([])
    setRight([])
    setPending({ left: false, right: false })
    setProgress(null)
    setSession(newSession || sid())
    setBusy(false)
  }

  function onSelect(id) {
    const a = attacks.find((x) => x.id === id)
    if (!a) return
    reset()
    setSelected(id)
    setMoment(a.moment || a.weakness)
    setText(joinTurns(a.turns))
    setDemo(a.simulate || '')
    setPersona(a.persona || 'anonymous')
  }

  function onMoment(label) {
    const g = groups.find((x) => x.label === label)
    if (g) onSelect(g.attacks[0].id)
  }

  // open on the first demo moment so Send is ready
  useEffect(() => {
    if (groups.length && !selected) onSelect(groups[0].attacks[0].id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groups])

  function changeMode(isLive) {
    setLive(isLive)
    reset()
  }

  const addLeft = (m) => setLeft((l) => [...l, m])
  const addRight = (m) => setRight((l) => [...l, m])

  async function sendLive(messages, sess = session) {
    const my = ++runId.current
    setBusy(true)
    for (let i = 0; i < messages.length; i++) {
      if (runId.current !== my) return
      setProgress(messages.length > 1 ? { i: i + 1, n: messages.length } : null)
      const m = messages[i]
      addLeft({ role: 'user', text: m })
      addRight({ role: 'user', text: m })
      setPending({ left: true, right: true })
      const body = { session_id: sess, message: m, persona, ...(demo ? { simulate: demo } : {}) }
      const g = api('/chat/guard-only', body).then((r) => {
        if (runId.current !== my) return
        addLeft(fromGuardOnly(r))
        setPending((p) => ({ ...p, left: false }))
      })
      const s = api('/chat/shielded', body).then((r) => {
        if (runId.current !== my) return
        addRight(fromShielded(r))
        setPending((p) => ({ ...p, right: false }))
      })
      await Promise.all([g, s])
      if (i < messages.length - 1) await sleep(500)
    }
    if (runId.current === my) {
      setBusy(false)
      setProgress(null)
      pollUsage()
    }
  }

  async function showReplay(attackId) {
    const c = replay?.cases?.find((x) => x.id === attackId)
    if (!c) {
      addRight({ role: 'bot', kind: 'error', text: 'There is no recorded run for this attack.' })
      return
    }
    const my = ++runId.current
    setBusy(true)
    for (let i = 0; i < c.turns.length; i++) {
      if (runId.current !== my) return
      const t = c.turns[i]
      const last = i === c.turns.length - 1
      setProgress(c.turns.length > 1 ? { i: i + 1, n: c.turns.length } : null)
      addLeft({ role: 'user', text: t.message })
      addRight({ role: 'user', text: t.message })
      setPending({ left: true, right: true })
      await sleep(450)
      if (runId.current !== my) return
      addLeft(fromGuardOnly({ ok: !t.guard_only.error, status: t.guard_only.error, data: t.guard_only }, last && !!c.guard_only?.leaked))
      addRight(fromShielded({ ok: !t.shielded.error, status: t.shielded.error, data: t.shielded }))
      setPending({ left: false, right: false })
      await sleep(350)
    }
    if (runId.current === my) {
      setBusy(false)
      setProgress(null)
    }
  }

  function send() {
    if (busy) return
    const trimmed = text.trim()
    if (!trimmed) return
    if (!live) {
      if (isLibrary) showReplay(current.id)
      else addRight({ role: 'bot', kind: 'error', text: 'Replay only plays the recorded attacks. Switch to Live to send your own message.' })
      return
    }
    // typing your own message after a library attack starts a new conversation, so old harm is not carried over
    let sess = session
    if (!isLibrary && ranLibrary.current) {
      sess = sid()
      reset(sess)
    }
    ranLibrary.current = !!isLibrary
    sendLive(isLibrary ? current.turns : [trimmed], sess)
  }

  // Only say something when it helps: multi-turn attacks, or text that replay cannot play.
  const hint = isLibrary && current.turns.length > 1
    ? `This attack plays ${current.turns.length} messages in order.`
    : !isLibrary && !live
      ? 'Replay only plays the recorded attacks. Switch to Live to send your own message.'
      : ''

  const expected = isLibrary ? current.expected : undefined
  const rawLeft = lastRaw(left)
  const rawRight = lastRaw(right)

  return (
    <div className="app">
      <a className="skip" href="#stage">Skip to results</a>
      <TopBar
        tab={tab}
        setTab={setTab}
        live={live}
        setLive={changeMode}
        usage={usage}
        theme={theme}
        onTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        present={present}
        onPresent={() => setPresent(!present)}
      />

      {!live && (
        <p className="replay-note" role="note">
          <span className="wrap">Replay: showing recorded results. Nothing is sent to the Guard or the model.</span>
        </p>
      )}

      {tab === 'score' ? (
        <Scoreboard replay={replay} />
      ) : (
        <>
          <div className="setup">
            <ScenarioRail groups={groups} active={moment} onMoment={onMoment} selectedId={selected} onSelect={onSelect} />
            <Composer
              text={text}
              setText={setText}
              onSend={send}
              busy={busy}
              progress={progress}
              hint={hint}
              persona={persona}
              setPersona={(p) => { setPersona(p); reset() }}
              demo={demo}
              setDemo={setDemo}
              onNew={reset}
            />
          </div>

          <main className="wrap stage" id="stage">
            <Pane
              side="left"
              title="Guard only"
              subtitle="What a typical app does today"
              botName="KwikPay Assist"
              blockedName="SecureAI Guard"
              messages={left}
              pending={pending.left}
              outcome={guardOutcome(left, { expected, replayHarm: lastBot(left)?.replayHarm })}
              tools={left.flatMap((m) => m.raw?.tool_log || [])}
              trust={rawLeft?.raw?.trust_level}
            >
              <GuardSummary data={rawLeft?.raw} />
            </Pane>
            <Pane
              side="right"
              title="Guard + Aim Shield"
              subtitle="Our layers beside the Guard"
              botName="KwikPay Assist"
              blockedName="Aim Shield"
              messages={right}
              pending={pending.right}
              outcome={aimOutcome(right, { expected })}
              tools={right.flatMap((m) => m.raw?.tool_log || [])}
              trust={rawRight?.raw?.trust_level}
            >
              <Pipeline key={right.length} data={rawRight?.raw} />
            </Pane>
          </main>

        </>
      )}
    </div>
  )
}
