"""Regression guard for proposal scoping on OST v1.1 (all splits), no LLM calls: the region locate() gives for each
row's `vote`. python experiments/stress/scope_regress.py save|check  (file: runs/v1/scope-regress-ost.json)
Rows whose vote title is in another language than the booklet are scoped with the stored translation in the
pipeline; here the raw title is used, which is enough to see whether the scoping code changed anything."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments/v1"))
from booklint.ingest import ingest  # noqa: E402
from booklint.proposal import locate  # noqa: E402
from run import load  # noqa: E402

OUT = ROOT / "runs/v1/scope-regress-ost.json"


def current():
    out = {}
    for split in ("dev_s_v11", "dev_rest_v11", "test_v11"):
        for r in load(split):
            b = ingest(r["booklet_url"])
            region, prop = locate(b, r.get("vote") or r["claim"])
            texts = "\n".join(b.chunks[i].render() for i in region)
            out[r["id"]] = [prop, len(region), hashlib.sha1(texts.encode()).hexdigest()[:12]]
    return out


def main():
    cur = current()
    if sys.argv[1] == "save":
        OUT.write_text(json.dumps(cur, indent=0) + "\n", encoding="utf-8")
        print("saved", len(cur))
    else:
        old = json.loads(OUT.read_text(encoding="utf-8"))
        diff = [k for k in old if old[k] != cur.get(k)]
        print(len(old), "rows,", len(diff), "differ", diff[:20])


if __name__ == "__main__":
    main()
