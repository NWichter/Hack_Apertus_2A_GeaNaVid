"""Assemble holdout-candidates.jsonl from spec.py and the downloaded booklets.

Keeps judge fields of an existing candidates file, so re-running the build
after a judge pass does not lose them.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pdftext
import spec

OUT = pdftext.TRACK_ROOT / "data" / "holdout-synth" / "holdout-candidates.jsonl"
GENERATOR_MODEL = "claude-opus-5-5"
PROMPT_VERSION = "holdout-v1"
LABEL_NAMES = {0: "entailment", 1: "neutral", 2: "contradiction"}


def booklet_path(date: str, lang: str) -> str:
    return f"data/holdout-synth/booklets/{date}_{lang}.pdf"


def cut(text: str, start: str, end: str, where: str) -> str:
    i = text.find(start)
    if i < 0:
        sys.exit(f"{where}: start anchor not found: {start!r}")
    j = text.find(end, i + len(start) if end != start else i)
    if j < 0:
        sys.exit(f"{where}: end anchor not found: {end!r}")
    return text[i : j + len(end)].strip()


def section_text(key: str) -> tuple[str, str, str]:
    vote, lang, parts = spec.SECTIONS[key]
    date = spec.VOTE_DATE[vote]
    pages = pdftext.clean_pages(booklet_path(date, lang))
    chunks = [cut(pages[p - 1], s, e, f"{key} p{p}") for p, s, e in parts]
    # one line per page part; verify.py checks each line against the PDF
    body = "\n".join(chunks)
    title = spec.VOTES[(vote, lang)]
    return date, lang, f"{title}\n\n\n{body}"


def main() -> None:
    old = {}
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            old[r["id"]] = r
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = []
    for rid, sec, label, claim_lang, claim, evidence in spec.ROWS:
        date, lang, ref = section_text(sec)
        vote_key = spec.SECTIONS[sec][0]
        prev = old.get(rid, {})
        row = {
            "id": rid,
            "claim": claim,
            "claim_language": claim_lang,
            "booklet_language": lang,
            "booklet_date": date,
            "booklet_path": booklet_path(date, lang),
            "booklet_url": spec.booklet_url(date, lang),
            "vote": spec.VOTES[(vote_key, lang)],
            "entailment_label": label,
            "label_name": LABEL_NAMES[label],
            "reference_string": ref,
            "evidence": [{"page": p, "text": t} for p, t in evidence],
            "provenance": prev.get("provenance")
            or {
                "generator": "claude",
                "generator_model": GENERATOR_MODEL,
                "generated_at": now,
                "prompt_version": PROMPT_VERSION,
            },
        }
        for k, v in prev.items():
            if k.startswith("judge_"):
                row[k] = v
        rows.append(row)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
