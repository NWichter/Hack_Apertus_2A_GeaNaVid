"""Errors of the defaults on development data only (dev_s_v11 + dev_rest_v11), by type. Stored runs, 0 calls.

Types (a row can have several): confusion (gold -> predicted), numbers/amounts in the claim, negation, time
expressions, cross-lingual, retrieval miss (no retrieved passage lies in the gold reference), confident (p >= 0.999).
python experiments/v1/error_types.py [--name final-v4]
Output: runs/v1/error-types-dev.json
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from booklint.textnorm import fold  # noqa: E402
from run import load  # noqa: E402

NAMES = {0: "E", 1: "N", 2: "C"}
NUM = re.compile(
    r"\d|\b(eins?|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|hundert|tausend|million|milliard|un|deux|trois|"
    r"quatre|cinq|dix|cent|mille|uno|due|tre|quattro|cinque|dieci|cento|mille|prozent|pour ?cent|per ?cento|franken|francs|franchi|"
    r"hälfte|moitié|metà|doppel|double|doppio|drittel|tiers|terzo|mehr|weniger|plus|moins|più|meno)\b",
    re.I,
)
NEG = re.compile(
    r"\b(nicht|kein\w*|nie|niemals|ohne|weder|ne|n'|pas|aucun\w*|jamais|sans|ni|non|nessun\w*|mai|senza|né)\b",
    re.I,
)
TIME = re.compile(
    r"\b(19|20)\d\d\b|\b(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember|janvier|"
    r"février|mars|avril|juin|juillet|août|septembre|octobre|novembre|décembre|gennaio|febbraio|marzo|aprile|maggio|giugno|"
    r"luglio|agosto|settembre|ottobre|dicembre|jahr\w*|ans?|année\w*|anni|anno|monat\w*|mois|mesi|mese|frist|délai|termine|"
    r"bis|ab|seit|dès|depuis|jusqu|entro|fino|dal|dalla)\b",
    re.I,
)


def norm(t):
    return re.sub(r"[^0-9a-z]+", "", fold(t or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="final-v4")
    args = ap.parse_args()
    out = {}
    for model in ("apertus-v1.5-8b", "apertus-v1.5-70b"):
        errors, totals = [], Counter()
        for split in ("dev_s_v11", "dev_rest_v11"):
            rows = {r["id"]: r for r in load(split)}
            preds = [
                json.loads(x)
                for x in (
                    ROOT / "runs" / "v1" / split / model / f"{args.name}.jsonl"
                ).open(encoding="utf-8")
            ]
            totals["rows"] += len(preds)
            for p in preds:
                r = rows[p["id"]]
                g, y = int(r["entailment_label"]), int(p["entailment_label"])
                totals[f"gold_{NAMES[g]}"] += 1
                if g == y:
                    continue
                claim = r["claim"]
                ref = norm(r["reference_string"])
                passages = [e.get("text", "") for e in (p.get("evidence") or [])]
                hit = p.get("recall_hit")
                if hit is None:
                    hit = (
                        any(
                            len(norm(t)) >= 20 and norm(t)[:200] in ref
                            for t in passages
                        )
                        if passages
                        else None
                    )
                tags = [f"{NAMES[g]}->{NAMES[y]}"]
                if NUM.search(claim):
                    tags.append("numbers")
                if NEG.search(claim):
                    tags.append("negation")
                if TIME.search(claim):
                    tags.append("time")
                if r["claim_language"] != r["reference_language"]:
                    tags.append("cross-lingual")
                if (p.get("confidence") or 0) >= 0.999:
                    tags.append("confident")
                if hit is False:
                    tags.append("evidence-not-in-gold")
                errors.append(
                    {
                        "id": p["id"],
                        "split": split,
                        "tags": tags,
                        "claim": claim[:200],
                        "steps": p.get("ladder_step"),
                        "confidence": p.get("confidence"),
                    }
                )
        counts = Counter(t for e in errors for t in e["tags"])
        out[model] = {
            "rows": totals["rows"],
            "errors": len(errors),
            "by_type": dict(counts.most_common()),
            "list": errors,
        }
        print(
            model,
            totals["rows"],
            "rows,",
            len(errors),
            "errors:",
            dict(counts.most_common()),
        )
    (ROOT / "runs" / "v1" / "error-types-dev.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
