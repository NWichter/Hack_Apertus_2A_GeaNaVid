"""Offline retrieval check: does BM25 top-k (plus neighbours) contain the gold reference? No LLM calls."""

import json
import re
from collections import defaultdict

from .metrics import evidence_hit
from .retrieve import Retriever
from .ingest import ingest
from .textnorm import fold


def _norm(text):
    return re.sub(r"[^0-9a-z]+", "", fold(text))


def gold_chunks(booklet, reference):
    """Chunk ids whose text lies inside the gold section (normalised substring of the first 80 characters)."""
    ref = _norm(reference or "")
    out = []
    for c in booklet.chunks:
        n = _norm(c.text)
        if len(n) >= 20 and n[:80] in ref:
            out.append(c.id)
    return out


def recall(rows, ks=(1, 3, 5, 8), neighbors=1, translations=None):
    cache = {}
    stats = defaultdict(lambda: defaultdict(int))
    tokens = defaultdict(list)
    for r in rows:
        if int(r["entailment_label"]) == 1:
            continue
        url = r["booklet_url"]
        if url not in cache:
            b = ingest(url)
            cache[url] = (b, Retriever(b))
        booklet, retriever = cache[url]
        queries = [r["claim"]]
        if translations and r.get("id") in translations:
            queries.append(translations[r["id"]])
        pair = "same" if r["claim_language"] == r["booklet_language"] else "cross"
        for k in ks:
            ids, _, _ = retriever.top_k(queries, k, neighbors)
            hit = evidence_hit(
                [booklet.chunks[i].text for i in ids], r["reference_string"]
            )
            stats[(pair, k)]["hit"] += hit
            stats[(pair, k)]["n"] += 1
            tokens[(pair, k)].append(
                sum(len(booklet.chunks[i].render()) for i in ids) / 3.6
            )
    out = {}
    for (pair, k), s in sorted(stats.items()):
        t = tokens[(pair, k)]
        out[f"{pair}@{k}"] = {
            "recall": round(s["hit"] / s["n"], 3),
            "n": s["n"],
            "approx_tokens": round(sum(t) / len(t)),
        }
    return out


if __name__ == "__main__":
    import sys

    rows = [
        json.loads(l)
        for f in sys.argv[1:]
        for l in open(f, encoding="utf-8")
        if l.strip()
    ]
    print(json.dumps(recall(rows), indent=2))
