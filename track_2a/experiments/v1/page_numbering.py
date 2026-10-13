"""Printed page number vs 1-based PDF index on all 60 OST v1.0 booklets (offline, no LLM calls).

A printed number is a text block of 1-3 digits in the top or bottom 10 % of the page. Output:
runs/v1/page-numbering.json (per booklet: pages, pages with a printed number, offset counts printed - index).
python experiments/v1/page_numbering.py
"""

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pymupdf  # noqa: E402

from booklint.ingest import fetch  # noqa: E402

NUM = re.compile(r"^\d{1,3}$")


def main():
    rows = [
        json.loads(line)
        for line in (ROOT / "data" / "v1" / "v1.0.jsonl").open(encoding="utf-8")
    ]
    report = []
    for url in sorted({r["booklet_url"] for r in rows}):
        doc = pymupdf.open(fetch(url))
        offsets, found = collections.Counter(), 0
        for i, page in enumerate(doc, start=1):
            h = page.rect.height
            nums = [
                int(b[4].strip())
                for b in page.get_text("blocks")
                if NUM.match(b[4].strip()) and (b[3] < 0.1 * h or b[1] > 0.9 * h)
            ]
            if nums:
                found += 1
                offsets[min(nums, key=lambda n: abs(n - i)) - i] += 1
        report.append(
            {
                "booklet": url.rsplit("/", 1)[-1],
                "url": url,
                "pages": doc.page_count,
                "with_printed_number": found,
                "offsets": {str(k): v for k, v in offsets.items()},
            }
        )
    total = {
        "booklets": len(report),
        "pages": sum(r["pages"] for r in report),
        "pages_with_printed_number": sum(r["with_printed_number"] for r in report),
        "printed_equals_pdf_index": sum(r["offsets"].get("0", 0) for r in report),
        "booklets_with_another_offset": [
            r["booklet"] for r in report if set(r["offsets"]) - {"0"}
        ],
    }
    (ROOT / "runs" / "v1" / "page-numbering.json").write_text(
        json.dumps({"total": total, "booklets": report}, indent=1) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(total, indent=1))


if __name__ == "__main__":
    main()
