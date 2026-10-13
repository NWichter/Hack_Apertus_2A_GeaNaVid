"""Sentence-level evidence: pick the sentence(s) of the cited chunks that best match the claim. No LLM calls."""

import re

from .textnorm import fold, tokens

_ABBR = set(
    """art abs al ziff bst lit nr ca bzw vgl z b d h u a usw etc evtl inkl insb mio mrd fr chf rp s ff
    resp sog str dr prof st bv cf p ex env cst lett cpv cost cc ecc ss sig mm mme m n no e g i v vol
    let par pp ch""".split()
)
_BOUNDARY = re.compile(r"[.!?…]+[\"»”’)\]]*\s+(?=[\"«„“(\[]?[A-ZÄÖÜÀ-ÖØ-Ý0-9])")
_LAST_WORD = re.compile(r"([^\W_]+)\W*$")
_MIN_LEN = 25


def split(text):
    """Sentence spans (start, end) in `text`; tolerant to abbreviations, ordinals and article numbers."""
    spans, start = [], 0
    for m in _BOUNDARY.finditer(text):
        w = _LAST_WORD.search(text[start : m.start() + 1])
        word = w.group(1) if w else ""
        if word.lower() in _ABBR or (len(word) == 1 and word.isalpha()):
            continue
        if word.isdigit() and len(word) <= 2:
            continue
        spans.append((start, m.start() + len(m.group(0).rstrip())))
        start = m.end()
    if text[start:].strip():
        spans.append((start, len(text.rstrip())))
    merged = []
    for s, e in spans:
        if merged and (e - s < _MIN_LEN or merged[-1][1] - merged[-1][0] < _MIN_LEN):
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def _grams(text, n=5):
    s = re.sub(r"[^0-9a-z]+", "", fold(text))
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def score(sentence, queries, idf=None):
    """Share of the query covered by the sentence (idf-weighted stems and character 5-grams, the latter
    robust to split words such as "Bundes steuer"), divided by a mild length penalty."""
    stoks = set(tokens(sentence))
    sgrams = _grams(sentence)
    if not stoks or not sgrams:
        return 0.0
    idf = idf or {}
    best = 0.0
    for q in queries:
        qtoks, qgrams = set(tokens(q)), _grams(q)
        if not qtoks or not qgrams:
            continue
        tok = sum(idf.get(t, 1.0) for t in qtoks & stoks) / sum(idf.get(t, 1.0) for t in qtoks)
        gram = len(qgrams & sgrams) / len(qgrams)
        best = max(best, (tok + gram) / 2)
    return best / max(1.0, len(sgrams) / max(len(_grams(queries[0])), 40)) ** 0.5


def select(chunks, queries, idf=None, preferred=(), bonus=1.2, max_spans=2, ratio=0.7, factors=None, min_share=None):
    """Best sentence span(s) among `chunks`, best first.

    Sentences of `preferred` chunks (the passages Apertus cited) get their score multiplied by `bonus`; `factors` maps
    chunk ids to an extra factor (sections the claim points to).
    Each span is a dict with text, page, char_start, char_end, chunk_id and score. Offsets refer to the booklet
    text (chunk texts joined by two characters, the convention of the chunk offsets), so
    `text == booklet_text[char_start:char_end]`. The best sentence is extended by an adjacent sentence of the
    same chunk if that one scores at least `ratio` of it; a span from another chunk is added if it scores at least
    `min_share` (default `ratio`) of the best one, up to `max_spans` spans from different chunks.
    """
    queries = [q for q in queries if q and q.strip()]
    if not queries:
        return []
    preferred = set(preferred)
    cands, seen = [], set()
    for c in chunks:
        if c.id in seen:
            continue
        seen.add(c.id)
        spans = split(c.text)
        factor = (bonus if c.id in preferred else 1.0) * (factors or {}).get(c.id, 1.0)
        scored = [factor * score(c.text[s:e], queries, idf) for s, e in spans]
        cands += [(sc, -len(cands), c, spans, scored, j) for j, sc in enumerate(scored)]
    cands = [x for x in cands if x[0] > 0]
    if not cands:
        return []
    cands.sort(key=lambda x: (-x[0], -x[1]))
    top = cands[0][0]
    picked = []
    for sc, _, c, spans, scored, j in cands:
        if len(picked) >= max_spans or sc < (ratio if min_share is None else min_share) * top:
            break
        if all(c.id != p["chunk_id"] for p in picked):
            picked.append(_span(c, spans, scored, j, ratio))
    return picked


def _span(c, spans, scored, j, ratio):
    lo = hi = j
    near = [
        k
        for k in (j - 1, j + 1)
        if 0 <= k < len(spans) and scored[k] >= ratio * scored[j]
    ]
    if near:
        k = max(near, key=lambda k: scored[k])
        lo, hi = min(j, k), max(j, k)
    s, e = spans[lo][0], spans[hi][1]
    return {
        "text": c.text[s:e],
        "page": c.page,
        "char_start": c.char_start + s,
        "char_end": c.char_start + e,
        "chunk_id": c.id,
        "score": round(scored[j], 4),
    }
