# Security review of the whole build (4 Oct)

**Scope:** everything in this folder: the FastAPI backend and layers, the React Attack Lab, the Docker image and compose file, the probe/eval scripts, the data files (attacks, probes, rag_docs), the pre-commit hook and `.env` handling.
**Not covered:** git history (Kwaku handles git; see "Left for you" below), the organisers' Guard service, OpenAI's service.

## How it was checked
| Check | Tool / method | Result |
| --- | --- | --- |
| Python static analysis | `bandit` 1.9.4 over `backend/app`, dev servers, `eval/`, `probes/`, `attacks/` | 3 findings, all resolved or justified (S1, S9) |
| Python dependencies | `pip-audit` on `backend/requirements-dev.txt` | no known vulnerabilities |
| Frontend dependencies | `npm audit` | 2 dev-server advisories, fixed by upgrading Vite (S8); now 0 |
| Secrets in the tree | search for token shapes and for the actual `GUARD_TOKEN` / `LLM_KEY` values | only in `.env`, which is git-ignored and Docker-ignored |
| Secrets in the Docker image | listed the image's files, searched for `.env*` and `sai_` | none after fixes (S6, S7) |
| Hidden characters | scanned every text file for zero-width and bidirectional control characters | found in 7 files, now none (S1) |
| Hostile input against the running app | path traversal, bad enum values, 3 MB message, 10,000-character session id, wrong content type, missing fields | all handled; gaps found are S2, S4, S5 |
| Dangerous code patterns | searched for `eval`, `exec`, `pickle`, `subprocess`, `shell=True`, `innerHTML`, `dangerouslySetInnerHTML`, `localStorage` | none |
| Secret leakage paths | read all uses of the token and key; there is no logging code; settings dumps and upstream error bodies tested | token and key appear only in outgoing request headers |
| Pre-commit hook | ran its patterns on 4 realistic token shapes and on every real file | all 4 caught, no false positives |
| Regression tests | 91 tests, 6 of them security tests (`backend/tests/test_security.py`) | pass |

## Findings and what was done
| ID | Severity | Finding | Fix |
| --- | --- | --- | --- |
| S1 | Medium | Raw bidirectional-control and zero-width characters sat in 7 source/data files (bandit B613 "Trojan Source"). They were legitimate (a detection regex and test attacks) but invisible to reviewers. | Replaced with visible `\uXXXX` escapes; the two generators now write escapes; scan is clean; tests still pass. |
| S2 | Medium | The chat routes had no throttle. Anyone who can reach the app can burn the Guard quota (1,000/day) and the LLM key. | Per-client-IP sliding window on both chat routes, 60/min by default (`CHAT_RATE_LIMIT_PER_MIN`, 0 = off), answers 429 with `Retry-After`. |
| S3 | Medium | `docker compose` published the port on all network interfaces and ran the app as root. | Port published on `127.0.0.1` only; container runs as unprivileged `appuser`; `/data` owned by it. Verified live. |
| S4 | Low | Unbounded memory: any message size, and unlimited sessions in three in-memory stores. Reading chat history also created empty sessions. | Messages capped at 20,000 characters (422 above); each store keeps at most 2,000 sessions (oldest evicted); reading no longer creates sessions. |
| S5 | Low | `/docs`, `/redoc` and `/openapi.json` were public. | Disabled (routes are in the README). |
| S6 | Low | The Docker image contained a local `aim_shield.db` (event log: decisions and request IDs, no message text) because `.dockerignore` had `*.db`, which only matches the top level. | Patterns are now `**/*.db`, `**/*.log`; tests and caches excluded; image re-checked. |
| S7 | Low | A test used a fake token-shaped string, which our own pre-commit hook would rightly refuse to commit. | The test builds its fake secrets at runtime. |
| S8 | Low | `npm audit`: esbuild/Vite development-server advisories (affect `npm run dev` only, not the shipped static build). | Upgraded to Vite 7.3.6 and plugin-react 4.7; build works; audit shows 0. README now requires Node 20.19+ or 22+. |
| S9 | Info | bandit B106 twice: placeholder tokens (`mock-token`, `replay-only`) in the two offline dev servers. | Not secrets; marked `# nosec B106` with the reason. |

## Secrets handling (summary)
- `GUARD_TOKEN` and `LLM_KEY` live only in `.env` (ignored by git and Docker). They are `SecretStr` values, used only to build the `Authorization` header, and never logged, printed, stored or returned to the browser. The event log stores decisions and request IDs, not message text.
- Tests prove the token and key stay out of `repr()`, settings dumps and error bodies returned by the API.
- `.githooks/pre-commit` blocks a staged `.env`, a `sai_` token, a long `sk-proj-` key, a Bearer header carrying a Guard token, and a `GUARD_TOKEN` assignment that has a value. It only works once enabled: `git config core.hooksPath .githooks`.
- All test data is synthetic; the Guard is only ever sent synthetic text (the organisers' rule).

## Accepted risks (this is a local demo)
These are deliberate and are stated in the README limitations:
1. **No authentication.** The app is meant to be run locally. Compose binds to localhost only; native `uvicorn` listens on 127.0.0.1 by default. Do not expose it to a network or the internet.
2. **The customer's trust level (`persona`) comes from the browser.** Anyone who can reach the app can choose "verified". In a real system identity comes from the server session.
3. **The one-time code is a fixed mock value** (`482913`), visible in the code and docs.
4. **`/usage` is unauthenticated** and shows the team name and quota (localhost only).
5. **State is in memory** and lost on restart.
6. **Python requirements use lower bounds, not a lockfile.** `pip-audit` was clean today; re-run it before submitting.
7. **The layers are heuristic**; they will miss attacks we did not think of (see the README results and limitations).
8. **LLM output is shown as plain text** by React (no HTML rendering), so a hostile model reply cannot inject markup; no `dangerouslySetInnerHTML` is used anywhere.

## Left for you (cannot be done from here)
- **Git history scan** before the first push: `git log -p --all | grep -E "sai_[A-Za-z0-9_-]{8,}|sk-proj-[A-Za-z0-9_-]{40,}"` must print nothing (or run `gitleaks detect` if installed). Also run `git ls-files | grep -E "(^|/)\.env$"`, which must print nothing.
- **If you submit a zip or folder instead of a git push, delete `.env` first.** It holds the real Guard token and OpenAI key.
- **After the event:** revoke the OpenAI key (it is a personal key) and ask the organisers about the Guard token. Both were only ever on this machine, never in git or the image.
- Re-run `pip-audit -r backend/requirements-dev.txt` and `npm audit` (in `frontend/`) just before you submit.
