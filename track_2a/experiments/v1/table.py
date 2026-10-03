"""Collect runs/v1/<split>/<model>/*.summary.json into a Markdown table (stdout)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLS = [("macro_f1", "F1"), ("ci95", "95% CI"), ("f1_e", "F1 E"), ("f1_n", "F1 N"), ("f1_c", "F1 C"),
        ("macro_f1_same", "F1 same"), ("macro_f1_cross", "F1 cross"), ("recall_hit", "hit@k"),
        ("tokens_mean", "tokens/claim"), ("llm_calls_mean", "calls/claim"), ("llm_seconds_mean", "s/claim (LLM)"),
        ("errors", "errors")]


def fmt(v):
    if isinstance(v, float):
        return f"{v:.3f}" if v < 10 else f"{v:,.0f}"
    if isinstance(v, list):
        return "–".join(f"{x:.3f}" for x in v)
    return "" if v is None else str(v)


def main(split, names=None):
    rows = []
    for model_dir in sorted((ROOT / "runs" / "v1" / split).iterdir()):
        if not model_dir.is_dir():
            continue
        for f in sorted(model_dir.glob("*.summary.json")):
            s = json.loads(f.read_text(encoding="utf-8"))
            if names and s["name"] not in names:
                continue
            rows.append(s)
    if names:
        rows.sort(key=lambda s: (names.index(s["name"]), s["model"]))
    print("| model | run | n | " + " | ".join(c[1] for c in COLS) + " |")
    print("|---|---|---|" + "---|" * len(COLS))
    for s in rows:
        model = s["model"].replace("apertus-v1.5-", "")
        print(f"| {model} | {s['name']} | {s['n']} | " + " | ".join(fmt(s.get(c[0])) for c in COLS) + " |")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2].split(",") if len(sys.argv) > 2 else None)
