"""Step 4: select clean items, separate disputed ones, write OST inputs and freeze everything (SHA-256).

clean    = text checks passed (evidence quote verbatim in the PDF) AND generator label = Gemma = Qwen
disputed = text checks passed, but at least one judge disagrees (or did not answer)
Outputs in data/: clean.jsonl, disputed.jsonl, cases_A.jsonl (booklet), cases_B.jsonl (reference), MANIFEST.json
"""

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from common import BOOKLETS, DATA

JUDGE_FILES = {"gemma": "judge_gemma.jsonl", "qwen": "judge_qwen.jsonl"}


def load_judge(name):
    out = {}
    for line in (DATA / JUDGE_FILES[name]).open(encoding="utf-8"):
        j = json.loads(line)
        if j.get("label"):
            out[j["id"]] = j
    return out


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    cands = [json.loads(x) for x in (DATA / "candidates.jsonl").open(encoding="utf-8")]
    judges = {n: load_judge(n) for n in JUDGE_FILES}
    clean, disputed = [], []
    for r in cands:
        if r["checks"]:
            continue
        jl = {n: (judges[n].get(r["id"]) or {}) for n in judges}
        r = dict(r)
        r["judges"] = {
            n: {
                "model": j.get("model"),
                "label": j.get("label"),
                "page": j.get("page"),
                "quote": j.get("quote"),
                "reason": j.get("reason"),
            }
            for n, j in jl.items()
        }
        if all(j.get("label") == r["label_name"] for j in jl.values()):
            clean.append(r)
        else:
            disputed.append(r)
    write(DATA / "clean.jsonl", clean)
    write(DATA / "disputed.jsonl", disputed)
    cases_a, cases_b = [], []
    for r in clean:
        claim = {"text": r["claim"], "language": r["claim_language"]}
        cases_a.append(
            {
                "id": r["id"] + "-A",
                "vote": r["vote"],
                "claim": claim,
                "booklet": {
                    "path": r["booklet_path"],
                    "language": r["booklet_language"],
                },
            }
        )
        cases_b.append(
            {
                "id": r["id"] + "-B",
                "claim": claim,
                "reference": {
                    "text": r["reference_string"],
                    "language": r["booklet_language"],
                },
            }
        )
    write(DATA / "cases_A.jsonl", cases_a)
    write(DATA / "cases_B.jsonl", cases_b)
    files = [
        "generated.jsonl",
        "generated_neutral.jsonl",
        "candidates.jsonl",
        "judge_gemma.jsonl",
        "judge_qwen.jsonl",
        "clean.jsonl",
        "disputed.jsonl",
        "cases_A.jsonl",
        "cases_B.jsonl",
        "download.log",
    ]
    manifest = {
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Eingefroren, bevor booklint/Apertus auf diesen Daten lief. Synthetisch, nicht OST.",
        "counts": {
            "candidates": len(cands),
            "passed_text_checks": sum(1 for r in cands if not r["checks"]),
            "clean": len(clean),
            "disputed": len(disputed),
            "clean_labels": dict(Counter(r["label_name"] for r in clean)),
            "clean_same_language": sum(
                r["claim_language"] == r["booklet_language"] for r in clean
            ),
            "clean_by_date": dict(
                sorted(Counter(r["booklet_date"] for r in clean).items())
            ),
            "clean_by_booklet_language": dict(
                Counter(r["booklet_language"] for r in clean)
            ),
            "clean_by_claim_language": dict(
                Counter(r["claim_language"] for r in clean)
            ),
        },
        "files": {
            f: {"sha256": sha(DATA / f), "bytes": (DATA / f).stat().st_size}
            for f in files
        },
        "booklets": {p.name: sha(p) for p in sorted(BOOKLETS.glob("*.pdf"))},
    }
    (DATA / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
