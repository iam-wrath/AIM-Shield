# Submission checklist (repo due 4 Oct, presentation 5 Oct)

Nothing here has been run yet. Git has not been used for commits so far; do not start until Kwaku says go.

1. Stop the dev server and delete local-only files: `server.log`, `suite_run.log`, `*.db`, `.venv`, `frontend/node_modules` are all git-ignored or removable. `frontend/dist` is ignored too (Docker builds it).
2. `git status`: confirm `.env` is NOT listed. Confirm `eval/results.json` has `"synthetic": false`.
3. Secret scan of the working tree before the first commit (no git needed):
   `grep -rIlE "sai_[A-Za-z0-9_-]{8,}|sk-proj-[A-Za-z0-9_-]{40,}" --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git .` should print only `.githooks/pre-commit`.
4. Commit, then scan history: `gitleaks detect` if installed, otherwise `git log -p | grep -E "sai_|sk-proj-"` must find nothing.
5. Enable the hook for everyone: `git config core.hooksPath .githooks`.
6. Push to the team's remote (Kwaku). Check the repo page: no `.env`, README renders, `docs/architecture.svg` shows.
7. Clean-clone test in a new folder: clone, `cp .env.example .env`, add keys, `docker compose up` (Docker Desktop must be running), open http://localhost:8000. Also test the no-keys path with `replay_server`.
8. Tell the organisers: their own Guard token and an LLM key go in `.env`; replay mode works without keys.
