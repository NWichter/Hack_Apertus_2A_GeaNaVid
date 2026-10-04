"""Write the blind judge input (id, claim, reference_string only) for further judges."""

import json

import pdftext

SRC = pdftext.TRACK_ROOT / "data" / "holdout-synth" / "holdout-candidates.jsonl"
DST = pdftext.TRACK_ROOT / "data" / "holdout-synth" / "judge-cases.jsonl"

with SRC.open(encoding="utf-8") as src, DST.open("w", encoding="utf-8", newline="\n") as dst:
    for line in src:
        r = json.loads(line)
        case = {k: r[k] for k in ("id", "claim", "claim_language", "booklet_language", "reference_string")}
        dst.write(json.dumps(case, ensure_ascii=False) + "\n")
print("wrote", DST)
