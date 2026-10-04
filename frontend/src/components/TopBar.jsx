import Icon from './Icon.jsx'
import Segmented from './Segmented.jsx'

export function quotaLabel(u) {
  if (!u) return 'Quota: checking'
  if (u.error) return 'Quota unavailable'
  const used = [u.used_today, u.used, u.requests_today, u.count].find((v) => typeof v === 'number')
  const limit = [u.daily_limit, u.limit, u.day_limit, u.max].find((v) => typeof v === 'number')
  if (used !== undefined && limit !== undefined) return `Quota ${used.toLocaleString()} / ${limit.toLocaleString()} today`
  return 'Quota'
}

export default function TopBar({ tab, setTab, live, setLive, usage, theme, onTheme, present, onPresent }) {
  return (
    <header className="topbar">
      <div className="wrap topbar-in">
        <div className="brand">
          <div>
            <h1>Aim Shield</h1>
            <p>Attack Lab</p>
          </div>
        </div>

        <nav aria-label="Views" className="views">
          <button aria-current={tab === 'lab' ? 'page' : undefined} onClick={() => setTab('lab')}>Lab</button>
          <button aria-current={tab === 'score' ? 'page' : undefined} onClick={() => setTab('score')}>Scoreboard</button>
        </nav>

        <div className="tools-right">
          <Segmented
            label="Mode"
            hideLabel
            name="mode"
            value={live ? 'live' : 'replay'}
            onChange={(v) => setLive(v === 'live')}
            options={[
              { value: 'live', label: 'Live', hint: 'The real Guard and model' },
              { value: 'replay', label: 'Replay', hint: 'Recorded results; nothing is sent' },
            ]}
          />
          <span className="quota" title="Guard requests used today">{live ? quotaLabel(usage) : 'No quota used'}</span>
          <button className="icon-btn" aria-pressed={present} onClick={onPresent} title="Presenter mode: larger text, less detail">
            <Icon name="screen" /> <span>Presenter</span>
          </button>
          <button
            className="icon-btn"
            onClick={onTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
          </button>
        </div>
      </div>
    </header>
  )
}
