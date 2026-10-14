"""Score predictions in OST's output format against expected labels written by ost_cases.py.

Macro-F1 per task (A = booklet, B = reference) and, for task A, the evidence rule of OST's evaluate.py
(one of the first five quotes inside the gold passage, rapidfuzz partial_ratio >= 90; see ost_evidence.py).
This mirrors OST's script for a quick local check; the official score comes from OST's own evaluation.
python experiments/v1/ost_score.py --predictions runs/ost-sample/output/predictions.jsonl --expected runs/ost-sample/data/expected-labels.jsonl
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz

MAX_QUOTES, MAX_CHARS, MIN_RATIO = (
    5,
    5000,
    90,
)  # as in ost_evidence.py (OST's evaluate.py)


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


def macro_f1(gold, pred):
    f = []
    for c in (0, 1, 2):
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    return sum(f) / 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--expected", required=True)
    a = ap.parse_args()
    gold = {
        r["id"]: r
        for r in map(
            json.loads, Path(a.expected).read_text(encoding="utf-8").splitlines()
        )
    }
    pred = {
        r["id"]: r
        for r in map(
            json.loads, Path(a.predictions).read_text(encoding="utf-8").splitlines()
        )
    }
    missing = [i for i in gold if i not in pred]
    for task in ("A", "B"):
        ids = [i for i in gold if i.endswith("-" + task) and i in pred]
        if not ids:
            continue
        f1 = macro_f1([gold[i]["label"] for i in ids], [pred[i]["label"] for i in ids])
        line = f"task {task}: {len(ids)} cases, macro-F1 {f1:.3f}"
        if task == "A":
            ec = [i for i in ids if gold[i]["label"] != 1]
            found = sum(
                any(
                    matches(e.get("text") or "", gold[i]["reference"])
                    for e in (pred[i].get("evidence") or [])[:MAX_QUOTES]
                )
                for i in ec
            )
            line += f", evidence found {found} of {len(ec)}"
        tok = [pred[i].get("metrics", {}).get("input_tokens") or 0 for i in ids]
        ms = sorted(
            pred[i].get("metrics", {}).get("inference_time_ms") or 0 for i in ids
        )
        line += (
            f", input tokens {sum(tok) / len(tok):.0f}, ms mean {sum(ms) / len(ms):.0f}"
        )
        print(line)
    print(f"missing predictions: {len(missing)}")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
