"""Offline comparison of evidence-sentence choices on a stored run (0 Apertus calls).

python experiments/v1/evidence_variants.py dev_s apertus-v1.5-8b default

For every entailment/contradiction answer the evidence sentence is chosen again from the stored cited chunks and
top-5 hits with each variant; reported: first sentence inside the gold section (normalised substring), page of the
first sentence is a gold page, any span inside the gold section, median length.
Variant "cue section": sentences of the section the claim points to (summary -> context section, committee ->
committee pages, Federal Council -> its arguments and recommendation, voting text -> legal text, no cue -> context
section) get an extra factor; "cue chunks in pool" adds the best BM25 chunks of that section to the candidates.
"""

import argparse
import functools
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint import sentences  # noqa: E402
from booklint.ingest import ingest  # noqa: E402
from booklint.proposal import locate  # noqa: E402
from booklint.sections import classify, claim_cue, factors, PREFER  # noqa: E402
from booklint.retrieval_eval import gold_chunks  # noqa: E402
from booklint.retrieve import Retriever  # noqa: E402
from booklint.textnorm import fold  # noqa: E402


@functools.lru_cache(None)
def book(url):
    b = ingest(url)
    return b, Retriever(b)


_KINDS = {}


def kinds_of(url, b):
    if url not in _KINDS:
        _KINDS[url] = classify(b)
    return _KINDS[url]


def norm(text):
    return re.sub(r"[^0-9a-z]+", "", fold(text))


def inside(text, ref):
    n = norm(text)
    return len(n) >= 10 and n in ref


VARIANTS = {
    "current (cited x1.2)": {"cue": 1.0},
    "cue section x1.3": {"cue": 1.3},
    "cue section x1.5": {"cue": 1.5},
    "cue section x2.0": {"cue": 2.0},
    "cue section x1.5 + 2 cue chunks in pool": {"cue": 1.5, "pool_cue": 2},
    "cue section x1.5 + 4 cue chunks in pool": {"cue": 1.5, "pool_cue": 4},
    "cue section x2.0 + 4 cue chunks in pool": {"cue": 2.0, "pool_cue": 4},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("split")
    ap.add_argument("model")
    ap.add_argument("run")
    args = ap.parse_args()
    rows = {
        json.loads(x)["id"]: json.loads(x)
        for x in (ROOT / "data/v1" / f"{args.split}.jsonl").open(encoding="utf-8")
    }
    preds = [
        json.loads(x)
        for x in (
            ROOT / "runs/v1" / args.split / args.model / f"{args.run}.jsonl"
        ).open(encoding="utf-8")
    ]
    stats = {v: {"n": 0, "first": 0, "page": 0, "any": 0, "len": []} for v in VARIANTS}
    for p in preds:
        if int(p["entailment_label"]) == 1:
            continue
        r = rows[p["id"]]
        b, ret = book(r["booklet_url"])
        ref = norm(r["reference_string"])
        gold_pages = {b.chunks[i].page for i in gold_chunks(b, r["reference_string"])}
        region, _ = locate(b, r["vote"])
        kinds = kinds_of(r["booklet_url"], b)
        cue = claim_cue(r["claim"], p.get("translation"))
        cited = [
            e["chunk_id"]
            for e in p.get("evidence", [])
            if isinstance(e, dict) and "chunk_id" in e
        ][:3]
        if not cited:
            cited = [s["chunk_id"] for s in p.get("evidence_sentences") or []]
        hits = p.get("hits") or []
        queries = ([p["translation"]] if p.get("translation") else []) + [r["claim"]]
        for name, v in VARIANTS.items():
            k = v.get("k", 5)
            pool = list(cited) + [i for i in hits[:k] if i not in cited]
            if v.get("pool_cue"):
                want = PREFER.get(cue, set())
                allowed = set(region)
                ranked = [
                    i for i in ret.rank(queries)[0] if i in allowed and kinds[i] in want
                ]
                pool += [i for i in ranked[: v["pool_cue"]] if i not in pool]
            spans = sentences.select(
                [b.chunks[i] for i in pool],
                queries,
                ret.bm25.idf,
                preferred=cited,
                bonus=1.2,
                factors=factors(kinds, cue, pool, v["cue"]),
            )
            if not spans:
                continue
            s = stats[name]
            s["n"] += 1
            s["first"] += inside(spans[0]["text"], ref)
            s["page"] += spans[0]["page"] in gold_pages
            s["any"] += any(inside(x["text"], ref) for x in spans)
            s["len"].append(len(spans[0]["text"]))
    out = {}
    for name, s in stats.items():
        n = max(s["n"], 1)
        lens = sorted(s["len"]) or [0]
        out[name] = {
            "n": s["n"],
            "first_in_gold": round(s["first"] / n, 3),
            "page_gold": round(s["page"] / n, 3),
            "any_in_gold": round(s["any"] / n, 3),
            "chars_median": lens[len(lens) // 2],
        }
    print(
        json.dumps(
            {"run": f"{args.split}/{args.model}/{args.run}", "variants": out},
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
