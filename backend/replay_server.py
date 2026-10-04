"""NO-KEYS SERVER: the Attack Lab with the recorded run only (no Guard token, no LLM key).

    cd backend && python -m uvicorn replay_server:app --port 8000
    then tick "Replay recorded run" in the page.

Live sending is disabled and says why. For live demos use app.main with a real .env.
"""
from __future__ import annotations

from app.config import Settings
from app.guard_client import GuardClient, GuardError
from app.llm_client import LLMClient, LLMError
from app.main import create_app

MSG = "replay-only mode: no Guard token or LLM key configured. Tick 'Replay recorded run', or add keys to .env and run app.main."


class _NoGuard(GuardClient):
    async def _request(self, method, path, *, json=None, auth=True):
        raise GuardError(MSG)


class _NoLLM(LLMClient):
    async def complete(self, messages, *, system=None):
        raise LLMError(MSG)


_s = Settings(_env_file=None, guard_token="replay-only",  # nosec B106 (placeholder, no network)
              guard_url="https://replay.invalid", db_path=":memory:")
app = create_app(_s, llm=_NoLLM(), guard=_NoGuard(_s))
app.state.replay_only = True
app.state.replay_message = MSG
