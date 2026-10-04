import Icon from './Icon.jsx'

const NAMES = {
  W1: 'Ghana data',
  W2: 'Split across turns',
  W3: 'Base64',
  W4: 'Guard failure (simulated)',
  W5: 'Over 4,000 characters',
  W6: 'Response side and poisoned documents',
}

function Bars({ name, n, guard, aim }) {
  const pct = (v) => (n ? Math.round((v / n) * 100) : 0)
  return (
    <li className="score-row">
      <div className="score-name">
        <b>{name}</b> <span>{n} attack{n === 1 ? '' : 's'}</span>
      </div>
      <div className="bar-line">
        <span className="bar-label">Guard alone</span>
        <span className="bar"><i className="guard" style={{ width: `${pct(guard)}%` }} /></span>
        <span className="bar-count">{guard} of {n}</span>
      </div>
      <div className="bar-line">
        <span className="bar-label">Guard + Aim</span>
        <span className="bar"><i className="aim" style={{ width: `${pct(aim)}%` }} /></span>
        <span className="bar-count">{aim} of {n}</span>
      </div>
    </li>
  )
}

export default function Scoreboard({ replay }) {
  if (!replay) {
    return (
      <main className="wrap score" id="stage">
        <p className="empty big">No recorded results yet. Run <code>python eval/run_suite.py</code> to create them.</p>
      </main>
    )
  }
  const s = replay.summary || {}
  const per = s.per_weakness || {}
  const rows = Object.entries(per).filter(([k]) => k !== 'Guard handles well')
  const control = per['Guard handles well']
  const total = rows.reduce((a, [, v]) => a + v.n, 0)
  const guardTotal = rows.reduce((a, [, v]) => a + v.guard_only_caught, 0)
  const aimTotal = rows.reduce((a, [, v]) => a + v.shielded_caught, 0)
  const pair = (o) => `${o?.guard_only ?? '-'} with the Guard alone, ${o?.shielded ?? '-'} with Aim`

  return (
    <main className="wrap score" id="stage">
      {replay.synthetic && (
        <p className="outcome caution" role="alert">
          <Icon name="alert" size="1.5em" />
          <span><b className="o-title">Placeholder data.</b> These numbers are synthetic, not measurements. Run eval/run_suite.py to replace them.</span>
        </p>
      )}

      <h2 className="score-lead">
        Across {total} attacks, the Guard alone stopped {guardTotal}. Guard + Aim Shield stopped {aimTotal}.
      </h2>

      <ul className="score-list">
        {rows.map(([k, v]) => (
          <Bars key={k} name={NAMES[k] || k} n={v.n} guard={v.guard_only_caught} aim={v.shielded_caught} />
        ))}
      </ul>

      {control && (
        <p className="honest">
          <Icon name="info" size="1.1em" /> <b>What the Guard already handles well</b> (we do not claim these): the Guard alone
          stopped {control.guard_only_caught} of {control.n}, and so did Guard + Aim.
        </p>
      )}

      <h3>Other measurements</h3>
      <dl className="facts">
        <div><dt>Harmless messages wrongly blocked</dt><dd>{s.benign?.guard_only_wrongly_blocked ?? '-'} with the Guard alone, {s.benign?.shielded_wrongly_blocked ?? '-'} with Aim (of {s.benign?.n ?? '-'})</dd></div>
        <div><dt>Replies that did harm to the customer</dt><dd>{pair(s.harmful_replies)}</dd></div>
        <div><dt>Unauthorised tool calls</dt><dd>{pair(s.unauthorised_tool_calls)}</dd></div>
        <div><dt>Guard calls per case</dt><dd>{s.guard_calls_per_case?.guard_only ?? '-'} with the Guard alone, {s.guard_calls_per_case?.shielded ?? '-'} with Aim</dd></div>
        <div><dt>Added screening time (95th percentile)</dt><dd>{s.added_screening_ms?.p95 ?? '-'} ms, not counting the model. The median is too noisy to quote.</dd></div>
        <div><dt>Still missed by Aim</dt><dd>{s.known_misses?.length ? s.known_misses.join(', ') : 'Nothing in this run (a small, hand-written suite).'}</dd></div>
      </dl>
      <p className="quiet">Recorded {replay.generated_at}. {replay.note}</p>
    </main>
  )
}
