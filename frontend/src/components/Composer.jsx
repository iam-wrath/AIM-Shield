import Icon from './Icon.jsx'
import Segmented from './Segmented.jsx'

const PERSONAS = [
  { value: 'anonymous', label: 'Anonymous', hint: 'Level 0: not logged in' },
  { value: 'ama', label: 'Logged in', hint: 'Level 1: logged in as Ama' },
  { value: 'ama_verified', label: 'Verified', hint: 'Level 2: Ama, one-time code checked' },
]
const DEMO = [
  { value: '', label: 'Off', hint: 'Everything works normally' },
  { value: 'outage', label: 'Guard outage', hint: 'The Guard returns a 502 (no quota used)' },
  { value: 'partial', label: 'Guard partial', hint: 'The Guard returns a partial result (no quota used)' },
  { value: 'rag_off', label: 'Document screen off', hint: 'Aim stops screening retrieved documents, so the Output Sentinel is the last line' },
]
const labelOf = (list, v) => list.find((o) => o.value === v)?.label

// Message entry. The customer and demo switch collapse into one summary line: choosing an attack already sets them.
export default function Composer({ text, setText, onSend, busy, progress, hint, persona, setPersona, demo, setDemo, onNew }) {
  const keyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      onSend()
    }
  }
  return (
    <section className="composer" aria-label="Send a message">
      <div className="wrap">
        <details className="session">
          <summary>
            <span>
              Customer: <b>{labelOf(PERSONAS, persona)}</b> · Demo switch: <b>{labelOf(DEMO, demo)}</b>
            </span>
            <span className="change">Change <Icon name="chevron" size="1em" /></span>
          </summary>
          <div className="settings">
            <Segmented label="Customer" name="persona" value={persona} onChange={setPersona} options={PERSONAS} />
            <Segmented label="Demo switch" name="demo" value={demo} onChange={setDemo} options={DEMO} />
          </div>
        </details>
        <div className="entry">
          <label htmlFor="msg" className="sr-only">Message to send</label>
          <textarea
            id="msg"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={keyDown}
            rows={2}
            placeholder="Pick an attack above, or type your own message. Enter sends, Shift+Enter adds a line."
          />
          <div className="entry-btns">
            <button className="primary" onClick={onSend} disabled={busy || !text.trim()}>
              {busy ? (progress ? `Turn ${progress.i} of ${progress.n}` : 'Running') : 'Send'}
            </button>
            <button onClick={onNew}>New session</button>
          </div>
        </div>
        {hint && <p className="hint">{hint}</p>}
      </div>
    </section>
  )
}
