import httpx
import pytest
import respx

from app.guard_client import (
    GuardAuthError,
    GuardDailyQuotaExceeded,
    GuardRateLimited,
    GuardTextRequired,
    GuardTextTooLong,
    GuardUnavailable,
)
from tests.conftest import GUARD, ok_body

PROMPT = f"{GUARD}/v1/check/prompt"


@respx.mock
async def test_check_prompt_parses_and_sends_auth(guard):
    route = respx.post(PROMPT).respond(200, json=ok_body(False, ["injection"]))
    r = await guard.check_prompt("hi")
    assert r.allowed is False and r.flags == ["injection"]
    assert r.request_id == "r1" and r.latency_ms == 12 and r.round_trip_ms is not None
    assert r.top_confidence == "HIGH" and not r.cached
    req = route.calls[0].request
    assert req.headers["Authorization"] == "Bearer test-token-not-real"
    assert req.content == b'{"text":"hi"}' or b'"text"' in req.content


@respx.mock
async def test_cache_by_endpoint_and_text(guard):
    p = respx.post(PROMPT).respond(200, json=ok_body())
    resp = respx.post(f"{GUARD}/v1/check/response").respond(200, json=ok_body())
    a = await guard.check_prompt("same")
    b = await guard.check_prompt("same")
    await guard.check_response("same")  # different endpoint -> not a cache hit
    assert p.call_count == 1 and resp.call_count == 1
    assert b.cached and b.round_trip_ms == 0 and not a.cached


@respx.mock
async def test_partial_not_cached(guard):
    p = respx.post(PROMPT).respond(200, json=ok_body(status="partial"))
    await guard.check_prompt("x")
    await guard.check_prompt("x")
    assert p.call_count == 2


async def test_too_long_checked_locally(guard):
    with respx.mock:  # no routes: any HTTP call would raise
        with pytest.raises(GuardTextTooLong):
            await guard.check_prompt("a" * 4001)
        await_ok = respx.post(PROMPT).respond(200, json=ok_body())
        await guard.check_prompt("a" * 4000)
        assert await_ok.called


async def test_empty_text_local(guard):
    with pytest.raises(GuardTextRequired):
        await guard.check_prompt("  ")


@respx.mock
async def test_status_code_mapping(guard):
    respx.post(PROMPT).mock(side_effect=[
        httpx.Response(401, json={"error": "unauthorized"}),
        httpx.Response(413, json={"error": "text_too_long"}),
        httpx.Response(400, json={"error": "text_required"}),
    ])
    with pytest.raises(GuardAuthError):
        await guard.check_prompt("a")
    with pytest.raises(GuardTextTooLong):
        await guard.check_prompt("b")
    with pytest.raises(GuardTextRequired):
        await guard.check_prompt("c")


@respx.mock
async def test_502_retries_with_backoff_then_succeeds(guard, sleeps):
    route = respx.post(PROMPT).mock(side_effect=[
        httpx.Response(502, json={"error": "guard_unavailable"}),
        httpx.Response(503, json={"error": "service_busy"}),
        httpx.Response(200, json=ok_body()),
    ])
    r = await guard.check_prompt("x")
    assert r.allowed and route.call_count == 3 and len(sleeps) == 2


@respx.mock
async def test_502_exhausted(guard):
    respx.post(PROMPT).respond(502, json={"error": "guard_unavailable"})
    with pytest.raises(GuardUnavailable):
        await guard.check_prompt("x")
    assert guard.calls == 4  # 1 + 3 retries


@respx.mock
async def test_network_error_retries(guard):
    respx.post(PROMPT).mock(side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json=ok_body())])
    assert (await guard.check_prompt("x")).allowed


@respx.mock
async def test_rate_limited_honours_retry_after(guard, sleeps):
    respx.post(PROMPT).mock(side_effect=[
        httpx.Response(429, json={"error": "rate_limited"}, headers={"Retry-After": "7"}),
        httpx.Response(200, json=ok_body()),
    ])
    assert (await guard.check_prompt("x")).allowed
    assert sleeps == [7.0]


@respx.mock
async def test_rate_limited_gives_up(guard):
    respx.post(PROMPT).respond(429, json={"error": "rate_limited"}, headers={"Retry-After": "3"})
    with pytest.raises(GuardRateLimited) as ei:
        await guard.check_prompt("x")
    assert ei.value.retry_after == 3.0


@respx.mock
async def test_daily_quota_distinct_and_not_retried(guard, sleeps):
    route = respx.post(PROMPT).respond(429, json={"error": "daily_quota_exceeded"})
    with pytest.raises(GuardDailyQuotaExceeded):
        await guard.check_prompt("x")
    assert route.call_count == 1 and sleeps == []


@respx.mock
async def test_usage_and_health(guard):
    u = respx.get(f"{GUARD}/v1/usage").respond(200, json={"used": 3})
    h = respx.get(f"{GUARD}/health").respond(200, json={"status": "ok"})
    assert (await guard.usage()) == {"used": 3}
    assert (await guard.health()) == {"status": "ok"}
    assert "Authorization" in u.calls[0].request.headers
    assert "Authorization" not in h.calls[0].request.headers


@respx.mock
async def test_cache_can_be_disabled(settings):
    from app.guard_client import GuardClient
    g = GuardClient(settings, cache=False)
    route = respx.post(PROMPT).respond(200, json=ok_body())
    await g.check_prompt("same")
    await g.check_prompt("same")
    assert route.call_count == 2
    await g.aclose()
