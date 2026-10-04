import { MOMENT_NOTES } from '../lib/moments.js'

// Six numbered steps (the demo moments) and a select for the attack within the chosen step.
export default function ScenarioRail({ groups, active, onMoment, selectedId, onSelect }) {
  const group = groups.find((g) => g.label === active)
  return (
    <section className="rail" aria-label="Scenario">
      <div className="wrap">
        <ol className="steps">
          {groups.map((g) => (
            <li key={g.label}>
              <button
                aria-current={g.label === active ? 'step' : undefined}
                onClick={() => onMoment(g.label)}
                title={g.label}
              >
                <span className="step-n" aria-hidden="true">{g.number || '·'}</span>
                <span>{g.name}</span>
              </button>
            </li>
          ))}
        </ol>

        {group && (
          <div className="rail-detail">
            <p className="note">{MOMENT_NOTES[group.number] || 'Pick an attack to run.'}</p>
            <label className="pick">
              <span>Attack</span>
              <select value={selectedId} onChange={(e) => onSelect(e.target.value)}>
                {group.attacks.map((a) => (
                  <option key={a.id} value={a.id}>{a.title}</option>
                ))}
              </select>
            </label>
          </div>
        )}
      </div>
    </section>
  )
}
