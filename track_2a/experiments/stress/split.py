"""Fixed split of the stress set (data/stress-synth/clean.jsonl) by voting date, decided before any development on it.

Stratified so that both halves hold each failure type of the first run (ERGEBNIS 4.2): one of the two dates where
the proposal is picked wrongly (1999, 2005), one of the two dates whose booklets are structured (2002, 2016), and
three of the six dates without a recognised structure. Seeded draw, no look at per-date scores.
python experiments/stress/split.py  ->  data/stress-synth/split.json
"""

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRATA = [
    ["1999-06-13", "2005-06-05"],
    ["2002-03-03", "2016-06-05"],
    ["2008-11-30", "2010-11-28", "2013-03-03", "2014-02-09", "2017-05-21", "2018-03-04"],
]
SEED = 20261014


def main():
    rng = random.Random(SEED)
    dev, holdout = [], []
    for s in STRATA:
        s = list(s)
        rng.shuffle(s)
        k = len(s) // 2
        dev += s[:k]
        holdout += s[k:]
    rows = [json.loads(x) for x in (ROOT / "data/stress-synth/clean.jsonl").open(encoding="utf-8")]
    n = {name: sum(r["booklet_date"] in ds for r in rows) for name, ds in (("dev", dev), ("holdout", holdout))}
    out = {"seed": SEED, "strata": STRATA, "dev": sorted(dev), "holdout": sorted(holdout), "rows": n}
    (ROOT / "data/stress-synth/split.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
