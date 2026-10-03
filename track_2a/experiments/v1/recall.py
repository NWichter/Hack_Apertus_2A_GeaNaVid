"""Offline Recall@k of the retrieval variants against the gold section (reference_string). No LLM calls,
except that translations are read from an existing run file (--translations runs/v1/.../ret-vote-tr.jsonl).

Hit@k: at least one of the top-k chunks lies in the gold section. Tokens: rendered context after neighbour expansion / 3.5.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint.ingest import ingest  # noqa: E402
from booklint.pipeline import Options, Pipeline  # noqa: E402
from booklint.retrieval_eval import gold_chunks  # noqa: E402
from booklint.proposal import locate  # noqa: E402
from booklint.retrieve import Retriever  # noqa: E402


class NoLLM:
    model = "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--translations", default="")
    ap.add_argument("--variants", default="bm25:booklet,bm25:vote,bm25:claim,dense:vote,hybrid:vote,hybrid:booklet")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    rows = [json.loads(line) for line in (ROOT / "data" / "v1" / f"{args.split}.jsonl").open(encoding="utf-8")]
    tr = {}
    if args.translations:
        for line in open(args.translations, encoding="utf-8"):
            p = json.loads(line)
            if p.get("translation"):
                tr[p["id"]] = p["translation"]
        rows = [r for r in rows if r["claim_language"] == r["reference_language"] or r["id"] in tr]
    ks = (1, 3, 5, 8, 10)
    stats = defaultdict(lambda: defaultdict(float))
    for variant in args.variants.split(","):
        retr, scope = variant.split(":")[:2]
        use_tr = variant.endswith(":tr")
        par = variant.endswith(":par")
        pipe = Pipeline(NoLLM(), Options(retriever=retr, scope=scope, rerank="", crossling="parallel" if par else "none"))
        for r in rows:
            b, ret = pipe.booklet(r["booklet_url"])
            gold = set(gold_chunks(b, r["reference_string"]))
            if not gold:
                continue
            queries = [r["claim"]] + ([tr[r["id"]]] if use_tr and r["id"] in tr else [])
            if scope == "vote":
                region, _ = locate(b, r["vote"])
            elif scope == "claim":
                region, _ = locate(b, " ".join(queries))
            else:
                region = [c.id for c in b.chunks]
            pipe.opt.k = max(ks)
            pipe.opt.route = False
            hits, _, _ = pipe._hits(r["booklet_url"], b, ret, queries, r["claim"], r["claim_language"], region, None, None)
            pair = "same" if r["claim_language"] == r["reference_language"] else "cross"
            for part in (pair, "all"):
                s = stats[(variant, part)]
                s["n"] += 1
                for k in ks:
                    s[f"hit@{k}"] += bool(gold & set(hits[:k]))
                ctx = ret.expand(hits[:5], 1)
                s["tokens@5"] += sum(len(b.chunks[i].render()) for i in ctx) / 3.5
                s["region_tokens"] += sum(len(b.chunks[i].render()) for i in region) / 3.5
    out = []
    for (variant, part), s in sorted(stats.items()):
        n = s["n"]
        rec = {"variant": variant, "part": part, "n": int(n)}
        rec.update({k: round(v / n, 3) for k, v in s.items() if k != "n"})
        out.append(rec)
        print(json.dumps(rec))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
