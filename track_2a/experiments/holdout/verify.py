"""Check holdout-candidates.jsonl against the booklet PDFs and the target counts."""

import json
import sys
from collections import Counter

import pdftext

PATH = pdftext.TRACK_ROOT / "data" / "holdout-synth" / "holdout-candidates.jsonl"


def main() -> int:
    rows = [json.loads(l) for l in PATH.read_text(encoding="utf-8").splitlines()]
    errors = []
    for r in rows:
        rid, path = r["id"], r["booklet_path"]
        doc = pdftext.loose_doc(path)
        pages = pdftext.loose_pages(path)
        title, _, body = r["reference_string"].partition("\n\n\n")
        if pdftext.loose(title) not in doc:
            errors.append(f"{rid}: vote title not in PDF")
        for part in body.split("\n"):
            lp = pdftext.loose(part)
            if lp not in doc and lp not in pdftext.loose_doc_no_folios(path):
                errors.append(f"{rid}: reference part not in PDF: {part[:60]!r}")
        if r["label_name"] == "neutral":
            if r["evidence"]:
                errors.append(f"{rid}: neutral row has evidence")
        elif not r["evidence"]:
            errors.append(f"{rid}: evidence missing")
        for ev in r["evidence"]:
            t = pdftext.loose(ev["text"])
            if t not in pages[ev["page"] - 1]:
                hits = [i + 1 for i, p in enumerate(pages) if t in p]
                errors.append(f"{rid}: evidence not on page {ev['page']} (found on {hits}): {ev['text'][:60]!r}")
            if t not in pdftext.loose(r["reference_string"]):
                errors.append(f"{rid}: evidence outside reference_string: {ev['text'][:60]!r}")
    n = len(rows)
    print(f"rows: {n}, ids unique: {len({r['id'] for r in rows}) == n}")
    print("labels:", dict(Counter(r["label_name"] for r in rows)))
    print("booklet languages:", dict(Counter(r["booklet_language"] for r in rows)))
    print("claim languages:", dict(Counter(r["claim_language"] for r in rows)))
    pairs = Counter(f"{r['claim_language']}->{r['booklet_language']}" for r in rows)
    print("claim->booklet pairs:", dict(sorted(pairs.items())))
    same = sum(r["claim_language"] == r["booklet_language"] for r in rows)
    print(f"same language: {same}, cross: {n - same}")
    print("per vote:", dict(Counter(r["vote"][:40] for r in rows)))
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
