"""Offline: how much of the gold section lies inside the located proposal, by vote title vs by claim."""

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint.ingest import ingest  # noqa: E402
from booklint.proposal import locate  # noqa: E402
from booklint.retrieval_eval import gold_chunks  # noqa: E402

split = sys.argv[1] if len(sys.argv) > 1 else "dev"
rows = [json.loads(line) for line in (ROOT / "data" / "v1" / f"{split}.jsonl").open(encoding="utf-8")]
res = {"vote": [], "claim": [], "claim_top2": []}
size = {k: [] for k in res}
whole = []
for r in rows:
    b = ingest(r["booklet_url"])
    gold = set(gold_chunks(b, r["reference_string"]))
    if not gold:
        continue
    whole.append(sum(len(c.text) for c in b.chunks))
    for name, q, top in (("vote", r["vote"], 1), ("claim", r["claim"], 1), ("claim_top2", r["claim"], 2)):
        ids, _ = locate(b, q, top)
        res[name].append(len(gold & set(ids)) / len(gold))
        size[name].append(sum(len(b.chunks[i].text) for i in ids))
for k in res:
    v = res[k]
    print(f"{k}: gold share inside region mean {statistics.mean(v):.3f}, all-in {sum(x == 1 for x in v) / len(v):.3f}, "
          f"none {sum(x == 0 for x in v) / len(v):.3f}, region chars median {statistics.median(size[k]):.0f} (booklet {statistics.median(whole):.0f})")
