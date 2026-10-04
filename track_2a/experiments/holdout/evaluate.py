"""One-time evaluation of the synthetic hold-out (data/holdout-synth/holdout.jsonl). Not OST data.

python experiments/holdout/evaluate.py --model apertus-v1.5-8b --mode retrieval|baseline|easy
Output: runs/holdout-synth/<model>/<mode>.{jsonl,summary.json}. The claim language is detected (as in OST's
input); the booklet is the local PDF; evidence is checked against the reference section and the pages of the
generator's evidence sentences.
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint.config import Settings  # noqa: E402
from booklint.llm import LLM, RETRIES, redact  # noqa: E402
from booklint.metrics import bootstrap, efficiency, macro_f1  # noqa: E402
from booklint.pipeline import Options, Pipeline  # noqa: E402
from booklint.textnorm import fold  # noqa: E402


def norm(text):
    return re.sub(r"[^0-9a-z]+", "", fold(text or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument(
        "--mode", default="retrieval", choices=["retrieval", "baseline", "easy"]
    )
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--name", default=None, help="output name (default: the mode)")
    args = ap.parse_args()
    rows = [
        json.loads(x)
        for x in (ROOT / "data/holdout-synth/holdout.jsonl").open(encoding="utf-8")
    ]
    pipeline = Pipeline(LLM(Settings.from_env(args.model)), Options(mode=args.mode))

    def one(r):
        path = str(ROOT / r["booklet_path"])
        try:
            if args.mode == "easy":
                out = pipeline.check(
                    r["claim"], None, None, r["reference_string"], None, r["id"]
                )
            else:
                out = pipeline.check(r["claim"], path, None, None, r["vote"], r["id"])
        except Exception as exc:
            out = {
                "label": 1,
                "entailment_label": 1,
                "evidence": [],
                "error": redact(repr(exc))[:300],
                "metrics": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "inference_time_ms": 0,
                },
                "usage": {},
            }
        out["id"] = r["id"]
        return out

    for r in rows:
        if args.mode != "easy":
            pipeline.booklet(str(ROOT / r["booklet_path"]))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        preds = list(pool.map(one, rows))
    gold = [r["entailment_label"] for r in rows]
    pred = [int(p["entailment_label"]) for p in preds]
    f1, per = macro_f1(gold, pred)
    lo, hi = bootstrap(gold, pred)
    same = [
        i for i, r in enumerate(rows) if r["claim_language"] == r["booklet_language"]
    ]
    cross = [
        i for i, r in enumerate(rows) if r["claim_language"] != r["booklet_language"]
    ]
    ev = {"n": 0, "first_in_reference": 0, "first_on_gold_page": 0}
    for r, p in zip(rows, preds):
        if p["entailment_label"] == 1 or not p.get("evidence"):
            continue
        first = p["evidence"][0]
        ev["n"] += 1
        ev["first_in_reference"] += len(norm(first["text"])) >= 10 and norm(
            first["text"]
        ) in norm(r["reference_string"])
        if args.mode != "easy":
            ev["first_on_gold_page"] += first["page"] in {
                e["page"] for e in r.get("evidence", [])
            }
    summary = {
        "set": "holdout-synth (synthetic, not OST)",
        "model": args.model,
        "mode": args.mode,
        "n": len(rows),
        "macro_f1": round(f1, 4),
        "ci95": [round(lo, 4), round(hi, 4)],
        "f1_e": round(per[0], 4),
        "f1_n": round(per[1], 4),
        "f1_c": round(per[2], 4),
        "macro_f1_same": round(
            macro_f1([gold[i] for i in same], [pred[i] for i in same])[0], 4
        ),
        "n_same": len(same),
        "macro_f1_cross": round(
            macro_f1([gold[i] for i in cross], [pred[i] for i in cross])[0], 4
        ),
        "n_cross": len(cross),
        "evidence_ec": ev["n"],
        "evidence_first_in_reference": round(
            ev["first_in_reference"] / max(ev["n"], 1), 4
        ),
        "evidence_first_on_gold_page": round(
            ev["first_on_gold_page"] / max(ev["n"], 1), 4
        )
        if args.mode != "easy"
        else None,
        "errors": sum("error" in p for p in preds),
        "uncached_calls": RETRIES["uncached"],
        **efficiency(preds),
    }
    out = ROOT / "runs" / "holdout-synth" / args.model
    out.mkdir(parents=True, exist_ok=True)
    name = args.name or args.mode
    with (out / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for p in preds:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    (out / f"{name}.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
