import { useEffect, useRef } from 'react'

const clip = (t) => (t && t.length > 600 ? t.slice(0, 600) + '...' : t)

export default function Conversation({ messages, pending, botName, blockedName, label }) {
  const end = useRef(null)
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest' })
  }, [messages, pending])

  return (
    <div className="chat" role="log" aria-live="polite" aria-label={label} tabIndex={0}>
      {messages.length === 0 && !pending && <p className="empty">Nothing sent yet.</p>}
      {messages.map((m, i) => {
        if (m.role === 'user') {
          return (
            <div key={i} className="bubble user">
              <span className="who">Customer</span>
              <span>{clip(m.text)}</span>
            </div>
          )
        }
        const notice = m.kind === 'blocked'
        const err = m.kind === 'error'
        return (
          <div key={i} className={`bubble bot ${notice ? 'notice' : ''} ${err ? 'err' : ''}`}>
            <span className="who">{err ? 'Error' : notice ? `${blockedName} replied` : botName}</span>
            <span>{clip(m.text)}</span>
          </div>
        )
      })}
      {pending && (
        <div className="bubble bot pending">
          <span className="who">{botName}</span>
          <span className="dots" role="img" aria-label="Checking"><i /><i /><i /></span>
        </div>
      )}
      <div ref={end} />
    </div>
  )
}
