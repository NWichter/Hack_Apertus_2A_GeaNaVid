"""Cases in OST's evaluation format (starter repo prepare_cases.py, 2026-10-06) from one of our splits.

Writes <out>/cases.jsonl (task A with booklet.path relative to /data, task B with reference.text),
<out>/expected-labels.jsonl (for OST's evaluate.py only, never for the predictor) and <out>/booklets/<date>_<lang>.pdf
copied from the local PDF cache. Rows are a seeded sample, the same for every run.
python experiments/v1/ost_cases.py --split test_v11 --rows 40 --out /tmp/ost-cases
"""

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from booklint.ingest import fetch  # noqa: E402
from run import load  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test_v11")
    ap.add_argument("--rows", type=int, default=40)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rows = load(args.split)
    rows = random.Random(args.seed).sample(rows, min(args.rows, len(rows)))
    out = Path(args.out)
    (out / "booklets").mkdir(parents=True, exist_ok=True)
    cases, expected = [], []
    for r in rows:
        name = (
            r["booklet_publish_date"].replace("-", "_")
            + "_"
            + r["reference_language"]
            + ".pdf"
        )
        target = out / "booklets" / name
        if not target.is_file():
            shutil.copyfile(fetch(r["booklet_url"]), target)
        for task in ("A", "B"):
            case = {
                "id": f"{r['id']}-{task}",
                "vote": r["vote"],
                "claim": {"text": r["claim"], "language": r["claim_language"]},
            }
            if task == "A":
                case["booklet"] = {
                    "path": f"booklets/{name}",
                    "language": r["reference_language"],
                }
            else:
                case["reference"] = {
                    "text": r["reference_string"],
                    "language": r["reference_language"],
                }
            cases.append(case)
            gold = {"id": case["id"], "label": r["entailment_label"]}
            if r["entailment_label"] != 1:
                gold["reference"] = r["reference_string"]
            expected.append(gold)
    for fname, items in (("cases.jsonl", cases), ("expected-labels.jsonl", expected)):
        with (out / fname).open("w", encoding="utf-8", newline="\n") as fh:
            for item in items:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"{len(cases)} cases from {len(rows)} rows of {args.split} in {out}")


if __name__ == "__main__":
    main()
