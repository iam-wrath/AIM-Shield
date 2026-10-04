import Conversation from './Conversation.jsx'
import Outcome from './Outcome.jsx'
import ToolLog from './ToolLog.jsx'
import { LEVEL_NAMES } from '../lib/moments.js'

// Order: the verdict, then the evidence (what was done, what the checks said), then the conversation.
export default function Pane({ side, title, subtitle, botName, blockedName, messages, pending, outcome, tools, trust, children }) {
  return (
    <section className={`pane ${side}`} aria-label={title}>
      <header className="pane-head">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {trust !== undefined && <span className="chip">Customer: {LEVEL_NAMES[trust]}</span>}
      </header>
      <Outcome outcome={outcome} pending={pending} />
      <ToolLog events={tools} />
      {children}
      <Conversation messages={messages} pending={pending} botName={botName} blockedName={blockedName} label={`${title} conversation`} />
    </section>
  )
}
