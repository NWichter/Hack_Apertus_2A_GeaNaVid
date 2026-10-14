"""Report tables on test v1.1 (493 rows) from the stored test predictions, 0 calls.

Rows of the main table and the language table of technical_report.md; labels and tokens of a run cannot change
when the 4 rows OST removed are dropped. Output: runs/v1/test/report-tables-v11.json
python experiments/v1/report_tables_v11.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from booklint.metrics import macro_f1  # noqa: E402
from run import load  # noqa: E402

MAIN = [
    ("Baseline: whole booklet", "baseline", "baseline"),
    ("Beginner: gold section", "easy", "easy"),
    ("Beginner + 3 examples (8B)", "easy-fs3", None),
    ("Adv.: BM25, whole booklet", "ret-booklet", None),
    ("Adv.: proposal + BM25", "ret-vote", "ret-vote"),
    ("Adv.: + translation", "ret-vote-tr", "ret-vote-tr"),
    ("Adv.: + 3 ex. + decomp.", "default", None),
    ("Adv.: + sections", "r1-secboost", "r1-secboost"),
    ("Adv.: + neutral re-check", "final-v2", "r9-recheck-terms"),
    ("Default (14 Oct.): 8B re-check if p < 0.999, 70B compact headers", "final-v4", "final-v4"),
]
LANG = {"Adv.": "final-v4", "Beg.": "beginner-default"}
SPLIT_DIR = {"final-v4": "test_v11"}  # runs made on v1.1 directly


def preds(model, name):
    path = ROOT / "runs" / "v1" / SPLIT_DIR.get(name, "test") / model / f"{name}.jsonl"
    return {p["id"]: p for p in map(json.loads, path.open(encoding="utf-8"))}


def f1(rows, pred):
    return round(
        macro_f1(
            [int(r["entailment_label"]) for r in rows],
            [int(pred[r["id"]]["entailment_label"]) for r in rows],
        )[0],
        4,
    )


def tokens(rows, pred):
    return round(sum(pred[r["id"]]["usage"]["prompt_tokens"] for r in rows) / len(rows))


def main():
    rows = load("test_v11")
    out = {"rows": len(rows), "main": [], "languages": {}}
    for label, n8, n70 in MAIN:
        entry = {"setup": label}
        for model, name in (("8b", n8), ("70b", n70)):
            if name:
                p = preds(f"apertus-v1.5-{model}", name)
                entry[model] = {
                    "run": name,
                    "macro_f1": f1(rows, p),
                    "input_tokens": tokens(rows, p),
                }
        out["main"].append(entry)
    groups = {
        "All": lambda r: True,
        "Same lang.": lambda r: r["claim_language"] == r["reference_language"],
        "Cross-ling.": lambda r: r["claim_language"] != r["reference_language"],
    }
    for lang in ("de", "fr", "it"):
        groups[f"Claim {lang.upper()}"] = (
            lambda r, lang=lang: r["claim_language"] == lang
        )
        groups[f"Booklet {lang.upper()}"] = (
            lambda r, lang=lang: r["reference_language"] == lang
        )
    for g, keep in groups.items():
        sub = [r for r in rows if keep(r)]
        out["languages"][g] = {"n": len(sub)}
        for task, name in LANG.items():
            for model in ("8b", "70b"):
                out["languages"][g][f"{task} {model}"] = f1(
                    sub, preds(f"apertus-v1.5-{model}", name)
                )
    (ROOT / "runs" / "v1" / "test" / "report-tables-v11.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    for e in out["main"]:
        print(e)
    for g, v in out["languages"].items():
        print(g, v)


if __name__ == "__main__":
    main()
