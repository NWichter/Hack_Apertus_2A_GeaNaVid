"""Macro-F1 intervals on the test split that account for the exact duplicate rows of OST v1.0 (no Apertus calls).

python experiments/v1/duplicates_ci.py

For each stored test run: macro-F1 and 95 % percentile bootstrap (2,000 resamples, seed 13) four ways:
  rows       every row independent (as in summary.json)
  dedup      first occurrence of each (claim, booklet_url, label) pair only (375 of 497 rows)
  cluster    all 497 rows, duplicate groups resampled as one unit
  proposal   all 497 rows, resampled by proposal (vote title x voting date), the coarser unit claims share
Also the paired cluster bootstrap of the difference between the two default pipelines (70B - 8B).
Output: runs/v1/test/duplicates-ci.json
"""

import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST = ROOT / "runs" / "v1" / "test"
B, SEED = 2000, 13
RUNS = {
    "apertus-v1.5-8b": [
        "r1-secboost",
        "default",
        "baseline",
        "easy-fs3",
        "easy",
        "ret-vote",
        "ret-vote-tr",
    ],
    "apertus-v1.5-70b": [
        "r1-secboost",
        "ret-vote-tr",
        "baseline",
        "easy",
        "ret-vote",
        "ret-vote-tr-dec",
    ],
}


def rj(p):
    return [
        json.loads(x)
        for x in Path(p).read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]


def macro_f1(pairs):
    f = []
    for c in (0, 1, 2):
        tp = sum(1 for g, p in pairs if g == c and p == c)
        fp = sum(1 for g, p in pairs if g != c and p == c)
        fn = sum(1 for g, p in pairs if g == c and p != c)
        f.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(f) / 3


def ci(units):
    rng = random.Random(SEED)
    vals = sorted(
        macro_f1([x for _ in units for x in rng.choice(units)]) for _ in range(B)
    )
    return [round(vals[int(0.025 * B)], 3), round(vals[int(0.975 * B) - 1], 3)]


def main():
    rows = rj(ROOT / "data" / "v1" / "test.jsonl")
    key = {
        r["id"]: (r["claim"].strip(), r["booklet_url"], r["entailment_label"])
        for r in rows
    }
    prop = {r["id"]: (r["vote"].strip(), r["booklet_publish_date"]) for r in rows}
    gold = {r["id"]: r["entailment_label"] for r in rows}
    first, groups = {}, defaultdict(list)
    for r in rows:
        first.setdefault(key[r["id"]], r["id"])
        groups[key[r["id"]]].append(r["id"])
    keep = set(first.values())
    by_prop = defaultdict(list)
    for r in rows:
        by_prop[prop[r["id"]]].append(r["id"])
    out = {
        "rows": len(rows),
        "distinct_pairs": len(keep),
        "duplicate_rows": len(rows) - len(keep),
        "groups_with_copies": sum(1 for g in groups.values() if len(g) > 1),
        "proposals": len(by_prop),
        "bootstrap": {"resamples": B, "seed": SEED},
        "runs": {},
    }
    for model, names in RUNS.items():
        for name in names:
            path = TEST / model / f"{name}.jsonl"
            if not path.exists():
                continue
            pred = {p["id"]: p["entailment_label"] for p in rj(path)}
            assert set(pred) == set(gold), path
            pair = {i: (gold[i], pred[i]) for i in gold}
            all_units = [[pair[i]] for i in gold]
            out["runs"][f"{model}/{name}"] = {
                "rows": {
                    "f1": round(macro_f1([pair[i] for i in gold]), 4),
                    "ci": ci(all_units),
                },
                "dedup": {
                    "f1": round(macro_f1([pair[i] for i in keep]), 4),
                    "ci": ci([[pair[i]] for i in keep]),
                },
                "cluster": {"ci": ci([[pair[i] for i in g] for g in groups.values()])},
                "proposal": {
                    "ci": ci([[pair[i] for i in g] for g in by_prop.values()])
                },
            }
    pa = {
        p["id"]: p["entailment_label"]
        for p in rj(TEST / "apertus-v1.5-8b" / "r1-secboost.jsonl")
    }
    pb = {
        p["id"]: p["entailment_label"]
        for p in rj(TEST / "apertus-v1.5-70b" / "r1-secboost.jsonl")
    }
    rng = random.Random(SEED)
    units = list(groups.values())
    diffs = []
    for _ in range(B):
        ids = [i for _ in units for i in rng.choice(units)]
        diffs.append(
            macro_f1([(gold[i], pb[i]) for i in ids])
            - macro_f1([(gold[i], pa[i]) for i in ids])
        )
    diffs.sort()
    out["default_70b_minus_8b_cluster"] = {
        "diff": round(
            macro_f1([(gold[i], pb[i]) for i in gold])
            - macro_f1([(gold[i], pa[i]) for i in gold]),
            4,
        ),
        "ci": [round(diffs[int(0.025 * B)], 3), round(diffs[int(0.975 * B) - 1], 3)],
    }
    dst = TEST / "duplicates-ci.json"
    dst.write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for k, v in out["runs"].items():
        print(
            f"{k:38s} all {v['rows']['f1']:.3f} {v['rows']['ci']}  dedup {v['dedup']['f1']:.3f} {v['dedup']['ci']}"
            f"  cluster {v['cluster']['ci']}  proposal {v['proposal']['ci']}"
        )
    print("70B - 8B defaults, cluster bootstrap:", out["default_70b_minus_8b_cluster"])
    print(
        {
            k: out[k]
            for k in (
                "rows",
                "distinct_pairs",
                "duplicate_rows",
                "groups_with_copies",
                "proposals",
            )
        }
    )


if __name__ == "__main__":
    main()
