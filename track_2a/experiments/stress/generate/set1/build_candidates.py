"""Step 2b: build candidates from generated.jsonl and check evidence quotes verbatim against the PDF.

Output: data/candidates.jsonl (all items, field `checks`), counts on stdout.
"""

import json
from collections import Counter

from common import (
    DATA,
    LABELS,
    LANGS,
    SPEC,
    clean_pages,
    find_quote,
    proposal_pages,
    verbatim_on_page,
)

URLS = {}
for line in (DATA / "download.log").read_text(encoding="utf-8").splitlines():
    d, lang, code, ctype, url = line.split(" ", 4)
    URLS[(d, lang)] = url
RANGES = {key: rng for _, key, rng, _ in SPEC}


def main():
    rows, stats = [], Counter()
    n = 0
    lines = (DATA / "generated.jsonl").read_text(encoding="utf-8").splitlines()
    if (DATA / "generated_neutral.jsonl").exists():
        lines += (DATA / "generated_neutral.jsonl").read_text(encoding="utf-8").splitlines()
    for line in lines:
        u = json.loads(line)
        if not u.get("items"):
            stats["unit_failed"] += 1
            continue
        slots = {s["slot"]: s for s in u["slots"]}
        for it in u["items"]:
            n += 1
            slot = slots.get(it.get("slot"), {})
            label = (it.get("label") or "").strip().lower()
            checks = []
            if label not in LABELS:
                checks.append("bad_label")
            if slot and label != slot["label"]:
                checks.append("label_not_requested")
            cl = (it.get("claim_language") or "").strip().lower()
            if cl not in LANGS or (slot and cl != slot["claim_language"]):
                checks.append("claim_language_not_requested")
            claim = (it.get("claim") or "").strip()
            if len(claim) < 25:
                checks.append("claim_too_short")
            ev = (it.get("evidence") or "").strip()
            date, lang, page = u["date"], u["booklet_language"], u["page"]
            evidence = []
            if label in ("entailment", "contradiction"):
                if verbatim_on_page(ev, date, lang, page):
                    evidence = [{"page": page, "text": ev}]
                else:
                    other = find_quote(
                        ev, date, lang, proposal_pages(date, RANGES[u["key"]], lang)
                    )
                    if other:
                        evidence = [{"page": other, "text": ev}]
                        checks.append("evidence_on_other_page")
                    else:
                        checks.append("evidence_not_verbatim")
            elif label == "neutral" and ev:
                checks.append("neutral_with_evidence")
            gold_page = evidence[0]["page"] if evidence else page
            row = {
                "id": f"st-{u['unit']}-s{it.get('slot')}",
                "claim": claim,
                "claim_language": cl,
                "booklet_language": lang,
                "booklet_date": date,
                "booklet_path": f"{date}_{lang}.pdf",
                "booklet_url": URLS[(date, lang)],
                "vote": u["vote"],
                "proposal_key": u["key"],
                "entailment_label": LABELS.get(label, -1),
                "label_name": label,
                "reference_string": u["vote"]
                + "\n\n\n"
                + clean_pages(date, lang)[gold_page - 1],
                "reference_page": gold_page,
                "evidence": evidence,
                "phenomenon": it.get("phenomenon") or slot.get("phenomenon"),
                "requested_phenomenon": slot.get("phenomenon"),
                "generator_reason": it.get("why"),
                "checks": checks,
                "provenance": {
                    "generator": "openrouter",
                    "generator_model": u["generator_model"],
                    "served_model": u.get("served_model"),
                    "generated_at": u["generated_at"],
                    "prompt_version": u["prompt_version"],
                    "unit": u["unit"],
                    "source_page": page,
                },
            }
            rows.append(row)
            stats["items"] += 1
            for c in checks:
                stats[c] += 1
            if not checks:
                stats["passed_text_checks"] += 1
    with (DATA / "candidates.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(dict(stats))
    ok = [r for r in rows if not r["checks"]]
    print("labels ok:", Counter(r["label_name"] for r in ok))


if __name__ == "__main__":
    main()
