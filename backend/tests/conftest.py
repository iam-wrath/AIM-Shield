import functools

import httpx._transports.default as _httpx_default
import pytest

# Building an SSL context takes ~3 s per client on Windows; tests never use TLS, so cache one.
_httpx_default.create_ssl_context = functools.lru_cache(maxsize=None)(_httpx_default.create_ssl_context)

from app.config import Settings
from app.guard_client import GuardClient

GUARD = "https://guard.test"


def make_settings(**kw) -> Settings:
    base = dict(guard_url=GUARD, guard_token="test-token-not-real", llm_url="https://llm.test/v1",
                llm_model="m", db_path=":memory:", guard_backoff_base=0.0)
    base.update(kw)
    return Settings(_env_file=None, **base)


def ok_body(allowed=True, flags=None, status="complete", rid="r1"):
    flags = flags or []
    return {
        "allowed": allowed, "flags": flags, "status": status,
        "checks": {"injection": {"ran": True, "flagged": "injection" in flags, "confidence": "HIGH"}},
        "request_id": rid, "latency_ms": 12,
    }


@pytest.fixture
def settings():
    return make_settings()


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
async def guard(settings, sleeps):
    async def fake_sleep(s):
        sleeps.append(s)

    g = GuardClient(settings, sleep=fake_sleep)
    yield g
    await g.aclose()
