import hashlib
import os
import json
import random
import re
import sys
import time
from dataclasses import dataclass, field

from openai import APIConnectionError, APITimeoutError, BadRequestError, InternalServerError, OpenAI, RateLimitError


_SECRET = re.compile(r"(sk-|key[ _-]?hash|hash)[\w:=\"' -]*[A-Za-z0-9_-]{12,}|[A-Za-z0-9_-]{32,}", re.I)


RETRIES = {"rate_limit": 0, "other": 0, "bad_request_fallback": 0, "uncached": 0}


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
        if self.use_cache and path.is_file():
            rec = json.loads(path.read_text(encoding="utf-8"))
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
        for attempt in range(10):
            t0 = time.perf_counter()
            try:
                resp = self.client.chat.completions.create(model=model, messages=messages, **params)
                break
            except BadRequestError as exc:
                had_fallback = False
                if "response_format" in params:
                    params.pop("response_format", None)
                    had_fallback = True
                if "logprobs" in params:
                    params.pop("logprobs", None)
                    params.pop("top_logprobs", None)
                    had_fallback = True
                if had_fallback:
                    RETRIES["bad_request_fallback"] += 1
                    if RETRIES["bad_request_fallback"] == 1:
                        print("warning: endpoint rejected response_format/logprobs; retrying without them "
                              "(no confidences, so decomposition and calibration are skipped)", file=sys.stderr)
                    try:
                        resp = self.client.chat.completions.create(model=model, messages=messages, **params)
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
                if attempt == 9:
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
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
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
