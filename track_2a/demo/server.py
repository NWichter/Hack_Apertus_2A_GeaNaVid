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
TRUST_PROXY = os.environ.get("TRUST_PROXY", "") == "1"
USE_LLM_CACHE = os.environ.get("DEMO_LLM_CACHE", "") == "1"

MAX_BODY_BYTES = 16_384
MAX_CLAIM_CHARS = 1_000
MAX_REFERENCE_CHARS = 8_000

PRESETS_FILE = TRACK2A_ROOT / "data" / "edge_cases.jsonl"
DATASET_FILE = TRACK2A_ROOT / "data" / "v1" / "v1.0.jsonl"

_rate_limits = defaultdict(list)
_rate_lock = threading.Lock()
_pipeline_lock = threading.Lock()
_pipeline_instance = None


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


def booklet_urls():
    """Official booklet URLs of the OST v1.0 dataset, keyed by (date, language). Nothing else may be fetched."""
    urls = {}
    if DATASET_FILE.is_file():
        for line in DATASET_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            url, date = row.get("booklet_url"), row.get("booklet_publish_date")
            if url and date:
                lang = (
                    "de"
                    if "/dam/de/" in url
                    else "fr"
                    if "/dam/fr/" in url
                    else "it"
                    if "/dam/it/" in url
                    else ""
                )
                urls[(date, lang)] = url
    return urls


BOOKLETS = booklet_urls()


def get_pipeline():
    global _pipeline_instance
    with _pipeline_lock:
        if _pipeline_instance is None:
            try:
                settings = Settings.from_env()
            except SystemExit as exc:
                logger.error("LLM backend not configured: %s", exc)
                return None
            _pipeline_instance = Pipeline(
                LLM(settings, use_cache=USE_LLM_CACHE), Options()
            )
            logger.info("Pipeline ready, model %s", settings.model)
        return _pipeline_instance


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
                200, {"presets": presets, "count": len(presets), "synthetic": True}
            )
            return
        if path == "/api/info":
            pipe = get_pipeline()
            self._send_json(
                200,
                {
                    "model": pipe.llm.model if pipe else None,
                    "labels": {"0": "entailment", "1": "neutral", "2": "contradiction"},
                    "booklets": sorted({d for d, _ in BOOKLETS}),
                    "rate_limit": f"{RATE_LIMIT_MAX_REQUESTS} requests / {RATE_LIMIT_WINDOW_SECONDS} s",
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

        pipe = get_pipeline()
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
        self._send_json(200, result)


def main(argv=None):
    global AUTH_ENABLED
    parser = argparse.ArgumentParser(description="GeaNaVid demo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--no-auth", action="store_true", help="run without Basic Auth (local use only)"
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
