"""Offline check of the sentence-level evidence on a stored run (0 Apertus calls).

python experiments/v1/sentences.py test apertus-v1.5-8b default [--sample 30 --out runs/v1/sentences-sample.jsonl]

Hit = the first evidence sentence of the run (`evidence_sentences[0]`) lies inside the gold section
(`reference_string`, normalised substring match). Reported for rows predicted entailment or contradiction,
against simpler alternatives computed from the cited chunks.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint import sentences  # noqa: E402
from booklint.ingest import ingest  # noqa: E402
from booklint.retrieve import Retriever  # noqa: E402
from booklint.textnorm import fold  # noqa: E402


def norm(text):
    return re.sub(r"[^0-9a-z]+", "", fold(text))


def inside(text, ref):
    n = norm(text)
    return len(n) >= 10 and n in ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("split")
    ap.add_argument("model")
    ap.add_argument("run")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    rows = {
        json.loads(line)["id"]: json.loads(line)
        for line in (ROOT / "data/v1" / f"{args.split}.jsonl").open(encoding="utf-8")
    }
    preds = [
        json.loads(line)
        for line in (
            ROOT / "runs/v1" / args.split / args.model / f"{args.run}.jsonl"
        ).open(encoding="utf-8")
    ]
    books = {}
    stats = {
        k: 0
        for k in (
            "n",
            "chosen",
            "first",
            "chunk",
            "chunk_in_gold",
            "chosen_if_chunk",
            "fallback",
            "spans2",
            "cited_only",
        )
    }
    chars = []
    by = {}
    out = []
    for p in preds:
        if p["entailment_label"] == 1:
            continue
        r = rows[p["id"]]
        url = r["booklet_url"]
        if url not in books:
            b = ingest(url)
            books[url] = (b, Retriever(b))
        b, ret = books[url]
        ids = [e["chunk_id"] for e in p.get("evidence", [])]
        if not ids:
            stats["fallback"] += 1
            ids = p.get("hits", [])[:5] or p.get("retrieved_ids", [])
        chunks = [b.chunks[i] for i in ids]
        queries = [q for q in (p.get("translation"), r["claim"]) if q]
        picked = p.get("evidence_sentences")
        if picked is None:
            picked = sentences.select(chunks, queries, ret.bm25.idf)
        if not picked:
            continue
        ref = norm(r["reference_string"])
        hit = inside(picked[0]["text"], ref)
        only_cited = sentences.select(chunks, queries, ret.bm25.idf, bonus=1.0)
        stats["cited_only"] += bool(only_cited) and inside(only_cited[0]["text"], ref)
        first_sent = chunks[0].text[slice(*sentences.split(chunks[0].text)[0])]
        chunk_hit = any(inside(c.text[:300], ref) for c in chunks)
        stats["n"] += 1
        stats["chosen"] += hit
        stats["first"] += inside(first_sent, ref)
        stats["chunk"] += inside(chunks[0].text[:300], ref)
        stats["chunk_in_gold"] += chunk_hit
        stats["chosen_if_chunk"] += hit and chunk_hit
        stats["spans2"] += len(picked) > 1
        chars.append(len(picked[0]["text"]))
        key = (p["label_name"][0].upper(), r["claim_language"], b.language)
        k2 = f"{key[0]} {'same' if key[1] == key[2] else 'cross'}"
        by.setdefault(k2, [0, 0])
        by[k2][0] += 1
        by[k2][1] += hit
        out.append(
            {
                "id": p["id"],
                "gold": r["entailment_label"],
                "pred": p["entailment_label"],
                "claim_language": r["claim_language"],
                "booklet_language": b.language,
                "claim": r["claim"],
                "translation": p.get("translation"),
                "hit": hit,
                "chunk_hit": chunk_hit,
                "sentences": picked,
                "chunk": chunks[0].text if chunks else "",
            }
        )
    n = stats["n"]
    chars.sort()
    report = {
        "rows_ec_pred": n,
        "sentence_in_gold": round(stats["chosen"] / n, 4),
        "best_sentence_of_cited_chunks_only_in_gold": round(stats["cited_only"] / n, 4),
        "first_sentence_of_first_cited_chunk_in_gold": round(stats["first"] / n, 4),
        "first_cited_chunk_in_gold": round(stats["chunk"] / n, 4),
        "any_cited_chunk_in_gold": round(stats["chunk_in_gold"] / n, 4),
        "sentence_in_gold_given_a_cited_chunk_in_gold": round(
            stats["chosen_if_chunk"] / max(stats["chunk_in_gold"], 1), 4
        ),
        "fallback_no_cited_chunk": stats["fallback"],
        "two_spans": stats["spans2"],
        "sentence_chars_median": chars[len(chars) // 2],
        "sentence_chars_p90": chars[int(0.9 * (len(chars) - 1))],
        "by_label_pair": {
            k: {"n": v[0], "hit": round(v[1] / v[0], 3)} for k, v in sorted(by.items())
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.sample and args.out:
        rng = random.Random(2026)
        groups = {}
        for o in out:
            groups.setdefault((o["pred"], o["booklet_language"]), []).append(o)
        sample = []
        keys = sorted(groups)
        while len(sample) < args.sample and any(groups.values()):
            for k in keys:
                if groups[k] and len(sample) < args.sample:
                    sample.append(groups[k].pop(rng.randrange(len(groups[k]))))
        Path(args.out).write_text(
            "\n".join(json.dumps(s, ensure_ascii=False) for s in sample) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
