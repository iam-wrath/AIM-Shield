# Cleanup of this folder (4 Oct)

We are not cloning the repo; we are submitting this folder. This file records what was cleared out, what was kept on purpose, and what is still yours to remove before submitting. Git was not touched.

## Removed (local, regenerable, or empty)
| What | Why |
| --- | --- |
| `aim_shield.db`, `backend/aim_shield.db` | Local SQLite event logs from running the app (decisions and request IDs). Recreated automatically. |
| `server.log`, `suite_run.log`, `docker_build.log` | Run logs. `*.log` is now git-ignored too. |
| `backend/.pytest_cache`, every `__pycache__` | Test and Python caches. |
| `probes/results.csv` | Byte-identical copy of `probes/results_batch1.csv` (it was just the runner's default output name). Nothing reads it. |
| `.gitkeep` in `attacks/`, `docs/`, `eval/`, `rag_docs/`, `backend/app/rag/` | Placeholders for folders that now have real files. |
| Raw invisible characters in 7 files | Replaced by `\uXXXX` escapes (see `docs/SECURITY-REVIEW.md`, S1). Not a deletion of data: the zero-width test attacks still work. |

## Kept on purpose
| What | Why it stays |
| --- | --- |
| `probes/make_probes*.py`, `probes*.json`, `probes/results_batch*.csv`, `probes/summarise.py` | The evidence behind `docs/probe-findings.md`. Anyone can re-run or audit it. |
| `attacks/make_starter.py`, `attacks/make_christabel.py` | They regenerate the attack JSON files. Edit the generator, not the JSON. |
| `backend/mock_server.py` | Offline rehearsal with a fake Guard and fake LLM (documented in the README). |
| `backend/replay_server.py` | The no-keys way for the organisers to run the lab with the recorded run. |
| `eval/run_suite.py`, `eval/results.json` | The evaluation and the real recorded run the scoreboard and replay read. |
| `docs/probe-findings.md`, `docs/architecture.svg`, `docs/SECURITY-REVIEW.md` | Submission documentation. |
| `.githooks/pre-commit`, `.gitignore`, `.dockerignore`, `Dockerfile`, `docker-compose.yml` | Needed to build, run and protect the repo. |

## Still yours to decide before submitting
| What | Size / note | Action |
| --- | --- | --- |
| **`.env`** | Holds the real Guard token and OpenAI key. | **If you submit by git push it is already ignored. If you zip or copy the folder, delete it first.** |
| `.venv/` | about 55 MB. Git-ignored. | Delete only if you submit a zip or folder; recreate with `python -m venv .venv` and `pip install -r backend/requirements-dev.txt`. |
| `frontend/node_modules/` | about 41 MB. Git-ignored. | Same: `npm install` brings it back. |
| `frontend/dist/` | the built UI. Git-ignored; Docker rebuilds it. | Delete if archiving; `npm run build` recreates it. The app only serves the UI if it exists when running without Docker. |
| `docs/CHRISTABEL-TASKS.md`, `docs/SUBMISSION-GUIDE.md` | Internal working notes for the two of you. | Delete before the first commit (the guide last); the README does not link to them. |
| `docs/CLEANUP.md` (this file) | Internal. | Delete before the first commit. |
| `.git/` | Yours. | Not touched. |

## One-shot commands
Run from the folder root in Git Bash. They only remove regenerable local files.

```bash
# after running tests or the app again
find . \( -name "__pycache__" -o -name ".pytest_cache" \) -not -path "./.venv/*" -not -path "./frontend/node_modules/*" -prune -exec rm -rf {} +
rm -f aim_shield.db backend/aim_shield.db *.log

# only if you submit an archive instead of pushing with git (this removes your real secrets from the folder):
rm -f .env
rm -rf .venv frontend/node_modules frontend/dist
```

## Last checks before you submit
- `.env` is not in the folder or not tracked: `git ls-files | grep -E "(^|/)\.env$"` prints nothing.
- `eval/results.json` has `"synthetic": false`.
- `cd backend && ../.venv/Scripts/python -m pytest` passes (91 tests).
- Secret scan is clean: `grep -rIlE "sai_[A-Za-z0-9_-]{8,}|sk-proj-[A-Za-z0-9_-]{40,}" --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git --exclude=.env .` prints nothing.
