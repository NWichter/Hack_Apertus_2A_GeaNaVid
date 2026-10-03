"""Offline analysis of stored runs (no LLM calls): calibration with cross-fitting, number rule, error types.

python experiments/v1/analyze.py calib  dev_s apertus-v1.5-8b ret-vote-tr
python experiments/v1/analyze.py numbers dev_s apertus-v1.5-8b ret-vote-tr
python experiments/v1/analyze.py errors dev_s apertus-v1.5-8b ret-vote-tr
"""

import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint import numbers  # noqa: E402
from booklint.ingest import ingest  # noqa: E402
from booklint.metrics import macro_f1  # noqa: E402
from booklint.pipeline import apply_bias  # noqa: E402
from booklint.proposal import locate  # noqa: E402

NAMES = ["entailment", "neutral", "contradiction"]
GRID = [x / 4 for x in range(-16, 17)]


def load(split, model, name):
    rows = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "data" / "v1" / f"{split}.jsonl").open(encoding="utf-8")}
    preds = [json.loads(l) for l in (ROOT / "runs" / "v1" / split / model / f"{name}.jsonl").open(encoding="utf-8")]
    return [rows[p["id"]] for p in preds], preds


def relabel(preds, bias):
    out = []
    for p in preds:
        probs = p.get("raw_probs") or p.get("probs")
        if not probs:
            out.append(p["entailment_label"])
            continue
        q = apply_bias(probs, bias)
        out.append(NAMES.index(max(q, key=q.get)))
    return out


def fit(rows, preds):
    gold = [r["entailment_label"] for r in rows]
    best = (macro_f1(gold, relabel(preds, {}))[0], 0.0, 0.0)
    for bn, bc in itertools.product(GRID, GRID):
        f = macro_f1(gold, relabel(preds, {"neutral": bn, "contradiction": bc}))[0]
        if f > best[0] + 1e-9:
            best = (f, bn, bc)
    return best


def calib(rows, preds):
    gold = [r["entailment_label"] for r in rows]
    base = macro_f1(gold, [p["entailment_label"] for p in preds])[0]
    f_all, bn, bc = fit(rows, preds)
    dates = sorted({r["booklet_publish_date"] for r in rows})
    folds = [set(dates[0::2]), set(dates[1::2])]
    cv_pred = [None] * len(rows)
    for k in (0, 1):
        tr = [i for i, r in enumerate(rows) if r["booklet_publish_date"] not in folds[k]]
        te = [i for i, r in enumerate(rows) if r["booklet_publish_date"] in folds[k]]
        _, n_, c_ = fit([rows[i] for i in tr], [preds[i] for i in tr])
        lab = relabel([preds[i] for i in te], {"neutral": n_, "contradiction": c_})
        for i, l in zip(te, lab):
            cv_pred[i] = l
    conf = [max((p.get("raw_probs") or {"x": 1}).values()) for p in preds]
    return {
        "macro_f1": round(base, 4),
        "fit_all": {"macro_f1": round(f_all, 4), "neutral": bn, "contradiction": bc},
        "cross_fit_macro_f1": round(macro_f1(gold, cv_pred)[0], 4),
        "share_conf_gt_0.9": round(sum(c > 0.9 for c in conf) / len(conf), 3),
        "pred_dist": dict(Counter(p["entailment_label"] for p in preds)),
    }


_region_cache = {}


def region_texts(r):
    key = (r["booklet_url"], r["vote"])
    if key not in _region_cache:
        b = ingest(r["booklet_url"])
        ids, _ = locate(b, r["vote"])
        _region_cache[key] = [b.chunks[i].text for i in ids]
    return _region_cache[key]


def number_rule(rows, preds, scope="region"):
    gold = [r["entailment_label"] for r in rows]
    pred = [p["entailment_label"] for p in preds]
    new, changed = [], Counter()
    for r, p in zip(rows, preds):
        texts = [r["reference_string"]] if scope == "gold" else region_texts(r)
        miss = numbers.check(r["claim"], texts)["missing"]
        lab = p["entailment_label"]
        if miss and lab == 0:
            changed[(r["entailment_label"], 1)] += 1
            lab = 1
        new.append(lab)
    return {"before": round(macro_f1(gold, pred)[0], 4), "after": round(macro_f1(gold, new)[0], 4),
            "changed_gold_to_new": {f"{g}->{n}": c for (g, n), c in changed.items()}}


TYPES = {
    "number": lambda c: bool(re.search(r"\d", c)),
    "federal_council": lambda c: bool(re.search(r"bundesrat|conseil fédéral|consiglio federale", c, re.I)),
    "committee": lambda c: bool(re.search(r"komitee|comité|comitato|initiant|promot", c, re.I)),
    "parliament": lambda c: bool(re.search(r"parlament|bundesversammlung|assemblée|assemblea", c, re.I)),
    "voting_text": lambda c: bool(re.search(r"abstimmungstext|texte soumis|testo in votazione|texte de vote|testo sottoposto", c, re.I)),
    "summary": lambda c: bool(re.search(r"zusammenfassung|in kürze|en bref|in breve|résumé|riassunto", c, re.I)),
    "negation": lambda c: bool(re.search(r"\b(nicht|kein\w*|ne |n'|pas|non|nessun\w*)\b", c, re.I)),
    "recommendation": lambda c: bool(re.search(r"empf|recommand|raccomand|ablehn|rejet|respin", c, re.I)),
}


def errors(rows, preds):
    stats = defaultdict(Counter)
    for r, p in zip(rows, preds):
        g, q = r["entailment_label"], p["entailment_label"]
        cross = "cross" if r["claim_language"] != r["reference_language"] else "same"
        for t, f in TYPES.items():
            if f(r["claim"]):
                stats[t]["n"] += 1
                stats[t]["err"] += g != q
        stats["all"]["n"] += 1
        stats["all"]["err"] += g != q
        stats[cross]["n"] += 1
        stats[cross]["err"] += g != q
        if g != q:
            stats["confusion"][f"{g}->{q}"] += 1
            hit = bool(p.get("hits")) and p.get("recall") is not None
            stats["retrieval"]["miss" if hit else "na"] += 0
    out = {t: {"n": s["n"], "err_rate": round(s["err"] / s["n"], 3)} for t, s in stats.items() if "n" in s}
    out["confusion"] = dict(stats["confusion"])
    return out


def main():
    what, split, model, name = sys.argv[1:5]
    rows, preds = load(split, model, name)
    if what == "calib":
        print(json.dumps(calib(rows, preds), indent=2))
    elif what == "numbers":
        for scope in ("region", "gold"):
            print(scope, json.dumps(number_rule(rows, preds, scope)))
    elif what == "errors":
        print(json.dumps(errors(rows, preds), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
