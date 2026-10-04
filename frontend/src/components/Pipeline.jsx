import { useState } from 'react'
import Icon from './Icon.jsx'
import { LAYER_SHORT, layerName } from '../lib/moments.js'

// One row of chips, one per layer, in the order a message travels:
// the Guard and Aim's input layers, the model, then the reply checks.
const FIRST = ['guard', 'chunker', 'failsafe']
const INPUT_REST = ['ghana_lens', 'base64_decoder', 'conversation_memory', 'identity_binding', 'rag_screen']
const OUTPUT_REST = ['output_sentinel', 'ghana_lens']
const OUT_LABEL = { guard: 'Guard (reply)', chunker: 'Chunker (reply)', failsafe: 'Fail-safe (reply)', output_sentinel: 'Sentinel', ghana_lens: 'Ghana Lens (reply)' }

const STATE = {
  pass: { icon: 'check', word: 'passed' },
  changed: { icon: 'changed', word: 'changed or flagged something' },
  stopped: { icon: 'shield-check', word: 'stopped it' },
  idle: { icon: 'minus', word: 'was not reached' },
}

const stateOf = (step) => (!step ? 'idle' : step.decision === 'BLOCK' ? 'stopped' : step.decision === 'WARN' || step.decision === 'REDACT' ? 'changed' : 'pass')

function chips(iv, ov) {
  const inTrace = iv?.trace || []
  const outTrace = ov?.trace || []
  const out = []
  const first = inTrace.find((t) => FIRST.includes(t.layer))
  out.push({ key: 'in:first', label: LAYER_SHORT[first?.layer || 'guard'], layer: first?.layer || 'guard', step: first })
  INPUT_REST.forEach((l) => out.push({ key: `in:${l}`, label: LAYER_SHORT[l], layer: l, step: inTrace.find((t) => t.layer === l) }))
  out.push({ key: 'model', label: 'Model', layer: 'model', step: ov ? { decision: 'ALLOW', reason: 'The assistant answered.', latency_ms: null } : null })
  const ofirst = outTrace.find((t) => FIRST.includes(t.layer))
  out.push({ key: 'out:first', label: OUT_LABEL[ofirst?.layer || 'guard'], layer: ofirst?.layer || 'guard', step: ofirst })
  OUTPUT_REST.forEach((l) => out.push({ key: `out:${l}`, label: OUT_LABEL[l], layer: l, step: outTrace.find((t) => t.layer === l) }))
  return out
}

export default function Pipeline({ data }) {
  const [open, setOpen] = useState(null)
  const iv = data?.input_verdict
  const ov = data?.output_verdict
  if (!iv) return null
  const list = chips(iv, ov)
  const fired = list.find((c) => stateOf(c.step) === 'stopped') || list.find((c) => stateOf(c.step) === 'changed')
  const shown = list.find((c) => c.key === (open ?? fired?.key))
  const calls = (iv.guard_calls || 0) + (ov?.guard_calls || 0)
  const ms = Math.round((iv.total_latency_ms || 0) + (ov?.total_latency_ms || 0))

  return (
    <section className="evidence" aria-label="Layer pipeline">
      <h3>What Aim checked <small>{calls} Guard call{calls === 1 ? '' : 's'}, {ms} ms of screening</small></h3>
      <ul className="pipe">
        {list.map((c) => {
          const st = stateOf(c.step)
          return (
            <li key={c.key}>
              <button
                className={`pchip ${st}`}
                aria-expanded={shown?.key === c.key}
                aria-label={`${c.label}: ${STATE[st].word}`}
                onClick={() => setOpen(shown?.key === c.key ? 'none' : c.key)}
              >
                <Icon name={STATE[st].icon} size="0.95em" /> {c.label}
              </button>
            </li>
          )
        })}
      </ul>
      {shown && (
        <p className="pipe-detail" role="note">
          <b>{layerName(shown.layer) === shown.layer ? (shown.label) : layerName(shown.layer)}</b>{' '}
          {STATE[stateOf(shown.step)].word}.{' '}
          {shown.step?.reason || (shown.step ? 'No problem found.' : 'Nothing earlier needed it.')}
          {shown.step?.latency_ms != null && <span className="detail-only"> ({shown.step.latency_ms} ms)</span>}
        </p>
      )}
      {iv.sanitized_text && (
        <p className="saw">
          <b>What the model saw:</b> {iv.sanitized_text.length > 260 ? iv.sanitized_text.slice(0, 260) + '...' : iv.sanitized_text}
        </p>
      )}
    </section>
  )
}
