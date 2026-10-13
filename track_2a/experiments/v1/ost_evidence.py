"""OST's task-A evidence score for stored runs, with the rule of evaluate.py in OST's starter repo
(gitlab.com/ifsoftware/hackapertus-starter, commit 5e69577, 2026-10-08): for every gold entailment/contradiction
case, found if one of the first five evidence texts (each at most 5,000 characters) matches the gold
reference_string with rapidfuzz partial_ratio >= 90 after NFKC, lower case, joined line-break hyphens and
collapsed whitespace. Pages are not checked by OST yet; the share with a gold page is reported separately.

uv run --with rapidfuzz python experiments/v1/ost_evidence.py --split test_v11 --runs final-v2 [...]
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import load  # noqa: E402

MAX_QUOTES, MAX_CHARS, MIN_RATIO = 5, 5000, 90


def normalize(text):
    text = unicodedata.normalize("NFKC", text).replace("­", "")
    text = re.sub(r"(\w) ?-\s*\n\s*(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def matches(quote, passage):
    quote, passage = normalize(quote), normalize(passage)
    return (
        bool(quote)
        and len(quote) <= MAX_CHARS
        and fuzz.partial_ratio(quote, passage) >= MIN_RATIO
    )


def score(rows, preds):
    found = first = n = items = chars = 0
    for r in rows:
        if int(r["entailment_label"]) == 1:
            continue
        n += 1
        ev = [
            e
            for e in preds[r["id"]].get("evidence") or []
            if isinstance(e, dict) and isinstance(e.get("text"), str)
        ]
        ev = ev[:MAX_QUOTES]
        hits = [matches(e["text"], r["reference_string"]) for e in ev]
        found += any(hits)
        first += bool(hits and hits[0])
        items += len(ev)
        chars += sum(len(e["text"]) for e in ev)
    return {
        "gold_ec_cases": n,
        "ost_evidence_score": round(found / n, 4),
        "first_item_matches": round(first / n, 4),
        "items_per_case": round(items / n, 2),
        "chars_per_case": round(chars / n),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test_v11")
    ap.add_argument("--runs", nargs="+", default=["final-v2"])
    ap.add_argument("--models", default="apertus-v1.5-8b,apertus-v1.5-70b")
    ap.add_argument("--out", default=None, help="write the results as JSON here")
    args = ap.parse_args()
    rows = load(args.split)
    out = {}
    for model in args.models.split(","):
        for name in args.runs:
            path = ROOT / "runs" / "v1" / args.split / model / f"{name}.jsonl"
            if not path.is_file():
                print("missing", path, file=sys.stderr)
                continue
            preds = {p["id"]: p for p in map(json.loads, path.open(encoding="utf-8"))}
            out[f"{args.split}/{model}/{name}"] = res = score(rows, preds)
            print(f"{args.split} {model} {name}: {res}")
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
