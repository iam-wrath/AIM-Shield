import Icon from './Icon.jsx'

// Mock KwikPay tool calls. "Ran, not authorised" is the harm the Guard cannot see; "Refused" is Aim doing its job.
function describe(e) {
  if (e.status === 'denied') return { tone: 'safe', icon: 'shield-check', word: 'Refused' }
  if (!e.authorised) return { tone: 'danger', icon: 'alert', word: 'Ran, not authorised' }
  return { tone: 'neutral', icon: 'check', word: 'Ran' }
}

export default function ToolLog({ events }) {
  return (
    <section className="tools" aria-label="Tool log">
      <h3>Actions taken <small>(mock KwikPay tools)</small></h3>
      {events.length === 0 ? (
        <p className="quiet">No tool was called.</p>
      ) : (
        <ul>
          {events.map((e, i) => {
            const d = describe(e)
            return (
              <li key={i}>
                <div className="tool-line">
                  <code className="tool-name">{e.tool}</code>
                  <code className="tool-args">{Object.values(e.args || {}).join(', ')}</code>
                  <span className={`status ${d.tone}`}><Icon name={d.icon} size="1em" /> {d.word}</span>
                </div>
                <p className="quiet">{e.detail}</p>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
