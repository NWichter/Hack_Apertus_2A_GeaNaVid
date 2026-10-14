"""Proposal scoping on the stress set without LLM calls: does locate() put the gold page inside the region?
python experiments/stress/diag.py [dev|holdout] [--groups]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from booklint.ingest import ingest  # noqa: E402
from booklint.proposal import candidates, locate  # noqa: E402

D = ROOT / "data/stress-synth"


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else "dev"
    dates = set(json.loads((D / "split.json").read_text())[part])
    rows = [json.loads(x) for x in (D / "clean.jsonl").open(encoding="utf-8")]
    rows = [r for r in rows if r["booklet_date"] in dates]
    stat = defaultdict(lambda: [0, 0, 0])
    shown = set()
    for r in rows:
        b = ingest(str(D / "booklets" / r["booklet_path"]))
        if "--groups" in sys.argv and r["booklet_path"] not in shown:
            shown.add(r["booklet_path"])
            print("==", r["booklet_path"], b.pages, "pages")
            for g, ids in candidates(b).items():
                pages = sorted({b.chunks[i].page for i in ids})
                print(f"   {len(ids):4d} chunks p{pages[0]}-{pages[-1]}  {g[:90]!r}")
        region, prop = locate(b, r["vote"])
        pages = {b.chunks[i].page for i in region}
        whole = len(region) == len(b.chunks)
        k = r["booklet_path"]
        stat[k][0] += 1
        stat[k][1] += whole
        stat[k][2] += (not whole) and r["reference_page"] in pages
    tot = [0, 0, 0]
    for k, (n, w, ok) in sorted(stat.items()):
        print(f"{k:22s} n={n:3d} whole={w:3d} right={ok:3d} wrong={n - w - ok:3d}")
        tot = [a + b for a, b in zip(tot, (n, w, ok))]
    print("total n=%d whole=%d right=%d wrong=%d" % (tot[0], tot[1], tot[2], tot[0] - tot[1] - tot[2]))


if __name__ == "__main__":
    main()
