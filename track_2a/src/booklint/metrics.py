import random
from collections import Counter, defaultdict

from rapidfuzz import fuzz

from .textnorm import clean

CLASSES = (0, 1, 2)


def macro_f1(gold, pred):
    f1s = {}
    for c in CLASSES:
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        f1s[c] = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    present = [c for c in CLASSES if c in gold or c in pred]
    return sum(f1s[c] for c in present) / len(present) if present else 0.0, f1s


def bootstrap(gold, pred, n=1000, seed=13):
    rng = random.Random(seed)
    idx = list(range(len(gold)))
    vals = []
    for _ in range(n):
        s = [rng.choice(idx) for _ in idx]
        vals.append(macro_f1([gold[i] for i in s], [pred[i] for i in s])[0])
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n) - 1]


def evidence_hit(texts, reference):
    paras = [clean(p) for p in (reference or "").split("\n\n") if p.strip()]
    for t in texts:
        t = clean(t)
        if len(t) < 15:
            continue
        for p in paras:
            short, long_ = (t, p) if len(t) <= len(p) else (p, t)
            if fuzz.partial_ratio(short[:300], long_) >= 90:
                return True
    return False


def percentile(values, q):
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]


def summarize(rows, preds, chunk_text=None):
    gold = [int(r.get("label", r.get("entailment_label", 1))) for r in rows]
    pred = [int(p.get("label", p.get("entailment_label", 1))) for p in preds]
    f1, per = macro_f1(gold, pred)
    lo, hi = bootstrap(gold, pred)
    conf = Counter(zip(gold, pred))
    grounded = rec_hits = n_ec = 0
    for r, p in zip(rows, preds):
        g = int(r.get("label", r.get("entailment_label", 1)))
        q = int(p.get("label", p.get("entailment_label", 1)))
        if g == 1:
            continue
        n_ec += 1
        cited = [e["text"] for e in p.get("evidence", [])]
        if g == q and evidence_hit(
            cited, r.get("reference_string", "")
        ):
            grounded += 1
        if chunk_text is not None:
            retrieved = [chunk_text(r, i) for i in p.get("retrieved_ids", [])]
            rec_hits += evidence_hit(retrieved, r.get("reference_string", ""))
    tokens = [
        p.get("metrics", {}).get("input_tokens", p.get("usage", {}).get("prompt_tokens", 0))
        for p in preds
    ]
    seconds = [
        p.get("metrics", {}).get("inference_time_ms", 0) / 1000.0 if "metrics" in p
        else p.get("usage", {}).get("llm_seconds", 0.0)
        for p in preds
    ]
    steps = Counter(p.get("ladder_step", "predict") for p in preds)
    by_pair = defaultdict(lambda: ([], []))
    for r, g, q in zip(rows, gold, pred):
        key = f"{r.get('claim_language')}->{r.get('booklet_language', r.get('reference_language'))}"
        by_pair[key][0].append(g)
        by_pair[key][1].append(q)
    return {
        "n": len(rows),
        "macro_f1": round(f1, 4),
        "ci95": [round(lo, 4), round(hi, 4)],
        "f1_e": round(per[0], 4),
        "f1_n": round(per[1], 4),
        "f1_c": round(per[2], 4),
        "accuracy": round(sum(g == p for g, p in zip(gold, pred)) / len(rows), 4),
        "confusion": {f"{g}->{p}": n for (g, p), n in sorted(conf.items())},
        "grounded_rate_ec": round(grounded / n_ec, 4) if n_ec else None,
        "retrieval_recall_ec": round(rec_hits / n_ec, 4)
        if n_ec and chunk_text
        else None,
        "prompt_tokens_mean": round(sum(tokens) / len(tokens), 1) if tokens else 0.0,
        "prompt_tokens_p95": percentile(tokens, 0.95),
        "completion_tokens_mean": round(
            sum(p.get("metrics", {}).get("output_tokens", p.get("usage", {}).get("completion_tokens", 0)) for p in preds) / len(preds), 1
        ) if preds else 0.0,
        "llm_calls_mean": round(
            sum(p.get("usage", {}).get("llm_calls", 1) for p in preds) / len(preds), 3
        ) if preds else 0.0,
        "seconds_p50": percentile(seconds, 0.5),
        "seconds_p95": percentile(seconds, 0.95),
        "steps": dict(steps),
        "by_pair": {
            k: round(macro_f1(g, q)[0], 3) for k, (g, q) in sorted(by_pair.items())
        },
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def breakdown(rows, preds, gold_ids=None):
    """Macro-F1 overall, per label, same vs cross language; cost per claim; retrieval recall against gold chunk ids."""
    gold = [int(r.get("label", r.get("entailment_label", 1))) for r in rows]
    pred = [int(p.get("label", p.get("entailment_label", 1))) for p in preds]
    f1, per = macro_f1(gold, pred)
    lo, hi = bootstrap(gold, pred)
    out = {
        "n": len(rows),
        "macro_f1": round(f1, 4),
        "ci95": [round(lo, 4), round(hi, 4)],
        "f1_e": round(per[0], 4),
        "f1_n": round(per[1], 4),
        "f1_c": round(per[2], 4),
        "accuracy": round(sum(g == p for g, p in zip(gold, pred)) / len(rows), 4),
        "confusion": {f"{g}->{p}": n for (g, p), n in sorted(Counter(zip(gold, pred)).items())},
    }
    def blang(r):
        return r.get("reference_language", r.get("booklet_language"))

    for name, keep in (("same", lambda r: r["claim_language"] == blang(r)),
                       ("cross", lambda r: r["claim_language"] != blang(r))):
        idx = [i for i, r in enumerate(rows) if keep(r)]
        if idx:
            out[f"macro_f1_{name}"] = round(macro_f1([gold[i] for i in idx], [pred[i] for i in idx])[0], 4)
            out[f"n_{name}"] = len(idx)
    usage = [p.get("usage", {}) for p in preds]
    out.update({
        "prompt_tokens_mean": _mean([u.get("prompt_tokens", 0) for u in usage]),
        "completion_tokens_mean": _mean([u.get("completion_tokens", 0) for u in usage]),
        "tokens_mean": _mean([u.get("prompt_tokens", 0) + u.get("completion_tokens", 0) for u in usage]),
        "prompt_tokens_p95": percentile([u.get("prompt_tokens", 0) for u in usage], 0.95),
        "llm_calls_mean": _mean([u.get("llm_calls", 0) for u in usage]),
        "llm_seconds_mean": _mean([u.get("llm_seconds", 0.0) for u in usage]),
        "llm_seconds_p50": percentile([u.get("llm_seconds", 0.0) for u in usage], 0.5),
        "llm_seconds_p95": percentile([u.get("llm_seconds", 0.0) for u in usage], 0.95),
        "errors": sum("error" in p for p in preds),
        "steps": dict(Counter(p.get("ladder_step") for p in preds)),
    })
    if gold_ids is not None and any(p.get("hits") for p in preds):
        hit = cov = n = 0
        for g, p in zip(gold_ids, preds):
            if not g:
                continue
            n += 1
            g = set(g)
            hit += bool(g & set(p.get("hits", [])))
            ret = set(p.get("retrieved_ids", []))
            cov += len(g & ret) / len(g)
        out["recall_hit"] = round(hit / n, 4) if n else None
        out["gold_coverage"] = round(cov / n, 4) if n else None
    return out
