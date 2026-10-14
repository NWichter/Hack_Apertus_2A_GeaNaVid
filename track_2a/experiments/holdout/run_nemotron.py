"""Second blind judge for holdout-candidates.jsonl: an NVIDIA Nemotron model on OpenRouter (open weights).

The key is read from the env file named by HOLDOUT_ENV_FILE (OPENROUTER_API_KEY), never printed.
The judge sees claim and reference_string only. Writes judge_nemotron into each row, then holdout.jsonl
(rows where generator, Codex and Nemotron agree) and holdout-dropped.jsonl.

python experiments/holdout/run_nemotron.py [--model nvidia/...]
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pdftext
from openai import OpenAI

sys.path.insert(0, str(pdftext.TRACK_ROOT / "src"))
from booklint.config import load_dotenv  # noqa: E402

DIR = pdftext.TRACK_ROOT / "data" / "holdout-synth"
LABELS = {"entailment": 0, "neutral": 1, "contradiction": 2}
PROMPT = """You are an annotator for a natural language inference (NLI) benchmark on Swiss federal voting booklets.
You get a CLAIM (German, French or Italian) and a REFERENCE (a verbatim section of the official booklet; the
language may differ from the claim). Decide, using only the REFERENCE:
- "entailment": the reference supports the claim.
- "contradiction": the reference states something incompatible with the claim (other number, actor, direction,
  recommendation, or negation).
- "neutral": the claim is on topic but the reference neither supports nor contradicts it.
Attribution phrases such as "According to the Federal Council" or "the committee thinks" refer to the speaker of
the reference section; judge the content. Do not use outside knowledge.
Answer with one JSON object only: {"label": "entailment|neutral|contradiction", "reason": "one short sentence"}"""


def pick_model(client):
    names = sorted(
        m.id for m in client.models.list().data if "nemotron" in m.id.lower()
    )
    free = [n for n in names if n.endswith(":free")]
    return (free or names)[-1]


def judge(client, model, row):
    msg = f"CLAIM: {row['claim']}\n\nREFERENCE:\n{row['reference_string']}"
    for attempt in range(6):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=2000,
                messages=[
                    {"role": "system", "content": PROMPT},
                    {"role": "user", "content": msg},
                ],
            )
            text = resp.choices[0].message.content or ""
            m = re.findall(r"\{[^{}]*\"label\"[^{}]*\}", text, re.S)
            data = json.loads(m[-1]) if m else {}
            label = str(data.get("label", "")).strip().lower()
            if label in LABELS:
                return {
                    "model": model,
                    "label": LABELS[label],
                    "label_name": label,
                    "reason": data.get("reason", ""),
                }
        except Exception as exc:  # rate limits of the free tier
            if attempt == 5:
                return {
                    "model": model,
                    "label": None,
                    "label_name": "",
                    "reason": f"error: {type(exc).__name__}",
                }
        time.sleep(5 * (attempt + 1))
    return {
        "model": model,
        "label": None,
        "label_name": "",
        "reason": "no parsable answer",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    load_dotenv(os.environ.get("HOLDOUT_ENV_FILE", str(Path(__file__).resolve().parents[2] / ".env")))
    if not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("OPENROUTER_API_KEY missing")
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=180,
    )
    model = args.model or pick_model(client)
    print("judge model:", model)
    path = DIR / "holdout-candidates.jsonl"
    rows = [
        json.loads(x)
        for x in path.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    todo = [r for r in rows if (r.get("judge_nemotron") or {}).get("label") is None]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for r, verdict in zip(todo, pool.map(lambda r: judge(client, model, r), todo)):
            r["judge_nemotron"] = verdict
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    keep, drop = [], []
    for r in rows:
        votes = [
            (r.get("judge_codex") or {}).get("label"),
            (r.get("judge_nemotron") or {}).get("label"),
        ]
        (keep if all(v == r["entailment_label"] for v in votes) else drop).append(r)
    for name, part in (("holdout.jsonl", keep), ("holdout-dropped.jsonl", drop)):
        with (DIR / name).open("w", encoding="utf-8", newline="\n") as fh:
            for r in part:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    agree = sum(
        (r["judge_nemotron"] or {}).get("label") == r["entailment_label"] for r in rows
    )
    print(f"nemotron agrees {agree}/{len(rows)}; kept {len(keep)}, dropped {len(drop)}")
    for r in drop:
        print(
            " drop",
            r["id"],
            r["label_name"],
            "codex",
            r["judge_codex"].get("label_name"),
            "nemotron",
            r["judge_nemotron"].get("label_name"),
            "|",
            r["judge_nemotron"].get("reason", "")[:120],
        )


if __name__ == "__main__":
    main()
