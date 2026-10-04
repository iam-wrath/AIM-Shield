# Submission guide: from this folder to a repo the organisers can run

Deadline: **Sunday 4 Oct**. Presentation: **Monday 5 Oct**. The organisers set up from your repo before the presentation, so it must run from a fresh copy with only their keys added.

All commands are for Git Bash from the repo root. Everything marked "expect" tells you what a correct result looks like. If a result differs, stop and fix it before going on.

Already done in the folder: tests pass (90), secret scan clean, dependency audits clean, caches and logs removed, line endings normalised to LF with a `.gitattributes`, the pre-commit hook fixed (it had Windows line endings and would have failed on Mac/Linux), Docker build and run verified, README has a "Quick start for the organisers".
---

## Step 1. Decide four things first
1. **Public or private repo?** Private is safer (the code runs against a shared Guard). If private, you must invite the organisers (ask them which GitHub accounts). If public, only the secret checks below stand between you and a leak.
2. **How do you tell the organisers where it is?** Use the same channel they used to give you the brief. Send the repo URL **and the tag** from Step 8.
3. **Which internal files to drop.** The other internal notes are already deleted. This guide is a working note for the two of you, not for judges: delete `docs/SUBMISSION-GUIDE.md` last, before the first commit.
   Keep: `docs/probe-findings.md`, `docs/architecture.svg`.
4. **License.** Optional. With no license file nobody has a licence to reuse the code, which is fine for a hackathon. Add a `LICENSE` (MIT is the usual choice) only if you want people to reuse it.

## Step 2. Check the folder before committing
```bash
cd backend && ../.venv/Scripts/python -m pytest -q && cd ..        # expect: 91 passed
python -c "import json;d=json.load(open('eval/results.json',encoding='utf-8'));print('synthetic =',d['synthetic'],'| cases =',len(d['cases']))"   # expect: synthetic = False
grep -rIlE "sai_[A-Za-z0-9_-]{8,}|sk-proj-[A-Za-z0-9_-]{40,}" --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git --exclude=.env . || echo clean   # expect: clean
find . \( -name "__pycache__" -o -name ".pytest_cache" \) -not -path "./.venv/*" -not -path "./frontend/node_modules/*" -prune -exec rm -rf {} + ; rm -f aim_shield.db backend/aim_shield.db *.log
```
Also re-run the dependency audits just before you submit (new advisories appear daily):
```bash
.venv/Scripts/python -m pip_audit -r backend/requirements-dev.txt --progress-spinner off     # expect: No known vulnerabilities found
(cd frontend && npm audit)                                                                   # expect: found 0 vulnerabilities
```
Read the README once as a stranger. It should say what you built, which system you protect (KwikPay Assist), how to run it, the evidence, and "no token or real personal data in this repo". Christabel's final numbers go in the Results section after her last suite run.

## Step 3. Turn the hook on and test it (before your first commit)
```bash
git config core.hooksPath .githooks
git config core.autocrlf false          # .gitattributes already enforces LF; this stops Git for Windows rewriting it
```
Prove the hook really blocks a secret. This commit **must be refused**:
```bash
printf 'GUARD_%s=abc123token\n' TOKEN > _hooktest.txt   # built at runtime so this line itself is not flagged
git add _hooktest.txt
git commit -m "hook test"               # expect: "pre-commit: staged changes look like they contain a Guard token ..." and no commit
git reset -q _hooktest.txt && rm -f _hooktest.txt
```
If the commit succeeded, the hook is not running: re-check the `hooksPath` line and that `.githooks/pre-commit` exists. Do not continue until it blocks.

## Step 4. Stage, then inspect before you commit
```bash
git add -A
git status --short | head -120
git ls-files | wc -l                                                      # expect: roughly 115 to 120; the point is that nothing like .env, a db, a log or node_modules is in the list
git ls-files | grep -E "(^|/)\.env$" || echo ".env not tracked"           # expect: .env not tracked
git ls-files | grep -E "node_modules|\.venv|(^|/)dist/|\.db$|\.log$|__pycache__" || echo "no build/local files tracked"   # expect: no build/local files tracked
git add --renormalize .                                                   # makes git re-apply the LF rule to every file
git update-index --chmod=+x .githooks/pre-commit                          # keeps the hook executable on Mac/Linux
```
Check the essentials are tracked (prints nothing when all are present):
```bash
for f in README.md Dockerfile docker-compose.yml .env.example .gitignore .gitattributes .dockerignore .githooks/pre-commit backend/requirements.txt frontend/package.json frontend/package-lock.json eval/results.json eval/run_suite.py docs/probe-findings.md docs/architecture.svg attacks/starter.json attacks/christabel.json rag_docs/reversal_policy_UPDATED.md backend/app/main.py backend/replay_server.py; do git ls-files --error-unmatch "$f" >/dev/null 2>&1 || echo "MISSING: $f"; done
```

## Step 5. Commit
One honest commit is fine for a hackathon; a few logical ones read better. Either way, **do not use `--no-verify`**.
```bash
git commit -m "Aim Shield: Guard-side safety layers, Attack Lab and evidence

SecureAI Hackathon 2026, Challenge 3. Protects KwikPay Assist (a fictional mobile
money support agent). Adds Ghana Lens, Identity Binding, Conversation Memory,
Base64 decoder, Output Sentinel and a fail-safe beside the SecureAI Guard,
with probe evidence, an evaluation suite and an Attack Lab UI."
```
If the hook refuses, it printed which line looks like a token: fix the text, never bypass it.

## Step 6. Scan the history (not just the files)
Do this **before** the first push. Nothing may print:
```bash
git log -p --all | grep -E "sai_[A-Za-z0-9_-]{8,}|sk-proj-[A-Za-z0-9_-]{40,}" || echo "history clean"
git log --all --name-only --pretty=format: | grep -E "(^|/)\.env$" || echo ".env never committed"
git log --all -p | grep -E "^\+GUARD_TOKEN[=]." || echo "no filled token lines"
```
`gitleaks detect` is an extra check if you have it installed (it was not on this machine).

## Step 7. Push
```bash
git branch -M main
git remote add origin <URL-of-the-empty-repo>      # create the repo on GitHub first, without a README or licence, so it starts empty
git push -u origin main
```

## Step 8. Tag the submission
A tag is the exact version the organisers should run, so later pushes cannot change what they were told to use.
```bash
git tag -a v1.0-submission -m "Submitted to SecureAI Hackathon 2026, Challenge 3"
git push origin v1.0-submission
git rev-parse --short HEAD                          # note this commit id
```

## Step 9. Look at it on GitHub as the organisers will
- The README renders, the architecture picture shows, the tables are not broken.
- Browse the file list: **no `.env`**, no `node_modules`, no `.venv`, no `.db` or `.log`.
- Search the repo (the `/` key, "t" to find files) for `sai_` and `sk-proj`: nothing.
- The repository size is small (about 1 MB).
- If it is private: open the repo in a private/incognito window to confirm strangers cannot see it, and add the organisers.

## Step 10. Test what you pushed (recommended, about 10 minutes)
You said you would not clone; this is the only test that proves the repo works without your local files, so it is worth the time. Do it in a throwaway folder:
```bash
cd /tmp && git clone --branch v1.0-submission <URL> aim-check && cd aim-check
cp .env.example .env            # then paste your Guard URL, token, OpenAI URL, key and model into .env
docker compose up --build       # expect: app starts; open http://localhost:8000
```
In the browser: pick an attack from the dropdown and press Send (live), then tick **Replay recorded run** and replay one. Then check the no-keys path in a second fresh clone with no `.env`: `docker compose up --build replay`, open http://localhost:8000, tick **Replay recorded run**.
When finished: `docker compose down -v` and `docker compose --profile replay down -v`, delete the folders, and remember the first one holds your keys in `.env`.

If you really will not clone: at least run `git archive --format=tar HEAD | tar -t | head -150` and check the list looks right, and re-run the "essentials" loop from Step 4.

## Step 11. What to send the organisers
- The repo URL and the tag `v1.0-submission` (and the commit id from Step 8).
- One line on running it: "Copy `.env.example` to `.env`, add your Guard URL and token plus any OpenAI-compatible key, then `docker compose up --build`. No keys are needed for the recorded-run mode: see the README Quick start."
- The system we protect: **KwikPay Assist**, a fictional mobile money support agent. No token or real personal data is in the repo.

## After submitting
- **Freeze.** Only push real bug fixes; never force-push or move the tag. If you must change something, tell the organisers the new commit.
- **Demo day (Mon 5 Oct):** run from a fresh `docker compose up --build` the night before. The Guard quota is 1,000/day (30/min) and resets at 00:00 UTC; the demo needs under about 15 calls. Keep **Replay recorded run** and Christabel's backup video as the fallback if the network or the Guard fails. Bring the laptop and a hotspot.
- **After the event:** revoke the OpenAI key, and ask the organisers about the Guard token.

## If something goes wrong
| Problem | What to do |
| --- | --- |
| A token reached a commit that is **not pushed yet** | `git reset --soft HEAD~1`, remove it, recommit. Never `--no-verify`. |
| A token was **pushed** (even for a minute) | Treat it as leaked: revoke the OpenAI key now, tell the organisers so they replace the Guard token, then remove it from history (`git filter-repo` or BFG) and force-push once. Do this before the deadline if you can. |
| The hook did not block the test in Step 3 | Run `git config core.hooksPath` (expect `.githooks`); check `.githooks/pre-commit` exists and has LF line endings. |
| `docker compose up` cannot find `.env` | Compose needs the file to exist: `cp .env.example .env`. |
| Port 8000 is busy | Stop the other server, or change the left side of the port mapping in `docker-compose.yml`. |
| Replay mode says no recorded run | `eval/results.json` is missing or the server was started from the wrong folder. |
