"""Step 2: generate claims with Nemotron 3 Ultra (open, OpenRouter, free).

Unit = (proposal, booklet language, page). 3 claims per unit, one per label; claim languages
= booklet language + the two others (≈ 2/3 cross-lingual, like OST v1.1 with 65 %).
Output: data/generated.jsonl (one line per unit, raw + parsed). Resumable.
"""

import json
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from common import (
    DATA,
    LANGS,
    SPEC,
    clean_pages,
    openrouter,
    parse_json,
    proposal_pages,
)

MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
PROMPT_VERSION = "stress-gen-v1"
SEED = 20261014
PAGES_PER_UNIT = 2
LANG_NAME = {"de": "German", "fr": "French", "it": "Italian"}

PHENOMENA = {
    "entailment": [
        (
            "paraphrase",
            "a faithful paraphrase of one statement in the passage, using different words",
        ),
        (
            "number",
            "a number, amount, date, vote count or percentage stated in the passage, restated correctly",
        ),
        (
            "stance",
            "the position, recommendation or main argument of the speaker of the passage (Federal Council, Parliament, or the committee), as stated",
        ),
        (
            "negation",
            "a true statement phrased with a negation (e.g. 'X does not ...', 'no longer', 'not only'), true according to the passage",
        ),
        (
            "consequence",
            "a consequence or effect of the proposal that the passage states",
        ),
    ],
    "contradiction": [
        (
            "number",
            "change one number, amount, date, vote count or percentage of the passage so the claim is false",
        ),
        (
            "negation",
            "negate a statement of the passage (add or remove a negation) so the claim is false",
        ),
        (
            "actor",
            "swap the actor (who demands, decides, pays, is affected) so the claim is false according to the passage",
        ),
        (
            "direction",
            "reverse a direction stated in the passage (increase/decrease, allow/forbid, accept/reject, more/less)",
        ),
        (
            "stance",
            "attribute to the speaker of the passage the opposite position or recommendation of what the passage says",
        ),
    ],
    "neutral": [
        (
            "invented_number",
            "an invented but plausible specific number, amount or date on this topic that the booklet does not give",
        ),
        (
            "other_actor",
            "a plausible statement about the position or action of an actor (a canton, a party, the EU, an association, another country) that the booklet does not mention",
        ),
        (
            "unstated_consequence",
            "a plausible consequence, forecast or detail of the proposal that the passage does not state and that cannot be derived from it",
        ),
        (
            "related_fact",
            "a plausible related fact (history, other law, other country) that the booklet does not mention",
        ),
    ],
}

SYSTEM = """You write test items for a natural language inference (NLI) benchmark on official Swiss federal voting booklets
("Erläuterungen des Bundesrates"). Each item is a CLAIM about one proposal, checked against the booklet.
Labels: entailment = the passage supports the claim; contradiction = the passage states something incompatible
with the claim; neutral = the claim is on topic and plausible, but the booklet neither supports nor contradicts it.
Style (as in the official benchmark): one sentence, 15-45 words, often starting with the source of the statement,
matching the passage, e.g. "Der Bundesrat ist der Ansicht, dass ...", "Das Komitee argumentiert, dass ...",
"Laut der Zusammenfassung ...", "Laut dem Abstimmungstext ...", "Wird die Vorlage angenommen, ...",
"Le Conseil fédéral estime que ...", "Le comité affirme que ...", "Selon le résumé ...", "Si le projet est accepté, ...",
"Il Consiglio federale ritiene che ...", "Il comitato sostiene che ...", "Secondo il riassunto ...", "Se il progetto viene accettato, ...".
Use the attribution that fits the passage: arguments of a committee belong to the committee, arguments of the
Federal Council to the Federal Council; neutral explanatory text is "the summary"/"the explanations"; legal text is
"the voting text". Never use outside knowledge to decide the label; only the passage counts.
Rules:
- The claim must be in the requested language (German, French or Italian), natural and grammatical.
- For entailment and contradiction, "evidence" is ONE or TWO consecutive sentences copied EXACTLY, character by
  character, from the PASSAGE (in the passage's language, do not translate, do not fix typos or hyphens).
  The evidence must be the sentence that decides the label.
- For neutral, "evidence" is "" and the claim must not be decidable from the passage nor from anything a booklet
  about this proposal would normally say. Do not make it trivially off topic.
- A contradiction must be clearly false given the evidence, not merely unsupported.
- No claim may be a near copy of the evidence; rephrase.
Return JSON only: {"items": [{"slot": 1, "label": "...", "claim_language": "de|fr|it", "claim": "...",
"evidence": "...", "phenomenon": "...", "why": "one short sentence"}, ...]}"""


def units():
    rnd = random.Random(SEED)
    out = []
    for date, key, rng, titles in SPEC:
        for lang in LANGS:
            pages = [
                p
                for p in proposal_pages(date, rng, lang)
                if len(clean_pages(date, lang)[p - 1]) >= 900
            ]
            pick = sorted(rnd.sample(pages, min(PAGES_PER_UNIT, len(pages))))
            for page in pick:
                labels = ["entailment", "neutral", "contradiction"]
                rnd.shuffle(labels)
                others = [x for x in LANGS if x != lang]
                rnd.shuffle(others)
                claim_langs = [lang] + others
                slots = []
                for i, (lab, cl) in enumerate(zip(labels, claim_langs), 1):
                    ph = rnd.choice(PHENOMENA[lab])
                    slots.append(
                        {
                            "slot": i,
                            "label": lab,
                            "claim_language": cl,
                            "phenomenon": ph[0],
                            "how": ph[1],
                        }
                    )
                out.append(
                    {
                        "unit": f"{key}-{lang}-p{page}",
                        "date": date,
                        "key": key,
                        "booklet_language": lang,
                        "page": page,
                        "vote": titles[lang],
                        "slots": slots,
                    }
                )
    return out


def neutral_units():
    """Extra units for neutral only (the judges reject many generated neutral items): per proposal and language
    one more page with two neutral slots (same language + one other)."""
    used = {(u["key"], u["booklet_language"], u["page"]) for u in units()}
    rnd = random.Random(SEED + 1)
    out = []
    for date, key, rng, titles in SPEC:
        for lang in LANGS:
            pages = [p for p in proposal_pages(date, rng, lang) if len(clean_pages(date, lang)[p - 1]) >= 900]
            fresh = [p for p in pages if (key, lang, p) not in used] or pages
            page = rnd.choice(fresh)
            other = rnd.choice([x for x in LANGS if x != lang])
            slots = []
            for i, cl in enumerate([lang, other], 1):
                ph = rnd.choice(PHENOMENA["neutral"])
                slots.append({"slot": i, "label": "neutral", "claim_language": cl, "phenomenon": ph[0], "how": ph[1]})
            out.append({"unit": f"{key}-{lang}-p{page}-nx", "date": date, "key": key, "booklet_language": lang,
                        "page": page, "vote": titles[lang], "slots": slots})
    return out


def user_msg(u):
    passage = clean_pages(u["date"], u["booklet_language"])[u["page"] - 1]
    lines = [
        f'Proposal ("vote"): {u["vote"]}',
        f"Booklet: federal vote of {u['date']}, {LANG_NAME[u['booklet_language']]} edition.",
        f"PASSAGE (PDF page {u['page']}):",
        '"""',
        passage,
        '"""',
        "",
        "Write exactly these items:",
    ]
    for s in u["slots"]:
        lines.append(
            f"- slot {s['slot']}: label {s['label']}, claim in {LANG_NAME[s['claim_language']]} ({s['claim_language']}), "
            f'phenomenon "{s["phenomenon"]}": {s["how"]}.'
        )
    return "\n".join(lines)


def main():
    DATA.mkdir(exist_ok=True)
    out_path = DATA / ("generated_neutral.jsonl" if "neutral" in sys.argv else "generated.jsonl")
    done = set()
    if out_path.exists():
        for line in out_path.open(encoding="utf-8"):
            r = json.loads(line)
            if r.get("items"):
                done.add(r["unit"])
    args = [a for a in sys.argv[1:] if a != "neutral"]
    pool_units = neutral_units() if "neutral" in sys.argv else units()
    todo = [u for u in pool_units if u["unit"] not in done]
    limit = int(args[0]) if args else len(todo)
    todo = todo[:limit]
    print(f"{len(done)} done, {len(todo)} to do", flush=True)
    lock = threading.Lock()

    def one(u):
        msgs = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg(u)},
        ]
        rec = dict(
            u,
            generator="openrouter",
            generator_model=MODEL,
            prompt_version=PROMPT_VERSION,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        try:
            resp = openrouter(MODEL, msgs, max_tokens=6000, temperature=0.7)
            text = resp["choices"][0]["message"].get("content") or ""
            rec["raw"] = text
            rec["usage"] = resp.get("usage")
            rec["served_model"] = resp.get("model")
            rec["items"] = parse_json(text)["items"]
        except Exception as exc:  # noqa: BLE001
            rec["error"] = repr(exc)[:300]
        with lock:
            with out_path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(
                rec["unit"], "ok" if rec.get("items") else rec.get("error"), flush=True
            )

    with ThreadPoolExecutor(max_workers=2 if "neutral" in sys.argv else 4) as pool:
        list(pool.map(one, todo))


if __name__ == "__main__":
    main()
