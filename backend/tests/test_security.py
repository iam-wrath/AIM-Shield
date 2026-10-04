"""Hardening checks: input limits, rate limiting, bounded memory, no public docs, secrets stay secret."""
import respx
from fastapi.testclient import TestClient

from app import kwikpay
from app.assistant import SessionStore
from app.config import Settings
from app.kwikpay import AuthStore
from app.main import create_app
from tests.conftest import GUARD, make_settings, ok_body
from tests.test_main import FakeLLM

PROMPT, RESP = f"{GUARD}/v1/check/prompt", f"{GUARD}/v1/check/response"


def app_client(**settings):
    return TestClient(create_app(make_settings(**settings), llm=FakeLLM()))


def test_oversized_message_rejected_before_any_work():
    with app_client() as c:  # no Guard routes mocked: any Guard call would raise
        r = c.post("/chat/shielded", json={"session_id": "s", "message": "A" * 20001})
        assert r.status_code == 422


def test_api_docs_are_not_published():
    with app_client() as c:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert c.get(path).status_code == 404


@respx.mock
def test_chat_routes_are_rate_limited_per_client():
    respx.post(PROMPT).respond(200, json=ok_body())
    respx.post(RESP).respond(200, json=ok_body())
    with app_client(chat_rate_limit_per_min=3) as c:
        codes = [c.post("/chat/guard-only", json={"session_id": "r", "message": "hello"}).status_code for _ in range(5)]
        assert codes == [200, 200, 200, 429, 429]
        r = c.post("/chat/shielded", json={"session_id": "r", "message": "hello"})
        assert r.status_code == 429 and r.headers["Retry-After"] == "10"  # one budget for both chat routes
        assert c.get("/health").status_code == 200  # other routes are not limited


def test_session_stores_are_bounded(monkeypatch):
    monkeypatch.setattr(kwikpay, "MAX_SESSIONS", 5)
    auth = AuthStore()
    for i in range(20):
        auth.ensure("shielded", f"s{i}", "ama")
    assert len(auth._s) == 5 and ("shielded", "s19") in auth._s
    store = SessionStore()
    for i in range(2100):
        store.append_turn("m", f"s{i}", "u", "a")
    assert len(store._data) <= 2000
    store.history("m", "never-seen")
    assert ("m", "never-seen") not in store._data  # reading history must not create sessions


def test_secrets_never_appear_in_settings_dumps_or_error_bodies():
    # built at runtime so no token-shaped string sits in the repo (the pre-commit hook would rightly refuse it)
    guard, llm = "sa" + "i_" + "X" * 24, "sk" + "-proj-" + "Y" * 48
    s = Settings(_env_file=None, guard_token=guard, llm_key=llm)
    for blob in (repr(s), str(s.model_dump()), s.model_dump_json()):
        assert guard not in blob and llm not in blob and "XXXXXXXX" not in blob and "YYYYYYYY" not in blob


@respx.mock
def test_upstream_errors_do_not_leak_credentials_to_the_client():
    respx.post(PROMPT).respond(401, json={"error": "unauthorized", "echo": "Bearer test-token-not-real"})
    with app_client() as c:
        r = c.post("/chat/guard-only", json={"session_id": "e", "message": "hello"})
    assert "test-token-not-real" not in r.text and "Bearer" not in r.text
