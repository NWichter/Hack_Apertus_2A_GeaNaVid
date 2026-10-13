"""How well do the defaults carry over? Stored predictions only, no calls.

dev_s (450, options chosen here), dev_rest (548 other dev rows, never used to choose an option), test (497, seen
for 22 configurations). Per split: macro-F1, without rows that copy a claim of another split, and the spread over
voting dates. Output: runs/v1/generalization.json
python experiments/v1/generalization.py [--name final-v2]
"""

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from booklint.metrics import macro_f1  # noqa: E402
from run import load  # noqa: E402

MODELS = ("apertus-v1.5-8b", "apertus-v1.5-70b")
SPLITS = ("dev_s", "dev_rest", "test")


def f1(pairs):
    return (
        round(macro_f1([g for g, _ in pairs], [p for _, p in pairs])[0], 4)
        if pairs
        else None
    )


def cluster_ci(groups, n=2000, seed=2026):
    """Resample voting dates (all rows of a date together)."""
    rng = random.Random(seed)
    keys = list(groups)
    vals = []
    for _ in range(n):
        pairs = [x for k in (rng.choice(keys) for _ in keys) for x in groups[k]]
        vals.append(f1(pairs))
    vals.sort()
    return [vals[int(0.025 * n)], vals[int(0.975 * n) - 1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="final-v2")
    args = ap.parse_args()
    rows = {s: load(s) for s in SPLITS}
    key = lambda r: (r["claim"].strip(), r["booklet_url"])  # noqa: E731
    seen_in = {s: {key(r) for r in rows[s]} for s in SPLITS}
    out = {"name": args.name, "models": {}}
    for model in MODELS:
        res = {}
        all_by_date = {}
        for s in SPLITS:
            path = ROOT / "runs" / "v1" / s / model / f"{args.name}.jsonl"
            preds = {p["id"]: p for p in map(json.loads, path.open(encoding="utf-8"))}
            pairs, unique, by_date = [], [], {}
            others = set().union(*(seen_in[o] for o in SPLITS if o != s))
            for r in rows[s]:
                g, p = (
                    int(r["entailment_label"]),
                    int(preds[r["id"]]["entailment_label"]),
                )
                pairs.append((g, p))
                if key(r) not in others:
                    unique.append((g, p))
                by_date.setdefault(r["booklet_publish_date"], []).append((g, p))
                all_by_date.setdefault(r["booklet_publish_date"], []).append((g, p))
            per_date = {d: f1(v) for d, v in sorted(by_date.items())}
            res[s] = {
                "n": len(pairs),
                "macro_f1": f1(pairs),
                "ci95_by_date": cluster_ci(by_date),
                "n_without_cross_split_copies": len(unique),
                "macro_f1_without_cross_split_copies": f1(unique),
                "dates": len(by_date),
                "per_date": per_date,
                "per_date_min": min(per_date.values()),
                "per_date_median": round(statistics.median(per_date.values()), 4),
            }
        flat = [x for v in all_by_date.values() for x in v]
        per_date = {d: f1(v) for d, v in sorted(all_by_date.items())}
        res["all_1495"] = {
            "n": len(flat),
            "macro_f1": f1(flat),
            "ci95_by_date": cluster_ci(all_by_date),
            "per_date_min": min(per_date.values()),
            "per_date_max": max(per_date.values()),
            "per_date_sd": round(statistics.pstdev(per_date.values()), 4),
        }
        out["models"][model] = res
    target = ROOT / "runs" / "v1" / "generalization.json"
    target.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for model, res in out["models"].items():
        for s, v in res.items():
            print(model, s, {k: v[k] for k in v if k not in ("per_date",)})


if __name__ == "__main__":
    main()
