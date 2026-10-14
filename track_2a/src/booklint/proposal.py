"""Find the proposal (Vorlage / objet / oggetto) of a claim inside a booklet. No LLM calls."""

import re

from .ingest import garbled
from .retrieve import BM25

_ORDINAL_ONLY = re.compile(
    r"^\s*(\d+\s+)?[^\W\d_]+\s+(vorlage|objet|oggetto|objets|oggetti)\s*$", re.I
)
MIN_CHUNKS = 8


def groups(booklet):
    out = {}
    for c in booklet.chunks:
        out.setdefault(c.group, []).append(c.id)
    return out


def _garbled_label(g):
    t = re.sub(r"\s+", "", g)
    letters = sum(ch.isalpha() for ch in t)
    vowels = sum(ch.lower() in "aeiouàèéìòùäöüâêîôûy" for ch in t)
    return not t or letters / len(t) < 0.7 or vowels / max(letters, 1) < 0.2


_READABLE = {}


def readable(booklet):
    """Chunk ids without broken font encoding; all chunks unless at least 5 % of the text is garbled."""
    key = (booklet.sha256, len(booklet.chunks))
    if key not in _READABLE:
        bad = {c.id for c in booklet.chunks if garbled(c.text)}
        share = sum(len(booklet.chunks[i].text) for i in bad) / max(
            1, sum(len(c.text) for c in booklet.chunks)
        )
        _READABLE[key] = [
            c.id for c in booklet.chunks if share < 0.05 or c.id not in bad
        ]
    return _READABLE[key]


def uses_outline(booklet):
    """True when the proposals come from the outline (older layout), not from the page headers."""
    return _layout(booklet)[1]


def candidates(booklet):
    """Proposal name -> chunk ids. From the page headers (all OST v1.1 booklets); for older layouts whose headers
    give fewer than two readable proposal names, from the outline found at ingest (ordinal lines or overview)."""
    return _layout(booklet)[0]


_LAYOUT = {}


def _layout(booklet):
    key = (booklet.sha256, len(booklet.chunks))
    if key not in _LAYOUT:
        _LAYOUT[key] = _candidates(booklet)
    return _LAYOUT[key]


def _candidates(booklet):
    gs = groups(booklet)
    out = {
        g: ids
        for g, ids in gs.items()
        if g
        and len(ids) >= MIN_CHUNKS
        and not _ORDINAL_ONLY.match(g)
        and not _garbled_label(g)
    }
    outline = getattr(booklet, "outline", None) or []
    if len(out) >= 2 or len(outline) < 2:
        return out, False
    ok = set(readable(booklet))
    ends = [p for p, _ in outline[1:]] + [booklet.pages + 1]
    seg = {}
    for (start, label), end in zip(outline, ends):
        ids = [c.id for c in booklet.chunks if start <= c.page < end and c.id in ok]
        if len(ids) >= MIN_CHUNKS:
            seg[label or f"p. {start}"] = ids
    return (seg, True) if len(seg) >= 2 else (out, False)


_INDEX = {}


def _index(booklet):
    key = (booklet.sha256, len(booklet.chunks))
    if key not in _INDEX:
        cands = candidates(booklet)
        names = list(cands)
        docs = [
            f"{g} {g} {g} " + " ".join(booklet.chunks[i].text for i in cands[g])
            for g in names
        ]
        _INDEX[key] = (names, BM25(docs, b=0.3) if len(names) >= 2 else None)
    return _INDEX[key]


def rank(booklet, query):
    """Proposal groups ordered by BM25 of the query over group label (boosted) and group text."""
    names, bm25 = _index(booklet)
    if bm25 is None:
        return list(names)
    scores = bm25.scores(query)
    return [names[i] for i in sorted(range(len(names)), key=lambda i: -scores[i])]


def locate(booklet, query, top=1):
    """Chunk ids of the best proposal for the query (vote title or claim); whole booklet if no structure."""
    ranked = rank(booklet, query)
    if len(ranked) < 2:
        return readable(booklet), ""
    cands = candidates(booklet)
    picked = ranked[:top]
    ids = sorted(i for g in picked for i in cands[g])
    return ids, picked[0]


def overview_pages(booklet, region):
    """Pages of the short overview that opens a proposal (In Kürze / Ausgangslage / Contexte / Contesto): the first
    run of consecutive pages of the region. Empty when the region is the whole booklet (no proposal structure)."""
    if not region or len(region) == len(booklet.chunks):
        return set()
    pages = sorted({booklet.chunks[i].page for i in region})
    run = [pages[0]]
    for p in pages[1:]:
        if p - run[-1] > 1:
            break
        run.append(p)
    return set(run)
