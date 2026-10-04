// Small stroke icons. Decorative: the meaning is always carried by a word next to the icon.
const PATHS = {
  check: <path d="M4 10.5l4 4 8-9" />,
  shield: <path d="M10 2.5l6 2.2v5c0 3.6-2.5 6.3-6 7.8-3.5-1.5-6-4.2-6-7.8v-5z" />,
  'shield-check': (
    <>
      <path d="M10 2.5l6 2.2v5c0 3.6-2.5 6.3-6 7.8-3.5-1.5-6-4.2-6-7.8v-5z" />
      <path d="M7 10l2.2 2.2L13 8" />
    </>
  ),
  alert: (
    <>
      <path d="M10 3l8 14H2z" />
      <path d="M10 8v4M10 14.5v.01" />
    </>
  ),
  info: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 9v5M10 6.5v.01" />
    </>
  ),
  minus: <path d="M5 10h10" />,
  changed: (
    <>
      <circle cx="10" cy="10" r="6.5" />
      <path d="M6.5 10h7" />
    </>
  ),
  sun: (
    <>
      <circle cx="10" cy="10" r="3.2" />
      <path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4" />
    </>
  ),
  moon: <path d="M16 12.5A6.5 6.5 0 0 1 7.5 4a6.5 6.5 0 1 0 8.5 8.5z" />,
  screen: (
    <>
      <rect x="3" y="4" width="14" height="9" rx="1.5" />
      <path d="M7 17h6M10 13v4" />
    </>
  ),
  chevron: <path d="M6 8l4 4 4-4" />,
}

export default function Icon({ name, size = '1.125em' }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  )
}
