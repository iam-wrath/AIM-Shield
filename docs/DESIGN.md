# Design system: Attack Lab

Light by default (projector, lit room), dark available via a toggle, presenter mode for large type. System fonts only (the app must work offline). No new dependencies.

## Colour (OKLCH, neutrals tinted toward blue-gray, hue about 255)
Strategy: **Restrained.** One deep-blue accent for primary action, selection and focus only.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--bg` | 0.985 0.004 255 | 0.19 0.012 255 | page |
| `--surface` | 0.997 0.002 255 | 0.235 0.013 255 | panes, composer |
| `--surface-2` | 0.962 0.006 255 | 0.275 0.013 255 | inset areas, customer bubbles |
| `--line` | 0.89 0.008 255 | 0.34 0.013 255 | borders |
| `--text` / `--text-2` | 0.2 / 0.42 | 0.95 / 0.76 | body / secondary |
| `--accent` | 0.5 0.17 258 | 0.74 0.12 258 | actions, selection, focus |
| `--safe` | 0.42 0.11 155 | 0.82 0.12 155 | the defence worked |
| `--caution` | 0.44 0.10 70 | 0.85 0.11 85 | changed, degraded, warning |
| `--danger` | 0.46 0.17 27 | 0.82 0.12 25 | harm happened |

Each semantic colour has a `-bg` tint and a `-line` border. **Meaning is fixed:** green = a defence worked (stopped, refused, masked), amber = the system changed or degraded something, red = harm was done, neutral = answered normally. Every state also carries an icon and a word, never colour alone.

## Typography
`ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`; `ui-monospace, SFMono-Regular, Consolas, monospace` for IDs, tool names and arguments. Fixed rem scale, ratio 1.2: 0.8125, 0.9375, 1, 1.125, 1.375, 1.75 rem. Everything in `rem` so browser zoom and text enlargement work. Tabular numbers for latencies and counts. Sentence case; no all-caps labels. Presenter mode sets the root size to 125%.

## Spacing, shape, elevation
4-point base (0.25rem). Radius 0.75rem for panes, 0.5rem for controls. Borders, not shadows. No nested cards: panes contain sections separated by hairlines.

## Components
- **Top bar:** brand, Lab/Scoreboard, Live/Replay segmented control, quota, presenter and theme toggles.
- **Scenario rail:** six numbered steps (the demo moments) with a one-line "what this shows"; an attack select within the step.
- **Pane:** outcome headline (icon + word + detail), then evidence (actions taken, then the Guard's verdict or the layer pipeline), then the conversation.
- **Outcome headline:** one per side. Harm done (danger), Attack stopped (safe), Answered normally (neutral), Safe mode / warning (caution).
- **Pipeline strip:** a chip per layer; pass is quiet, changed is amber, stopped is green, not reached is dimmed. A chip opens its reason and latency (disclosure).
- **Tool log:** tool name, arguments, status word (Ran, Ran but not authorised, Refused).
- **Segmented control:** radio group, used for Live/Replay, customer trust level and the demo switch.
- **Setup band and composer:** scenario steps, the attack menu, a one-line summary of Customer and Demo switch (expands to edit), and a labelled textarea sit together at the top, so results appear directly below with no pinned bar covering them. Enter sends, Shift+Enter adds a line. Typing after a library attack starts a new conversation.

## Motion
150 to 250 ms, ease-out-quart. State only: a pending indicator, the outcome headline easing in, chip disclosure. Nothing animates layout properties. All motion off under `prefers-reduced-motion`.

## Accessibility
Text contrast 4.5:1 or better in both themes (main text 7:1 or better); controls at least 2rem tall; visible focus ring; labelled controls; `aria-live="polite"` on conversations and outcomes; keyboard-complete; usable at 200% zoom.
