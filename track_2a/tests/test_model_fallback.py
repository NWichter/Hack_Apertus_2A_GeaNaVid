"""Model-name fallback against a local mock of an OpenAI-compatible endpoint (no network, no real LLM).

The judges' proxy may name the Apertus models differently from our default. At start the CLI makes a test call;
if the model is unknown it reads /models, else it tries known spellings; every change and failure is loud.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from openai import OpenAI

from booklint import llm as llm_module
from booklint.cli import main

ANSWER = '{"evidence": [1], "label": "entailment"}'


class Endpoint:
    def __init__(self, served, list_models=True, unknown_status=404):
        self.served, self.list_models, self.unknown_status = (
            set(served),
            list_models,
            unknown_status,
        )
        self.asked = []
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def _send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models") and endpoint.list_models:
                    self._send(
                        200,
                        {
                            "object": "list",
                            "data": [
                                {"id": m, "object": "model"}
                                for m in sorted(endpoint.served)
                            ],
                        },
                    )
                else:
                    self._send(404, {"error": {"message": "Not Found"}})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                model = body.get("model")
                endpoint.asked.append(model)
                if model not in endpoint.served:
                    self._send(
                        endpoint.unknown_status,
                        {"error": {"message": f"The model `{model}` does not exist."}},
                    )
                    return
                self._send(
                    200,
                    {
                        "id": "x",
                        "object": "chat.completion",
                        "created": 0,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "finish_reason": "stop",
                                "message": {"role": "assistant", "content": ANSWER},
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 11,
                            "completion_tokens": 7,
                            "total_tokens": 18,
                        },
                    },
                )

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def client(self):
        return OpenAI(base_url=self.url, api_key="test-key", max_retries=0)

    def close(self):
        self.server.shutdown()


class _Err:
    def __init__(self, capsys):
        self.capsys, self.seen = capsys, ""

    def getvalue(self):
        self.seen += self.capsys.readouterr().err
        return self.seen


@pytest.fixture
def stderr(capsys):
    llm_module._RESOLVED.clear()
    return _Err(capsys)


def test_served_name_is_kept_quietly(stderr):
    ep = Endpoint(["apertus-v1.5-8b", "apertus-v1.5-70b"])
    try:
        assert (
            llm_module.resolve_model(ep.client(), "apertus-v1.5-70b")
            == "apertus-v1.5-70b"
        )
        assert ep.asked == ["apertus-v1.5-70b"] and "WARNING" not in stderr.getvalue()
    finally:
        ep.close()


@pytest.mark.parametrize(
    "wanted,expected",
    [
        ("apertus-v1.5-70b", "swiss-ai/Apertus-v1.5-70B"),
        ("apertus-v1.5-8b", "swiss-ai/Apertus-v1.5-8B"),
    ],
)
def test_unknown_name_takes_same_size_from_the_model_list(stderr, wanted, expected):
    ep = Endpoint(
        ["swiss-ai/Apertus-v1.5-8B", "swiss-ai/Apertus-v1.5-70B", "other/llama-70b"]
    )
    try:
        assert llm_module.resolve_model(ep.client(), wanted) == expected
        assert f"using '{expected}' from the endpoint's model list" in stderr.getvalue()
    finally:
        ep.close()


def test_list_without_the_size_takes_the_first_apertus_model_and_says_so(stderr):
    ep = Endpoint(["meta/llama-3", "swiss-ai/Apertus-v1.5-8B"])
    try:
        assert (
            llm_module.resolve_model(ep.client(), "apertus-v1.5-70b")
            == "swiss-ai/Apertus-v1.5-8B"
        )
        assert "is not the configured size" in stderr.getvalue()
    finally:
        ep.close()


@pytest.mark.parametrize("status", [400, 403, 404])
def test_without_a_model_list_known_spellings_are_tried(stderr, status):
    ep = Endpoint(
        ["swiss-ai/Apertus-70B-Instruct-2509"], list_models=False, unknown_status=status
    )
    try:
        assert (
            llm_module.resolve_model(ep.client(), "apertus-v1.5-70b")
            == "swiss-ai/Apertus-70B-Instruct-2509"
        )
        err = stderr.getvalue()
        assert "no model list" in err and "first known Apertus name" in err
    finally:
        ep.close()


def test_nothing_works_is_loud_and_keeps_the_configured_name(stderr):
    ep = Endpoint([], list_models=False)
    try:
        assert (
            llm_module.resolve_model(ep.client(), "apertus-v1.5-8b")
            == "apertus-v1.5-8b"
        )
        assert "no Apertus model name works" in stderr.getvalue()
    finally:
        ep.close()


def test_other_errors_are_reported_not_hidden(stderr):
    assert (
        llm_module.resolve_model(
            OpenAI(base_url="http://127.0.0.1:9/v1", api_key="k", max_retries=0),
            "apertus-v1.5-8b",
        )
        == "apertus-v1.5-8b"
    )
    assert "test call to model 'apertus-v1.5-8b' failed" in stderr.getvalue()


def _cli(monkeypatch, tmp_path, ep, model):
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_NAME"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("BASE_URL", ep.url)
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("LLM_NAME", model)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("BOOKLINT_ENV_FILE", str(tmp_path / "none.env"))
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        json.dumps(
            {
                "id": "c1-B",
                "vote": "E-ID",
                "reference": {
                    "text": "Die E-ID ist freiwillig und kostenlos.",
                    "language": "de",
                },
                "claim": {"text": "Die E-ID ist kostenlos.", "language": "de"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "out" / "predictions.jsonl"
    main(["--input", str(cases), "--output", str(out), "--no-cache"])
    return json.loads(out.read_text(encoding="utf-8"))


def test_cli_end_to_end_switches_to_the_proxy_name(monkeypatch, tmp_path, stderr):
    ep = Endpoint(["swiss-ai/Apertus-v1.5-8B"])
    try:
        row = _cli(monkeypatch, tmp_path, ep, "apertus-v1.5-8b")
        assert (
            row["label"] == 0
            and "error" not in row
            and row["evidence"][0]["page"] is None
        )
        assert set(ep.asked[1:]) == {"swiss-ai/Apertus-v1.5-8B"}
        assert "using 'swiss-ai/Apertus-v1.5-8B'" in stderr.getvalue()
    finally:
        ep.close()


def test_cli_end_to_end_failure_is_neutral_but_loud(monkeypatch, tmp_path, stderr):
    ep = Endpoint([], list_models=False)
    try:
        row = _cli(monkeypatch, tmp_path, ep, "apertus-v1.5-8b")
        assert row["label"] == 1 and row["evidence"] == [] and "error" in row
        err = stderr.getvalue()
        assert "no Apertus model name works" in err and "1 of 1 cases failed" in err
    finally:
        ep.close()
