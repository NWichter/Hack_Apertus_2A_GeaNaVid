"""Error analysis of a stored run by error type (0 Apertus calls).

python experiments/v1/errors.py dev_s apertus-v1.5-8b default [--dump runs/v1/dev_s/errors-8b.jsonl]

Types (a row can have several): number (digits or number words in the claim), actor (claim names the Federal
Council, Parliament, committee or cantons), cross (claim language != booklet language), table (gold section looks
like a table: many short numeric lines), recommendation, negation. For every error: was a gold chunk retrieved
(hit@5 + neighbours), did Apertus cite a gold chunk, and the confusion gold -> predicted. For E/C answers: is the
first evidence sentence inside the gold section, is its page a gold page.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint.ingest import ingest  # noqa: E402
from booklint.metrics import macro_f1  # noqa: E402
from booklint.retrieval_eval import gold_chunks  # noqa: E402
from booklint.textnorm import fold  # noqa: E402

NUMBER_WORDS = r"million|milliard|miliard|milion|prozent|percent|pour ?cent|per ?cento|hälfte|moitié|metà|drittel|tiers|terzo|viertel|quart"
TYPES = {
    "number": lambda r: bool(re.search(r"\d|" + NUMBER_WORDS, r["claim"], re.I)),
    "actor": lambda r: bool(
        re.search(
            r"bundesrat|conseil fédéral|consiglio federale|parlament|assemblée|assemblea|komitee|comité|comitato|initiant|kanton|canton",
            r["claim"],
            re.I,
        )
    ),
    "cross": lambda r: r["claim_language"] != r["reference_language"],
    "table": lambda r: _tableish(r["reference_string"]),
    "recommendation": lambda r: bool(
        re.search(
            r"empf|recommand|raccomand|ablehn|rejet|respin|annehm|accept|accett",
            r["claim"],
            re.I,
        )
    ),
    "negation": lambda r: bool(
        re.search(
            r"\b(nicht|kein\w*|nie|ne|n'|pas|non|nessun\w*|mai)\b", r["claim"], re.I
        )
    ),
}
NAMES = ["E", "N", "C"]


def _tableish(text):
    lines = [x.strip() for x in text.split("\n") if x.strip()]
    if len(lines) < 4:
        return False
    numeric = sum(1 for x in lines if len(x) < 60 and re.search(r"\d", x))
    return numeric / len(lines) >= 0.4


def norm(text):
    return re.sub(r"[^0-9a-z]+", "", fold(text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("split")
    ap.add_argument("model")
    ap.add_argument("run")
    ap.add_argument("--dump", default="")
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
    books = {}
    by_type = defaultdict(Counter)
    cause = Counter()
    conf = Counter()
    ev = Counter()
    ev_type = defaultdict(Counter)
    dump = []
    gold_all, pred_all = [], []
    for p in preds:
        r = rows[p["id"]]
        url = r["booklet_url"]
        if url not in books:
            books[url] = ingest(url)
        b = books[url]
        gold = set(gold_chunks(b, r["reference_string"]))
        g, q = int(r["entailment_label"]), int(p["entailment_label"])
        gold_all.append(g)
        pred_all.append(q)
        types = [t for t, f in TYPES.items() if f(r)]
        for t in types + ["all"]:
            by_type[t]["n"] += 1
            by_type[t]["err"] += g != q
        retrieved = set(p.get("retrieved_ids") or [])
        cited = {
            e["chunk_id"]
            for e in p.get("evidence", [])
            if isinstance(e, dict) and "chunk_id" in e
        }
        if not cited:
            cited = {s["chunk_id"] for s in p.get("evidence_sentences") or []}
        hit = bool(gold & retrieved) if gold else None
        if q != 1:
            ref = norm(r["reference_string"])
            first = (p.get("evidence_sentences") or [{}])[0]
            text = first.get("text") or p.get("evidence_sentence") or ""
            inside = len(norm(text)) >= 10 and norm(text) in ref
            gold_pages = {b.chunks[i].page for i in gold}
            ev["n"] += 1
            ev["inside"] += inside
            ev["page"] += first.get("page", p.get("page")) in gold_pages
            ev["retrieved_gold"] += bool(hit)
            ev["no_gold_chunk"] += not gold
            for t in types:
                ev_type[t]["n"] += 1
                ev_type[t]["inside"] += inside
        if g != q:
            conf[f"{NAMES[g]}->{NAMES[q]}"] += 1
            if not gold:
                c = "gold not mappable"
            elif not hit:
                c = "retrieval miss"
            elif g != 1 and not (gold & cited) and q != 1:
                c = "judged on other passage"
            else:
                c = "wrong judgement, gold retrieved"
            cause[c] += 1
            dump.append(
                {
                    "id": p["id"],
                    "gold": NAMES[g],
                    "pred": NAMES[q],
                    "cause": c,
                    "types": types,
                    "claim": r["claim"],
                    "translation": p.get("translation"),
                    "vote": r["vote"],
                    "confidence": p.get("confidence"),
                    "step": p.get("ladder_step"),
                    "evidence": [
                        s.get("text") for s in p.get("evidence_sentences") or []
                    ][:2],
                    "reference": r["reference_string"][:600],
                }
            )
    f1 = macro_f1(gold_all, pred_all)[0]
    out = {
        "run": f"{args.split}/{args.model}/{args.run}",
        "macro_f1": round(f1, 4),
        "errors": sum(cause.values()),
        "confusion": dict(conf.most_common()),
        "cause": dict(cause.most_common()),
        "by_type": {
            t: {"n": s["n"], "err": s["err"], "err_rate": round(s["err"] / s["n"], 3)}
            for t, s in by_type.items()
        },
        "evidence_ec": {
            "n": ev["n"],
            "first_in_gold": round(ev["inside"] / max(ev["n"], 1), 3),
            "first_page_gold": round(ev["page"] / max(ev["n"], 1), 3),
            "gold_retrieved": round(ev["retrieved_gold"] / max(ev["n"], 1), 3),
            "gold_unmappable": ev["no_gold_chunk"],
        },
        "evidence_by_type": {
            t: {"n": s["n"], "first_in_gold": round(s["inside"] / s["n"], 3)}
            for t, s in ev_type.items()
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if args.dump:
        Path(args.dump).write_text(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in dump) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
