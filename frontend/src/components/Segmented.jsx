// A standard segmented control built on radio inputs: keyboard-complete (arrow keys), screen-reader friendly.
export default function Segmented({ label, name, value, onChange, options, hideLabel = false, disabled = false }) {
  return (
    <fieldset className="seg" disabled={disabled}>
      <legend className={hideLabel ? 'sr-only' : ''}>{label}</legend>
      <div className="seg-track">
        {options.map((o) => (
          <label key={o.value} className={value === o.value ? 'on' : ''} title={o.hint}>
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
            />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
