"""Demo server: Basic Auth from env, rate limit, booklet allowlist, errors instead of fake answers."""

import base64
import json
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import demo.server as demo_server  # noqa: E402
from booklint.llm import Call  # noqa: E402
from booklint.pipeline import Options, Pipeline  # noqa: E402

USER, PASSWORD = "demo-user", "dummy-test-password"


class MockLLM:
    model = "mock-apertus"

    def __init__(self, fail=False):
        self.fail = fail

    def chat(self, messages, usage, purpose, model=None, **params):
        if self.fail:
            raise RuntimeError("upstream down")
        usage.add(Call(purpose, self.model, 11, 3, 0.01, False))
        return {"content": json.dumps({"evidence": [1], "label": "entailment"})}


@pytest.fixture(scope="module")
def base_url():
    saved = (
        demo_server.BASIC_AUTH_USER,
        demo_server.BASIC_AUTH_PASSWORD,
        demo_server.AUTH_ENABLED,
    )
    (
        demo_server.BASIC_AUTH_USER,
        demo_server.BASIC_AUTH_PASSWORD,
        demo_server.AUTH_ENABLED,
    ) = USER, PASSWORD, True
    demo_server._models = ["mock-apertus", "mock-apertus-70b"]
    big = MockLLM()
    big.model = "mock-apertus-70b"
    demo_server._pipelines = {
        "mock-apertus": Pipeline(MockLLM(), Options(decompose=False, fewshot=0)),
        "mock-apertus-70b": Pipeline(big, Options(decompose=False, fewshot=0)),
    }
    server = demo_server.ThreadingHTTPServer(("127.0.0.1", 0), demo_server.DemoHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    demo_server._models, demo_server._pipelines = None, {}
    (
        demo_server.BASIC_AUTH_USER,
        demo_server.BASIC_AUTH_PASSWORD,
        demo_server.AUTH_ENABLED,
    ) = saved


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    demo_server._rate_limits.clear()
    yield
    demo_server._rate_limits.clear()


def _auth(user=USER, password=PASSWORD):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def _post(base_url, payload, auth=True):
    req = Request(
        f"{base_url}/api/predict", data=json.dumps(payload).encode(), method="POST"
    )
    req.add_header("Content-Type", "application/json")
    if auth:
        req.add_header("Authorization", _auth())
    return urlopen(req)


def test_no_credentials_in_frontend():
    for name in ("demo.js", "index.html"):
        text = (ROOT / "demo" / name).read_text(encoding="utf-8")
        assert "Authorization" not in text and "btoa(" not in text


def test_health_public(base_url):
    with urlopen(f"{base_url}/api/health") as resp:
        assert json.loads(resp.read())["status"] == "ok"


def test_requires_basic_auth(base_url):
    with pytest.raises(HTTPError) as exc:
        urlopen(f"{base_url}/api/presets")
    assert exc.value.code == 401
    bad = Request(f"{base_url}/api/presets")
    bad.add_header("Authorization", _auth(password="wrong"))
    with pytest.raises(HTTPError) as exc:
        urlopen(bad)
    assert exc.value.code == 401
    good = Request(f"{base_url}/api/presets")
    good.add_header("Authorization", _auth())
    with urlopen(good) as resp:
        data = json.loads(resp.read())
    assert data["synthetic"] is True and data["presets"]


def test_server_source_not_served(base_url):
    req = Request(f"{base_url}/server.py")
    req.add_header("Authorization", _auth())
    with pytest.raises(HTTPError) as exc:
        urlopen(req)
    assert exc.value.code == 404


def test_info_hides_key(base_url):
    req = Request(f"{base_url}/api/info")
    req.add_header("Authorization", _auth())
    with urlopen(req) as resp:
        raw = resp.read().decode()
    assert "api_key" not in raw and "LLM_API_KEY" not in raw


def test_info_shows_both_limits(base_url):
    req = Request(f"{base_url}/api/info")
    req.add_header("Authorization", _auth())
    with urlopen(req) as resp:
        info = json.loads(resp.read().decode())
    assert info["rate_limit"].endswith(" s")
    assert info["global_limit"] == f"{demo_server.GLOBAL_LIMIT_MAX_REQUESTS} requests / {demo_server.GLOBAL_LIMIT_WINDOW_SECONDS} s"


def test_predict_beginner_returns_measured_metrics(base_url):
    payload = {
        "id": "t-01",
        "mode": "beginner",
        "claim": "Die E-ID ist freiwillig.",
        "reference": "Die E-ID ist freiwillig und kostenlos.",
    }
    with _post(base_url, payload) as resp:
        data = json.loads(resp.read())
    assert set(data) == {"id", "label", "label_name", "evidence", "metrics"}
    assert data["id"] == "t-01" and data["label"] == 0
    assert data["evidence"] and set(data["evidence"][0]) == {"page", "text"}
    assert (
        data["metrics"]["input_tokens"] == 11 and data["metrics"]["output_tokens"] == 3
    )


def test_advanced_rejects_unknown_booklet(base_url):
    for booklet in ("https://example.com/x.pdf", "C:/Windows/win.ini", "1999-01-01"):
        with pytest.raises(HTTPError) as exc:
            _post(base_url, {"mode": "advanced", "claim": "x", "booklet": booklet})
        assert exc.value.code == 400


def test_validation_errors(base_url):
    with pytest.raises(HTTPError) as exc:
        _post(base_url, {"mode": "beginner", "claim": "x"})
    assert exc.value.code == 400
    with pytest.raises(HTTPError) as exc:
        _post(base_url, {"mode": "beginner", "claim": "x" * 5000, "reference": "y"})
    assert exc.value.code == 400


def test_upstream_failure_is_an_error_not_a_label(base_url):
    demo_server._pipelines["mock-apertus"] = Pipeline(
        MockLLM(fail=True), Options(decompose=False, fewshot=0)
    )
    try:
        with pytest.raises(HTTPError) as exc:
            _post(base_url, {"mode": "beginner", "claim": "x", "reference": "y"})
        assert exc.value.code == 502
        assert "upstream" not in exc.value.read().decode()
    finally:
        demo_server._pipelines["mock-apertus"] = Pipeline(
            MockLLM(), Options(decompose=False, fewshot=0)
        )


def test_rate_limit(base_url):
    demo_server._rate_limits["127.0.0.1"] = [
        time.time()
    ] * demo_server.RATE_LIMIT_MAX_REQUESTS
    with pytest.raises(HTTPError) as exc:
        _post(base_url, {"mode": "beginner", "claim": "x", "reference": "y"})
    assert exc.value.code == 429
    assert exc.value.headers["Retry-After"]


def test_forwarded_for_ignored_without_trust_proxy(base_url):
    demo_server._rate_limits["127.0.0.1"] = [
        time.time()
    ] * demo_server.RATE_LIMIT_MAX_REQUESTS
    req = Request(
        f"{base_url}/api/predict",
        data=b'{"mode":"beginner","claim":"x","reference":"y"}',
        method="POST",
    )
    req.add_header("Authorization", _auth())
    req.add_header("X-Forwarded-For", "203.0.113.9")
    with pytest.raises(HTTPError) as exc:
        urlopen(req)
    assert exc.value.code == 429


def test_start_without_credentials_fails(monkeypatch):
    monkeypatch.setattr(demo_server, "BASIC_AUTH_USER", "")
    monkeypatch.setattr(demo_server, "BASIC_AUTH_PASSWORD", "")
    with pytest.raises(SystemExit):
        demo_server.main(["--port", "0"])


def test_model_choice_is_listed_used_and_checked(base_url):
    req = Request(f"{base_url}/api/info")
    req.add_header("Authorization", _auth())
    info = json.loads(urlopen(req).read())
    assert info["models"] == ["mock-apertus", "mock-apertus-70b"] and info["model"] == "mock-apertus"
    resp = _post(base_url, {"mode": "beginner", "claim": "x", "reference": "y", "model": "mock-apertus-70b"})
    assert resp.headers["X-Model"] == "mock-apertus-70b" and "model" not in json.loads(resp.read())
    assert _post(base_url, {"mode": "beginner", "claim": "x", "reference": "y"}).headers["X-Model"] == "mock-apertus"
    with pytest.raises(HTTPError) as exc:
        _post(base_url, {"mode": "beginner", "claim": "x", "reference": "y", "model": "gpt-4"})
    assert exc.value.code == 400

def test_public_mode_without_auth_keeps_rate_limit(base_url, monkeypatch):
    """Public deployment (--no-auth): no credentials needed, but the per-IP rate limit still applies."""
    monkeypatch.setattr(demo_server, "AUTH_ENABLED", False)
    payload = {"mode": "beginner", "claim": "x", "reference": "y"}
    assert _post(base_url, payload, auth=False).status == 200
    demo_server._rate_limits["127.0.0.1"] = [
        time.time()
    ] * demo_server.RATE_LIMIT_MAX_REQUESTS
    with pytest.raises(HTTPError) as exc:
        _post(base_url, payload, auth=False)
    assert exc.value.code == 429


def test_global_limit_caps_all_clients(base_url, monkeypatch):
    """Overall hourly cap: once reached, every client gets a friendly 429, even with a fresh per-IP budget."""
    monkeypatch.setattr(demo_server, "AUTH_ENABLED", False)
    payload = {"mode": "beginner", "claim": "x", "reference": "y"}
    demo_server._rate_limits.clear()
    monkeypatch.setattr(demo_server, "_global_hits", [])
    assert _post(base_url, payload, auth=False).status == 200
    demo_server._global_hits[:] = [time.time()] * demo_server.GLOBAL_LIMIT_MAX_REQUESTS
    demo_server._rate_limits.clear()
    with pytest.raises(HTTPError) as exc:
        _post(base_url, payload, auth=False)
    assert exc.value.code == 429
    assert "hourly limit" in exc.value.read().decode()
    # old hits fall out of the window again
    demo_server._global_hits[:] = [time.time() - demo_server.GLOBAL_LIMIT_WINDOW_SECONDS - 1] * demo_server.GLOBAL_LIMIT_MAX_REQUESTS
    demo_server._rate_limits.clear()
    assert _post(base_url, payload, auth=False).status == 200
