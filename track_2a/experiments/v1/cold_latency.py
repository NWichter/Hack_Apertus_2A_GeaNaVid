"""Cold latency and tokens of two or more configurations, interleaved case by case so they share endpoint conditions.

50 seeded rows of a split (default dev_rest_v11, never used for tuning), OST input format, no response cache, one
request at a time, booklets parsed beforehand. For every case each configuration runs right after the other.
python experiments/v1/cold_latency.py --name cold-1014 --configs '[["8b-old","apertus-v1.5-8b",{}], ...]'
Output: runs/v1/<split>/<name>.json
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from booklint.cli import check_case, normalize_case  # noqa: E402
from booklint.config import Settings  # noqa: E402
from booklint.llm import LLM  # noqa: E402
from booklint.metrics import macro_f1, percentile  # noqa: E402
from booklint.pipeline import Options, Pipeline  # noqa: E402
from run import load  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev_rest_v11")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--name", required=True)
    ap.add_argument(
        "--configs", required=True, help="JSON list of [label, model, options]"
    )
    args = ap.parse_args()
    rows = load(args.split)
    rows = [
        rows[i]
        for i in sorted(random.Random(args.seed).sample(range(len(rows)), args.n))
    ]
    cases = [
        normalize_case(
            {
                "id": r["id"],
                "booklet": {"path": r["booklet_url"]},
                "vote": r["vote"],
                "claim": {"text": r["claim"]},
            }
        )
        for r in rows
    ]
    configs = json.loads(args.configs)
    pipes = {}
    for label, model, opts in configs:
        pipes[label] = Pipeline(
            LLM(Settings.from_env(model), use_cache=False), Options(**opts)
        )
        for c in cases:
            pipes[label].booklet(c["booklet"])
    out = {label: [] for label, _, _ in configs}
    for c in cases:
        for label, _, _ in configs:
            t0 = time.perf_counter()
            try:
                p = check_case(pipes[label], c)
            except Exception as exc:  # noqa: BLE001
                p = {
                    "label": 1,
                    "error": repr(exc)[:200],
                    "metrics": {"input_tokens": 0, "output_tokens": 0},
                }
            ms = (time.perf_counter() - t0) * 1000
            out[label].append(
                {
                    "id": c["id"],
                    "label": p["label"],
                    "ms": round(ms),
                    "input_tokens": p["metrics"]["input_tokens"],
                    "output_tokens": p["metrics"]["output_tokens"],
                    "error": p.get("error"),
                }
            )
    gold = {r["id"]: int(r["entailment_label"]) for r in rows}
    report = {
        "split": args.split,
        "n": len(rows),
        "seed": args.seed,
        "configs": configs,
        "results": {},
    }
    for label, preds in out.items():
        ms = [p["ms"] for p in preds]
        report["results"][label] = {
            "macro_f1": round(
                macro_f1([gold[p["id"]] for p in preds], [p["label"] for p in preds])[
                    0
                ],
                4,
            ),
            "errors": sum(bool(p["error"]) for p in preds),
            "input_tokens_mean": round(
                sum(p["input_tokens"] for p in preds) / len(preds), 1
            ),
            "output_tokens_mean": round(
                sum(p["output_tokens"] for p in preds) / len(preds), 1
            ),
            "ms_mean": round(sum(ms) / len(ms)),
            "ms_p95": percentile(ms, 0.95),
            "cases": preds,
        }
        r = report["results"][label]
        print(
            label,
            {
                k: r[k]
                for k in (
                    "macro_f1",
                    "errors",
                    "input_tokens_mean",
                    "output_tokens_mean",
                    "ms_mean",
                    "ms_p95",
                )
            },
            flush=True,
        )
    target = ROOT / "runs" / "v1" / args.split / f"{args.name}.json"
    target.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
