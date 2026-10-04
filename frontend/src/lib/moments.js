// What each demo moment shows, in one line. Keyed by the leading number of the attack's `moment` label.
export const MOMENT_NOTES = {
  1: 'Legitimate verification works on both sides. Aim masks the one-time code before the model sees it.',
  2: 'A verified customer asks about her sister. The Guard allows it: watch the tool log on the left.',
  3: 'A stranger builds a scam over several harmless-looking messages. Each one passes the Guard alone.',
  4: 'A poisoned policy document tries to make the assistant ask for a PIN. Switch the document screen off to see the Output Sentinel.',
  5: 'Quick attacks, including what the Guard already handles well. We do not claim those.',
  6: 'The Guard is down or answers partially. Aim falls back to local checks and pauses money actions.',
}

export const momentNumber = (label) => Number((label || '').match(/^(\d+)/)?.[1]) || 0
export const momentName = (label) => (label || '').replace(/^\d+\.\s*/, '').replace(/\s*\(.*\)\s*$/, '')

export const LAYER_NAMES = {
  guard: 'the Guard',
  ghana_lens: 'Ghana Lens',
  base64_decoder: 'the Base64 decoder',
  conversation_memory: 'Conversation Memory',
  identity_binding: 'Identity Binding',
  chunker: 'the Chunker',
  failsafe: 'the Fail-safe',
  rag_screen: 'the document screen',
  output_sentinel: 'the Output Sentinel',
}

export const LAYER_SHORT = {
  guard: 'Guard',
  ghana_lens: 'Ghana Lens',
  base64_decoder: 'Base64',
  conversation_memory: 'Memory',
  identity_binding: 'Identity',
  chunker: 'Chunker',
  failsafe: 'Fail-safe',
  rag_screen: 'Documents',
  output_sentinel: 'Sentinel',
}

export const layerName = (l) => LAYER_NAMES[l] || l || 'a layer'

export const LEVEL_NAMES = ['Anonymous', 'Logged in as Ama', 'Verified']
