#!/usr/bin/env python3
"""GeaNaVid demo server: static UI plus a JSON API in front of the booklint pipeline.

The LLM key stays on the server. Credentials come only from the environment:
BASIC_AUTH_USER / BASIC_AUTH_PASSWORD (required unless --no-auth), LLM_BASE_URL / LLM_API_KEY / LLM_NAME.
"""

import argparse
import base64
import hmac
import json
import logging
import os
import sys
import threading
import time
from collections import defaultdict
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

TRACK2A_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = TRACK2A_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from booklint.config import Settings, load_dotenv  # noqa: E402
from booklint.llm import LLM, redact  # noqa: E402
from booklint.pipeline import Options, Pipeline, format_slide25  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("geanavid-demo")

load_dotenv(TRACK2A_ROOT / ".env")

BASIC_AUTH_USER = os.environ.get("BASIC_AUTH_USER", "")
BASIC_AUTH_PASSWORD = os.environ.get("BASIC_AUTH_PASSWORD", "")
AUTH_ENABLED = True

RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))
GLOBAL_LIMIT_MAX_REQUESTS = int(os.environ.get("GLOBAL_LIMIT_MAX", "300"))
GLOBAL_LIMIT_WINDOW_SECONDS = int(os.environ.get("GLOBAL_LIMIT_WINDOW", "3600"))
TRUST_PROXY = os.environ.get("TRUST_PROXY", "") == "1"
USE_LLM_CACHE = os.environ.get("DEMO_LLM_CACHE", "") == "1"

MAX_BODY_BYTES = 16_384
MAX_CLAIM_CHARS = 1_000
MAX_REFERENCE_CHARS = 8_000

PRESETS_FILE = TRACK2A_ROOT / "data" / "edge_cases.jsonl"
DATASET_FILE = TRACK2A_ROOT / "data" / "v1" / "v1.0.jsonl"

_rate_limits = defaultdict(list)
_rate_lock = threading.Lock()
_global_hits = []
_pipeline_lock = threading.Lock()


def check_rate_limit(client_ip):
    now = time.time()
    with _rate_lock:
        recent = [
            t for t in _rate_limits[client_ip] if t > now - RATE_LIMIT_WINDOW_SECONDS
        ]
        allowed = len(recent) < RATE_LIMIT_MAX_REQUESTS
        if allowed:
            recent.append(now)
        _rate_limits[client_ip] = recent
        return allowed


def check_global_limit():
    """Overall cap across all clients, so the LLM key cannot be burned through many IPs."""
    now = time.time()
    with _rate_lock:
        recent = [t for t in _global_hits if t > now - GLOBAL_LIMIT_WINDOW_SECONDS]
        allowed = len(recent) < GLOBAL_LIMIT_MAX_REQUESTS
        if allowed:
            recent.append(now)
        _global_hits[:] = recent
        return allowed


OST_EXAMPLE_IDS = ("v1-0161", "v1-1484", "v1-0696", "v1-1179", "v1-0632", "v1-0316")


def dataset_rows():
    if not DATASET_FILE.is_file():
        return []
    return [
        dict(json.loads(line), id=f"v1-{i:04d}")
        for i, line in enumerate(DATASET_FILE.read_text(encoding="utf-8").splitlines())
        if line.strip()
    ]


def url_lang(url):
    for lang in ("de", "fr", "it"):
        if f"/dam/{lang}/" in url:
            return lang
    return ""


def booklet_index(rows):
    """Official booklet URLs of the OST v1.0 dataset, keyed by (date, language), and the vote titles per booklet.
    Nothing else may be fetched."""
    urls, votes = {}, defaultdict(set)
    for row in rows:
        url, date = row.get("booklet_url"), row.get("booklet_publish_date")
        if url and date:
            urls[(date, url_lang(url))] = url
            if row.get("vote"):
                votes[(date, url_lang(url))].add(row["vote"].strip())
    return urls, votes


def ost_examples(rows):
    by_id = {r["id"]: r for r in rows}
    out = []
    for i in OST_EXAMPLE_IDS:
        r = by_id.get(i)
        if not r:
            continue
        out.append(
            {
                "id": i,
                "claim": r["claim"],
                "claim_language": r["claim_language"],
                "booklet": r["booklet_publish_date"],
                "booklet_lang": url_lang(r["booklet_url"]),
                "vote": r["vote"],
                "label": r["entailment_label"],
                "source": "OST v1.0, development split",
            }
        )
    return out


_ROWS = dataset_rows()
BOOKLETS, VOTES = booklet_index(_ROWS)
OST_EXAMPLES = ost_examples(_ROWS)
del _ROWS


_pipelines = {}
_models = None


def available_models():
    """Apertus models the demo offers: DEMO_MODELS (comma-separated), else the Apertus models in the endpoint's
    /models list, else only the configured LLM_NAME. The first one is the default."""
    global _models
    with _pipeline_lock:
        if _models is not None:
            return _models
        try:
            settings = Settings.from_env()
        except SystemExit as exc:
            logger.error("LLM backend not configured: %s", exc)
            return []
        wanted = [m.strip() for m in os.environ.get("DEMO_MODELS", "").split(",") if m.strip()]
        if not wanted:
            try:
                client = LLM(settings, use_cache=USE_LLM_CACHE).client
                listed = [m.id for m in client.with_options(timeout=10, max_retries=0).models.list().data]
                wanted = sorted((m for m in listed if "apertus" in m.lower()), key=lambda m: (m != settings.model, m))
            except Exception as exc:  # noqa: BLE001
                logger.warning("No model list from the endpoint: %s", redact(exc)[:200])
        _models = wanted or [settings.model]
        logger.info("Demo models: %s", ", ".join(_models))
        return _models


def get_pipeline(model=None):
    models = available_models()
    if not models:
        return None
    model = model or models[0]
    if model not in models:
        return None
    with _pipeline_lock:
        if model not in _pipelines:
            settings = Settings.from_env(model)
            _pipelines[model] = Pipeline(LLM(settings, use_cache=USE_LLM_CACHE), Options())
            logger.info("Pipeline ready, model %s", _pipelines[model].llm.model)
        return _pipelines[model]


def load_presets():
    if not PRESETS_FILE.is_file():
        return []
    keep = (
        "id",
        "claim",
        "claim_language",
        "reference_string",
        "reference_language",
        "vote",
        "challenge_type",
        "label",
    )
    rows = [
        json.loads(line)
        for line in PRESETS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [{k: r[k] for k in keep if k in r} for r in rows]


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, directory=str(Path(__file__).resolve().parent), **kwargs
        )

    def log_message(self, format, *args):
        logger.info("%s %s", self.client_address[0], format % args)

    def _send_json(self, status, data, headers=None):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        if not AUTH_ENABLED:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            user, _, password = (
                base64.b64decode(header[6:].strip()).decode("utf-8").partition(":")
            )
        except Exception:
            return False
        return hmac.compare_digest(
            user.encode(), BASIC_AUTH_USER.encode()
        ) and hmac.compare_digest(password.encode(), BASIC_AUTH_PASSWORD.encode())

    def _require_auth(self):
        if self._authorized():
            return True
        self._send_json(
            401,
            {"error": "Authentication required."},
            {"WWW-Authenticate": 'Basic realm="GeaNaVid demo"'},
        )
        return False

    def _client_ip(self):
        if TRUST_PROXY:
            forwarded = [
                p.strip()
                for p in self.headers.get("X-Forwarded-For", "").split(",")
                if p.strip()
            ]
            if forwarded:
                return forwarded[-1]
        return self.client_address[0]

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return
        if not self._require_auth():
            return
        if path == "/api/presets":
            presets = load_presets()
            self._send_json(
                200,
                {
                    "ost": OST_EXAMPLES,
                    "presets": presets,
                    "count": len(presets),
                    "synthetic": True,
                },
            )
            return
        if path == "/api/info":
            models = available_models()
            self._send_json(
                200,
                {
                    "model": models[0] if models else None,
                    "models": models,
                    "labels": {"0": "entailment", "1": "neutral", "2": "contradiction"},
                    "booklets": sorted({d for d, _ in BOOKLETS}),
                    "booklet_sources": {
                        f"{d}_{lang}": {"url": url, "votes": sorted(VOTES.get((d, lang), ()))}
                        for (d, lang), url in sorted(BOOKLETS.items())
                    },
                    "rate_limit": f"{RATE_LIMIT_MAX_REQUESTS} requests / {RATE_LIMIT_WINDOW_SECONDS} s",
                    "global_limit": f"{GLOBAL_LIMIT_MAX_REQUESTS} requests / {GLOBAL_LIMIT_WINDOW_SECONDS} s",
                },
            )
            return
        if path.startswith("/api/") or path.endswith((".py", ".md")):
            self._send_json(404, {"error": "Not found."})
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._require_auth():
            return
        if path != "/api/predict":
            self._send_json(404, {"error": "Not found."})
            return
        if not check_rate_limit(self._client_ip()):
            self._send_json(
                429,
                {
                    "error": f"Rate limit: at most {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW_SECONDS} s."
                },
                {"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
            )
            return
        if not check_global_limit():
            self._send_json(
                429,
                {
                    "error": "The public demo has reached its hourly limit of "
                    f"{GLOBAL_LIMIT_MAX_REQUESTS} requests. Please try again later."
                },
                {"Retry-After": str(GLOBAL_LIMIT_WINDOW_SECONDS)},
            )
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(
                400 if length <= 0 else 413,
                {"error": f"Body must be 1 to {MAX_BODY_BYTES} bytes of JSON."},
            )
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError
        except Exception:
            self._send_json(400, {"error": "Body is not a JSON object."})
            return

        claim = str(payload.get("claim") or "").strip()
        reference = str(payload.get("reference") or "").strip()
        mode = str(payload.get("mode") or "beginner").lower()
        claim_lang = str(payload.get("claim_lang") or "").strip() or None
        case_id = str(payload.get("id") or f"web-{int(time.time() * 1000) % 100000}")[
            :64
        ]
        if not claim or len(claim) > MAX_CLAIM_CHARS:
            self._send_json(
                400,
                {
                    "error": f"'claim' is required (at most {MAX_CLAIM_CHARS} characters)."
                },
            )
            return

        kwargs = {"claim": claim, "claim_lang": claim_lang, "case_id": case_id}
        if mode == "beginner":
            if not reference or len(reference) > MAX_REFERENCE_CHARS:
                self._send_json(
                    400,
                    {
                        "error": f"'reference' is required (at most {MAX_REFERENCE_CHARS} characters)."
                    },
                )
                return
            kwargs["gold_reference"] = reference
        elif mode == "advanced":
            date = str(payload.get("booklet") or "").strip()
            lang = str(payload.get("booklet_lang") or "de").strip()
            url = BOOKLETS.get((date, lang))
            if not url:
                self._send_json(
                    400,
                    {
                        "error": "Unknown booklet. Choose one of the listed dates (de, fr or it)."
                    },
                )
                return
            kwargs["booklet_source"] = url
            kwargs["vote"] = str(payload.get("vote") or "").strip()[:300] or None
        else:
            self._send_json(400, {"error": "'mode' must be 'beginner' or 'advanced'."})
            return

        model = str(payload.get("model") or "").strip() or None
        if model and model not in available_models():
            self._send_json(400, {"error": f"Unknown model. Choose one of: {', '.join(available_models())}."})
            return
        pipe = get_pipeline(model)
        if pipe is None:
            self._send_json(
                503, {"error": "The LLM backend is not configured on this server."}
            )
            return
        try:
            result = format_slide25(pipe.check(**kwargs), case_id=case_id)
        except Exception as exc:
            logger.error("Inference failed for %s: %s", case_id, redact(exc)[:300])
            self._send_json(502, {"error": "Inference failed. Please try again later."})
            return
        # the model goes in a header, so the body stays exactly OST's output format
        self._send_json(200, result, {"X-Model": pipe.llm.model})


def main(argv=None):
    global AUTH_ENABLED
    parser = argparse.ArgumentParser(description="GeaNaVid demo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--no-auth", action="store_true", help="run without Basic Auth (local use, or public behind nginx; the rate limit stays active)"
    )
    args = parser.parse_args(argv)

    if args.no_auth:
        AUTH_ENABLED = False
        logger.warning("Basic Auth disabled")
    elif not (BASIC_AUTH_USER and BASIC_AUTH_PASSWORD):
        sys.exit(
            "Set BASIC_AUTH_USER and BASIC_AUTH_PASSWORD, or start with --no-auth for local use."
        )

    httpd = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    logger.info(
        "GeaNaVid demo on http://%s:%s (rate limit %s/%ss)",
        args.host,
        args.port,
        RATE_LIMIT_MAX_REQUESTS,
        RATE_LIMIT_WINDOW_SECONDS,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    main()
