import Icon from './Icon.jsx'

const ICON = { safe: 'shield-check', danger: 'alert', caution: 'alert', neutral: 'info', idle: 'minus' }

// The verdict for one side, as a plain headline. Icon, word and colour always agree.
export default function Outcome({ outcome, pending }) {
  const o = pending ? { tone: 'idle', title: 'Checking', detail: '' } : outcome
  return (
    <div className={`outcome ${o.tone}`} role="status" aria-live="polite" key={`${o.title}|${o.detail}`}>
      <Icon name={ICON[o.tone]} size="1.5em" />
      <div>
        <p className="o-title">{o.title}</p>
        {o.detail && <p className="o-detail">{o.detail}</p>}
      </div>
    </div>
  )
}
