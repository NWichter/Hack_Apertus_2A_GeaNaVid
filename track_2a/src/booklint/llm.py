import hashlib
import os
import json
import random
import re
import sys
import threading
import time
from dataclasses import dataclass, field

from openai import APIConnectionError, APITimeoutError, BadRequestError, InternalServerError, OpenAI, RateLimitError


_SECRET = re.compile(r"(sk-|key[ _-]?hash|hash)[\w:=\"' -]*[A-Za-z0-9_-]{12,}|[A-Za-z0-9_-]{32,}", re.I)


RETRIES = {"rate_limit": 0, "other": 0, "bad_request_fallback": 0, "uncached": 0}
# Parameters the endpoint rejected once (and accepted without): left out of every later call, so a proxy without
# json_schema/logprobs costs one failed request per run, not one per call.
UNSUPPORTED = set()


def redact(text):
    return _SECRET.sub("<redacted>", str(text))


@dataclass
class Call:
    purpose: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    cached: bool


@dataclass
class Usage:
    calls: list = field(default_factory=list)

    def add(self, call):
        self.calls.append(call)

    def summary(self):
        return {
            "llm_calls": len(self.calls),
            "prompt_tokens": sum(c.prompt_tokens for c in self.calls),
            "completion_tokens": sum(c.completion_tokens for c in self.calls),
            "llm_seconds": round(sum(c.seconds for c in self.calls), 3),
            "cached_calls": sum(c.cached for c in self.calls),
            "steps": [c.purpose for c in self.calls],
        }


_RESOLVED = {}

# Spellings of the Apertus v1.5 models seen in the Hack Apertus guide, OST's Solution API Guide
# ("swiss-ai/Apertus-v1.5-..."), Hugging Face and the hackathon endpoint; {size} is 8 or 70. Only v1.5 names:
# the challenge allows Apertus v1.5 only.
CANDIDATES = (
    "swiss-ai/Apertus-v1.5-{size}B",
    "swiss-ai/Apertus-v1.5-{size}B-Instruct",
    "apertus-v1.5-{size}b",
    "swiss-ai/apertus-v1.5-{size}b",
    "Apertus-v1.5-{size}B",
    "Apertus-v1.5-{size}B-Instruct",
    "apertus-v1.5-{size}b-instruct",
)


def warn(message):
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


def model_size(name):
    m = re.search(r"(?<![\d.])(\d+)\s*b\b", (name or "").lower())
    return m.group(1) if m else None


def _status(exc):
    return getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)


def _model_missing(exc):
    """Errors that mean "this model name is not served here" (404/400/422, or 401/403 naming the model)."""
    status, text = _status(exc), str(exc).lower()
    if status in (400, 404, 422):
        return True
    return status in (401, 403) and "model" in text


def probe(client, model):
    """One tiny chat call: None if the model answers, else the exception."""
    try:
        client.chat.completions.create(model=model, messages=[{"role": "user", "content": "Ja?"}], max_tokens=1,
                                       temperature=0)
        return None
    except RateLimitError:
        return None
    except Exception as exc:  # noqa: BLE001
        return exc


def pick_from_list(ids, wanted):
    """The Apertus model of the wanted size from an endpoint's model list, else the first Apertus model."""
    apertus = [i for i in ids if "apertus" in i.lower()]
    size = model_size(wanted)
    same = [i for i in apertus if size and model_size(i) == size]
    pool = sorted(same, key=lambda i: ("1.5" not in i, "instruct" not in i.lower(), len(i))) or apertus
    return pool[0] if pool else None


def candidates(wanted):
    size = model_size(wanted) or "8"
    other = "70" if size == "8" else "8"
    out = [c.format(size=size) for c in CANDIDATES] + [c.format(size=other) for c in CANDIDATES]
    return [c for c in dict.fromkeys(out) if c != wanted]


def resolve_model(client, wanted):
    """The model id to send. A test call checks `wanted` first; if the endpoint says the model does not exist,
    its /models list is read and the Apertus model of the same size is taken; without a list, known spellings
    are tried one by one. Every change and every failure is reported on stderr; nothing fails silently."""
    key = (str(client.base_url), wanted)
    if key in _RESOLVED:
        return _RESOLVED[key]
    quick = client.with_options(timeout=30, max_retries=0)
    exc = probe(quick, wanted)
    choice = wanted
    if exc is not None and not _model_missing(exc):
        warn(f"test call to model {wanted!r} failed ({redact(type(exc).__name__)}: {redact(exc)[:200]}); "
             "continuing with this model, cases that fail are answered neutral with an 'error' field")
    elif exc is not None:
        warn(f"model {wanted!r} is not served by the endpoint ({_status(exc)}: {redact(exc)[:160]})")
        ids = None
        try:
            ids = [m.id for m in quick.models.list().data]
        except Exception as list_exc:  # noqa: BLE001
            warn(f"no model list at {redact(client.base_url)}models ({type(list_exc).__name__}); trying known names")
        found = pick_from_list(ids, wanted) if ids else None
        if ids and not found:
            warn(f"the endpoint lists no Apertus model: {ids[:10]}")
        if found:
            choice = found
            warn(f"using {choice!r} from the endpoint's model list")
        else:
            for name in candidates(wanted):
                if probe(quick, name) is None:
                    choice = name
                    warn(f"using {choice!r}, the first known Apertus name the endpoint accepts")
                    break
            else:
                warn("no Apertus model name works at this endpoint; every case will fail and be answered "
                     "neutral with an 'error' field. Set LLM_NAME to the endpoint's model name.")
        if model_size(choice) and model_size(choice) != model_size(wanted):
            warn(f"{choice!r} is not the configured size ({wanted!r})")
    _RESOLVED[key] = choice
    return choice

class LLM:
    def __init__(self, settings, use_cache=True):
        self.settings = settings
        self.model = settings.model
        self.client = OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=settings.timeout,
            max_retries=1,
        )
        if os.environ.get("BOOKLINT_RESOLVE_MODEL", "1") != "0":
            self.model = settings.model = resolve_model(self.client, settings.model)
        self.cache = settings.cache_dir / "llm"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.use_cache = use_cache

    def chat(self, messages, usage, purpose, model=None, **params):
        model = model or self.model
        key = hashlib.sha256(
            json.dumps(
                [model, messages, params], sort_keys=True, ensure_ascii=False
            ).encode()
        ).hexdigest()
        path = self.cache / f"{key[:2]}" / f"{key}.json"
        rec = None
        if self.use_cache and path.is_file():
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                rec = None  # a broken cache file is a miss
        if rec is not None:
            usage.add(
                Call(
                    purpose,
                    model,
                    rec["prompt_tokens"],
                    rec["completion_tokens"],
                    rec["seconds"],
                    True,
                )
            )
            return rec
        limit = int(os.environ.get("BOOKLINT_MAX_CALLS", "0") or 0)
        if limit and RETRIES["uncached"] >= limit:
            raise RuntimeError(f"call budget of {limit} uncached Apertus calls reached")
        RETRIES["uncached"] += 1
        params = dict(params)
        if UNSUPPORTED:
            for k in list(params):
                if k in UNSUPPORTED:
                    params.pop(k)
        for attempt in range(10):
            t0 = time.perf_counter()
            try:
                resp = self.client.chat.completions.create(model=model, messages=messages, **params)
                break
            except BadRequestError as exc:
                dropped = [k for k in ("response_format", "logprobs", "top_logprobs") if k in params]
                for k in dropped:
                    params.pop(k)
                if dropped:
                    RETRIES["bad_request_fallback"] += 1
                    if RETRIES["bad_request_fallback"] == 1:
                        print("warning: endpoint rejected response_format/logprobs; retrying without them "
                              "(no confidences, so decomposition and calibration are skipped)", file=sys.stderr)
                    try:
                        resp = self.client.chat.completions.create(model=model, messages=messages, **params)
                        UNSUPPORTED.update(dropped)
                        break
                    except Exception as inner_exc:
                        raise RuntimeError(redact(inner_exc)) from None
                raise RuntimeError(redact(exc)) from None
            except RateLimitError as exc:
                RETRIES["rate_limit"] += 1
                if attempt == 9:
                    raise RuntimeError(redact(exc)) from None
                time.sleep(1 + 2 * random.random())
            except (APIConnectionError, APITimeoutError, InternalServerError) as exc:
                RETRIES["other"] += 1
                if attempt >= 3:  # a hanging endpoint must not stall a case for many minutes
                    raise RuntimeError(redact(exc)) from None
                time.sleep(min(30, 2 ** attempt) * (0.5 + random.random()))
        seconds = time.perf_counter() - t0
        choice = resp.choices[0]
        logprobs = None
        if choice.logprobs and choice.logprobs.content:
            logprobs = [
                {
                    "token": t.token,
                    "top": [[x.token, x.logprob] for x in (t.top_logprobs or [])],
                }
                for t in choice.logprobs.content
            ]
        rec = {
            "content": choice.message.content or "",
            "finish_reason": choice.finish_reason,
            "logprobs": logprobs,
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            "seconds": round(seconds, 3),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)  # atomic: workers asking the same prompt never interleave their writes
        except OSError:
            pass
        usage.add(
            Call(
                purpose,
                model,
                rec["prompt_tokens"],
                rec["completion_tokens"],
                rec["seconds"],
                False,
            )
        )
        return rec
