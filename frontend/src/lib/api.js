export async function api(path, body) {
  try {
    const res = await fetch(path, body
      ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
      : undefined)
    const data = await res.json().catch(() => ({}))
    return { ok: res.ok, status: res.status, data }
  } catch (e) {
    return { ok: false, status: 0, data: { error: 'network', detail: String(e) } }
  }
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
export const sid = () => Math.random().toString(36).slice(2, 10)

// localStorage can be missing or blocked (private windows, previews): never let it break the page.
export const store = {
  get(k) {
    try { return localStorage.getItem(k) } catch { return null }
  },
  set(k, v) {
    try { localStorage.setItem(k, v) } catch { /* ignore */ }
  },
}
