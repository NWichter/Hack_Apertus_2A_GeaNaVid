"""Readable proposal titles for the demo: data/v1/vote-titles.json maps each `vote` string of OST v1.0 to the title as
printed in its booklet.

The `vote` field of OST v1.0 carries lost characters (U+FFFD for "ü", "é", "à", "«", the apostrophe, ...) and words split
by the PDF layout ("Kampf flugzeuge", "popolar e"). Each title is matched against the text of its own booklet: a lost
character matches any single character, and a space inside a word may be absent in the booklet (or be a line-end
hyphen). The matched booklet text, with whitespace collapsed, becomes the readable title; titles without a match keep
their form with only the lost characters dropped. The CLI does not use this file: it locates proposals with the
original `vote` string, so OST results do not depend on it. No model calls.

python experiments/v1/vote_titles.py
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint.ingest import page_texts  # noqa: E402

LOST = "�"


def pattern(title):
    parts = []
    for ch in unicodedata.normalize("NFC", title.strip()):
        if ch == LOST:
            parts.append(r"[^\s]{1,2}")
        elif ch.isspace():
            parts.append(r"[\s­\-]*")
        else:
            parts.append(re.escape(ch))
    return re.compile("".join(parts))


def tidy(text):
    text = unicodedata.normalize("NFC", text).replace("­", "")
    # a line-end hyphen inside a word, but not a suspended compound ("Energie- und Klimapolitik")
    text = re.sub(
        r"(?<=[a-zäöüéèàìòù])-\s+(?!(?:und|oder|bzw|et|ou|e|o)\b)(?=[a-zäöüéèàìòù])",
        "",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def repair(title, booklet_text):
    m = pattern(title).search(booklet_text)
    if m:
        return tidy(m.group(0)), True
    return re.sub(r"\s+", " ", title.replace(LOST, "")).strip(), False


def main():
    rows = [json.loads(x) for x in (ROOT / "data/v1/v1.0.jsonl").open(encoding="utf-8")]
    # in v1.0 the vote title may be in another language than the row's booklet: search all booklets of that date
    urls, votes_by_date = {}, {}
    for r in rows:
        d = r["booklet_publish_date"]
        urls.setdefault(d, set()).add(r["booklet_url"])
        votes_by_date.setdefault(d, set()).add(r["vote"].strip())
    out, found, total = {}, 0, 0
    for d, votes in sorted(votes_by_date.items()):
        text = "\n".join("\n".join(page_texts(u)) for u in sorted(urls[d]))
        for v in sorted(votes):
            if v in out:
                continue
            total += 1
            fixed, ok = repair(v, text)
            found += ok
            out[v] = fixed
    path = ROOT / "data/v1/vote-titles.json"
    path.write_text(
        json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    left = [v for v in out.values() if LOST in v]
    print(
        f"{total} titles, {found} matched in their booklet, {len(left)} still with lost characters -> {path}"
    )


if __name__ == "__main__":
    main()
