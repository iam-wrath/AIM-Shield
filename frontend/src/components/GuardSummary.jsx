import Icon from './Icon.jsx'

// What the SecureAI Guard itself said about the message and the reply: the evidence that it let the attack through.
export default function GuardSummary({ data }) {
  if (!data) return null
  const rows = [['Message', data.guard_prompt], ['Reply', data.guard_response]].filter(([, r]) => r)
  return (
    <section className="evidence" aria-label="What the Guard said">
      <h3>What the Guard said</h3>
      <ul className="checks">
        {rows.map(([name, r]) => (
          <li key={name}>
            <Icon name={r.allowed ? 'check' : 'shield-check'} size="1em" />
            <span>
              <b>{name}</b> {r.allowed ? 'allowed' : 'blocked'}
              {r.flags?.length ? `: ${r.flags.join(', ')}` : r.allowed ? ', no flags' : ''}
              {r.status && r.status !== 'complete' ? ` (status: ${r.status})` : ''}
            </span>
            <code className="detail-only">{r.request_id}</code>
          </li>
        ))}
      </ul>
    </section>
  )
}
