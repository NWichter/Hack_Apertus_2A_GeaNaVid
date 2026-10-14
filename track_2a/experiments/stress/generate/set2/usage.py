"""Print OpenRouter key usage (no key values). Appends a line to data/usage.log."""

import json
import sys
import urllib.request
from datetime import datetime, timezone

from common import DATA, load_env


def get(url):
    key = load_env()["OPENROUTER_API_KEY"]
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())["data"]


def main():
    k = get("https://openrouter.ai/api/v1/key")
    rec = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tag": sys.argv[1] if len(sys.argv) > 1 else "",
        "usage": k.get("usage"),
        "limit": k.get("limit"),
        "limit_remaining": k.get("limit_remaining"),
        "is_free_tier": k.get("is_free_tier"),
    }
    try:
        c = get("https://openrouter.ai/api/v1/credits")
        rec["credits_total"] = c.get("total_credits")
        rec["credits_used"] = c.get("total_usage")
    except Exception as exc:  # noqa: BLE001
        rec["credits_error"] = repr(exc)[:120]
    DATA.mkdir(exist_ok=True)
    with (DATA / "usage.log").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
