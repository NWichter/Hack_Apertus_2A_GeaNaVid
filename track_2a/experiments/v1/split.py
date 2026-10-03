"""Split OST v1.0 by voting date (all three language versions of a booklet stay together).

Writes data/v1/dev.jsonl, data/v1/test.jsonl, data/v1/dev_s.jsonl (stratified ablation subset of dev)
and data/v1/split.json. Deterministic: seed 2026.
"""

import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "v1" / "v1.0.jsonl"
SEED = 2026
N_TEST_DATES = 7
FORCE_DEV = {"2026-06-14"}  # demo booklet, used for tuning before v1.0
DEV_S_SIZE = 450  # stratified by label x (same, cross), proportional


def cell(r):
    return (r["entailment_label"], r["claim_language"] == r["reference_language"])


def imbalance(test, total):
    score = abs(len(test) / len(total) - 1 / 3) * 3
    for key in (lambda r: r["entailment_label"], lambda r: r["claim_language"],
                lambda r: r["reference_language"], lambda r: r["claim_language"] == r["reference_language"]):
        a, b = Counter(map(key, test)), Counter(map(key, total))
        score += sum(abs(a[k] / len(test) - b[k] / len(total)) for k in b)
    return score


def main():
    rows = [json.loads(line) for line in SRC.open(encoding="utf-8")]
    for i, r in enumerate(rows):
        r["id"] = f"v1-{i:04d}"
    dates = sorted({r["booklet_publish_date"] for r in rows})
    free = [d for d in dates if d not in FORCE_DEV]
    rng = random.Random(SEED)
    best = None
    for _ in range(5000):
        pick = set(rng.sample(free, N_TEST_DATES))
        test = [r for r in rows if r["booklet_publish_date"] in pick]
        s = imbalance(test, rows)
        if best is None or s < best[0]:
            best = (s, sorted(pick))
    test_dates = set(best[1])
    dev = [r for r in rows if r["booklet_publish_date"] not in test_dates]
    test = [r for r in rows if r["booklet_publish_date"] in test_dates]
    rng = random.Random(SEED)
    cells = {}
    for r in dev:
        cells.setdefault(cell(r), []).append(r)
    dev_s = []
    for key in sorted(cells):
        dev_s += rng.sample(cells[key], round(DEV_S_SIZE * len(cells[key]) / len(dev)))
    dev_s.sort(key=lambda r: r["id"])
    out = ROOT / "data" / "v1"
    for name, part in (("dev", dev), ("test", test), ("dev_s", dev_s)):
        with (out / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
            for r in part:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def stats(part):
        return {
            "rows": len(part),
            "booklets": len({r["booklet_url"] for r in part}),
            "labels": dict(sorted(Counter(r["entailment_label"] for r in part).items())),
            "same_language": sum(r["claim_language"] == r["reference_language"] for r in part),
            "cross_language": sum(r["claim_language"] != r["reference_language"] for r in part),
            "booklet_language": dict(sorted(Counter(r["reference_language"] for r in part).items())),
            "claim_language": dict(sorted(Counter(r["claim_language"] for r in part).items())),
        }

    meta = {
        "source": "OSTswiss/MNLIoverSwissVotingBooklets v1.0.jsonl (HF commit adca9a5)",
        "seed": SEED,
        "unit": "booklet_publish_date (DE/FR/IT versions of a booklet stay in one split)",
        "forced_dev": sorted(FORCE_DEV),
        "test_dates": sorted(test_dates),
        "dev_dates": sorted({r["booklet_publish_date"] for r in dev}),
        "dev": stats(dev),
        "test": stats(test),
        "dev_s": stats(dev_s),
    }
    (out / "split.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
