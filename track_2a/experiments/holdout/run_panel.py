"""Blind panel of open-weight judges for holdout-candidates.jsonl (OpenRouter): GLM-5.3, DeepSeek V3.2, Qwen3-235B.

Each judge sees claim and reference_string only (same prompt as run_nemotron.py), never the generator's label.
Writes judge_glm, judge_deepseek and judge_qwen into each row, then holdout.jsonl and holdout-dropped.jsonl:
a row is kept if the generator's label equals the Nemotron verdict and the majority (at least 2 of 3) of the panel.
The key comes from OPENROUTER_API_KEY (environment or the env file in HOLDOUT_ENV_FILE, default track_2a/.env),
never printed. A budget guard stops new calls once the key's usage has grown by --budget USD.

python experiments/holdout/run_panel.py [--budget 0.9]
"""

import argparse
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pdftext
from openai import OpenAI
from run_nemotron import DIR, LABELS, PROMPT, judge

sys.path.insert(0, str(pdftext.TRACK_ROOT / "src"))
from booklint.config import load_dotenv  # noqa: E402

PANEL = {
    "judge_glm": "z-ai/glm-5.3",
    "judge_deepseek": "deepseek/deepseek-v3.2",
    "judge_qwen": "qwen/qwen3-235b-a22b-2507",
}


def usage(key):
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())["data"]["usage"]


def keep_row(r):
    panel = [(r.get(k) or {}).get("label") for k in PANEL]
    majority = sum(v == r["entailment_label"] for v in panel) >= 2
    return (
        majority
        and (r.get("judge_nemotron") or {}).get("label") == r["entailment_label"]
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=0.9)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    load_dotenv(
        os.environ.get(
            "HOLDOUT_ENV_FILE", str(Path(__file__).resolve().parents[2] / ".env")
        )
    )
    key = os.environ.get("OPENROUTER_API_KEY") or sys.exit("OPENROUTER_API_KEY missing")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key, timeout=180)
    start = usage(key)
    path = DIR / "holdout-candidates.jsonl"
    rows = [
        json.loads(x)
        for x in path.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    for field, model in PANEL.items():
        spent = usage(key) - start
        if spent > args.budget:
            sys.exit(f"budget stop before {model}: {spent:.4f} USD spent")
        todo = [r for r in rows if (r.get(field) or {}).get("label") is None]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for r, verdict in zip(
                todo, pool.map(lambda r: judge(client, model, r), todo)
            ):
                r[field] = verdict
        agree = sum(
            (r.get(field) or {}).get("label") == r["entailment_label"] for r in rows
        )
        print(f"{model}: agrees with the generator on {agree}/{len(rows)}")
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    keep = [r for r in rows if keep_row(r)]
    drop = [r for r in rows if not keep_row(r)]
    for name, part in (("holdout.jsonl", keep), ("holdout-dropped.jsonl", drop)):
        with (DIR / name).open("w", encoding="utf-8", newline="\n") as fh:
            for r in part:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"kept {len(keep)}, dropped {len(drop)}; cost {usage(key) - start:.4f} USD")
    for r in drop:
        votes = " ".join(
            f"{k[6:]}={(r.get(k) or {}).get('label_name')}"
            for k in ("judge_nemotron", *PANEL)
        )
        print(" drop", r["id"], r["label_name"], "|", votes)


if __name__ == "__main__":
    main()
