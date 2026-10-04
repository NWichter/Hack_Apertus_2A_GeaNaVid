"""Section type of every chunk and the section a claim points to ("the summary says", "the committee argues").
Keyword rules on headings and page notes, DE/FR/IT. No LLM calls."""

import re

_HEAD = [
    (
        "legal",
        r"abstimmungstext|texte soumis|testo in votazione|testo sottoposto|^bundesbeschluss|^arrêté fédéral|^decreto federale",
    ),
    ("committee", r"komitee|comité|comitato|initiativkomitee|referendumskomitee"),
    (
        "authorities",
        r"argumente (von )?bundesrat|arguments (du )?conseil fédéral|argomenti (del )?consiglio federale|^argumente$|^arguments$|^argomenti$|^gli argomenti$|^les arguments$|^die argumente$",
    ),
    ("debate", r"debatte|débat|dibattito|beratung im parlament|délibérations"),
    (
        "recommendation",
        r"empfehlung|recommandation|raccomandazione|abstimmungsfrage|la question qui vous est posée|domanda|position der minderheit|position de la minorité|posizione della minoranza|abstimmung im (national|stände)rat|vote du conseil|voto del consiglio|votazione nel consiglio",
    ),
    (
        "overview",
        r"in kürze|en bref|in breve|das wichtigste|l'essentiel|l'essenziale|übersicht|aperçu|panoramica",
    ),
    (
        "context",
        r"ausgangslage|contexte|contesto|im detail|en détail|in dettaglio|situation initiale|situazione iniziale|die vorlage|le projet|il progetto|was will die|que veut|che cosa chiede",
    ),
]
_HEAD = [(name, re.compile(p, re.I)) for name, p in _HEAD]
_COMMITTEE_NOTE = re.compile(r"komitee|comité|comitato|initiant|referendum", re.I)

_CUES = [
    (
        "summary",
        re.compile(
            r"zusammenfassung|in kürze|kurzfassung|übersicht|résumé|en bref|synthèse|riassunto|sintesi|in breve",
            re.I,
        ),
    ),
    (
        "legal",
        re.compile(
            r"abstimmungstext|gesetzestext|verfassungstext|initiativtext|texte soumis|texte de vote|texte du vote|texte mis au vote|texte de (la )?loi|texte de l'initiative|testo in votazione|testo sottoposto|testo di voto|testo della votazione|testo di legge|testo dell'iniziativa",
            re.I,
        ),
    ),
    (
        "committee",
        re.compile(
            r"komitee|initiant|comité|comitato|promotor|promoteur|promotori|referendumskomitee|opposants|gegner|oppositori",
            re.I,
        ),
    ),
    (
        "authorities",
        re.compile(
            r"bundesrat|conseil fédéral|consiglio federale|parlament|assemblée fédérale|assemblea federale|bundesversammlung",
            re.I,
        ),
    ),
]

PREFER = {
    "summary": {"context"},
    None: {"context"},
    "legal": {"legal"},
    "committee": {"committee"},
    "authorities": {"authorities", "recommendation"},
}


def factors(kinds, cue, ids, factor):
    """Extra evidence factor for the chunks whose section type matches the claim cue."""
    want = PREFER.get(cue, set())
    return {i: factor for i in ids if kinds[i] in want} if factor != 1.0 else {}


def classify(booklet):
    """Section type per chunk id: legal, committee, authorities, debate, recommendation, overview, context or other.
    A matching heading opens a section that later sub-headings of the same proposal inherit; committee pages
    (page note from the committee) are always committee."""
    out, current, group, last_heading = [], "other", None, None
    for c in booklet.chunks:
        if c.group != group:
            group, current = c.group, "other"
        heading = (c.heading or "").strip()
        if heading != last_heading:
            last_heading = heading
            for name, pat in _HEAD:
                if pat.search(heading):
                    current = name
                    break
        kind = current
        if c.note and _COMMITTEE_NOTE.search(c.note) and kind != "legal":
            kind = "committee"
        out.append(kind)
    return out


def claim_cue(*texts):
    """Section the claim refers to, from its wording; None when it names no source."""
    text = " ".join(t for t in texts if t)
    for name, pat in _CUES:
        if pat.search(text):
            return name
    return None
