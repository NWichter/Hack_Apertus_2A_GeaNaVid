"""Run one pipeline configuration on a v1.0 split and store predictions, config and summary.

python experiments/v1/run.py --split dev_s --model apertus-v1.5-8b --name baseline --opts '{"mode": "baseline"}'
Output: runs/v1/<split>/<model>/<name>.{jsonl,config.json,summary.json}
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint.config import Settings  # noqa: E402
from booklint.llm import LLM, RETRIES, redact  # noqa: E402
from booklint.metrics import breakdown  # noqa: E402
from booklint.pipeline import Options, Pipeline  # noqa: E402
from booklint.retrieval_eval import gold_chunks  # noqa: E402
from booklint.textnorm import fold  # noqa: E402


# Ablations start from the plain pipeline; the CLI defaults (Options()) are the chosen configuration.
ABLATION_BASE = {"mode": "ladder", "translate": False, "fewshot": 0, "decompose": False, "tau_decompose": 0.75,
                 "section_boost": 1.0, "evidence_section": 1.0, "evidence_section_pool": 0,
                 "recheck": False, "committee_terms": False}


def load(split):
    """dev_rest = the 548 dev rows outside dev_s, which no option was chosen on."""
    if split == "dev_rest":
        used = {r["id"] for r in load("dev_s")}
        return [r for r in load("dev") if r["id"] not in used]
    path = ROOT / "data" / "v1" / f"{split}.jsonl"
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def _norm(text):
    import re

    return re.sub(r"[^0-9a-z]+", "", fold(text or ""))


def evidence_scores(pipeline, rows, preds, gold):
    """E/C answers: first evidence item inside the gold section (normalised substring), its page a gold page,
    any item inside the gold section (the proxies for OST's evidence check, slide 28)."""
    n = first = page = any_ = 0
    for r, p, g in zip(rows, preds, gold):
        if int(p.get("entailment_label", 1)) == 1 or not p.get("evidence"):
            continue
        b = pipeline.booklet(r["booklet_url"])[0]
        ref = _norm(r["reference_string"])
        pages = {b.chunks[i].page for i in g}
        inside = [len(_norm(e["text"])) >= 10 and _norm(e["text"]) in ref for e in p["evidence"]]
        n += 1
        first += inside[0]
        page += p["evidence"][0].get("page") in pages
        any_ += any(inside)
    return {"evidence_n": n, "evidence_first_in_gold": round(first / n, 4) if n else None,
            "evidence_page_gold": round(page / n, 4) if n else None, "evidence_any_in_gold": round(any_ / n, 4) if n else None}


def predict(pipeline, rows, workers):
    for r in rows:
        pipeline.booklet(r["booklet_url"])

    def one(r):
        try:
            out = pipeline.check(r["claim"], r["booklet_url"], r["claim_language"], r["reference_string"], r.get("vote"))
        except Exception as exc:
            out = {"decision": 1, "answer": "blank", "page": None, "evidence_sentence": None, "evidence_sentences": [],
                   "entailment_label": 1, "label_name": "neutral", "error": redact(repr(exc))[:300],
                   "evidence": [], "hits": [], "retrieved_ids": [], "ladder_step": "error", "confidence": None,
                   "usage": {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "llm_seconds": 0.0}}
        out["id"] = r["id"]
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev_s")
    ap.add_argument("--model", default="apertus-v1.5-8b")
    ap.add_argument("--name", required=True)
    ap.add_argument("--opts", default="{}")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--base", default="ablation", choices=["ablation", "default"],
                    help="option base: the plain ablation pipeline or the CLI default (Options())")
    ap.add_argument("--offline", action="store_true", help="answer from the response cache only; a miss is an error")
    args = ap.parse_args()
    rows = load(args.split)[: args.limit or None]
    base = ABLATION_BASE if args.base == "ablation" else {}
    opts = Options(**{**base, **json.loads(args.opts)})
    llm = LLM(Settings.from_env(args.model))
    if args.offline:
        def refuse(**_):
            raise RuntimeError("cache miss in an offline replay")

        llm.client.chat.completions.create = refuse
    pipeline = Pipeline(llm, opts)
    t0 = time.perf_counter()
    preds = predict(pipeline, rows, args.workers)
    wall = time.perf_counter() - t0
    gold = [gold_chunks(pipeline.booklet(r["booklet_url"])[0], r["reference_string"]) for r in rows]
    summary = breakdown(rows, preds, gold)
    summary.update(evidence_scores(pipeline, rows, preds, gold))
    summary.update({"retries": dict(RETRIES), "workers": args.workers, "model": args.model, "name": args.name, "split": args.split, "wall_s": round(wall, 1),
                    "uncached_calls": sum(p["usage"].get("llm_calls", 0) - p["usage"].get("cached_calls", 0) for p in preds)})
    out = ROOT / "runs" / "v1" / args.split / args.model
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"{args.name}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for p in preds:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    config = {"name": args.name, "split": args.split, "model": args.model, "options": asdict(opts),
              "split_seed": 2026, "rows": len(rows), "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "command": " ".join(sys.argv)}
    (out / f"{args.name}.config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / f"{args.name}.summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    keys = ["macro_f1", "ci95", "evidence_first_in_gold", "evidence_page_gold", "input_tokens_mean", "f1_e", "f1_n", "f1_c", "macro_f1_same", "macro_f1_cross", "recall_hit",
            "tokens_mean", "llm_calls_mean", "llm_seconds_p50", "errors", "uncached_calls", "wall_s", "retries"]
    print(args.split, args.model, args.name, {k: summary.get(k) for k in keys}, flush=True)


if __name__ == "__main__":
    main()
