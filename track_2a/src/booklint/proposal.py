"""Find the proposal (Vorlage / objet / oggetto) of a claim inside a booklet. No LLM calls."""

import re

from .retrieve import BM25

_ORDINAL_ONLY = re.compile(r"^\s*(\d+\s+)?[^\W\d_]+\s+(vorlage|objet|oggetto|objets|oggetti)\s*$", re.I)
MIN_CHUNKS = 8


def groups(booklet):
    out = {}
    for c in booklet.chunks:
        out.setdefault(c.group, []).append(c.id)
    return out


def candidates(booklet):
    gs = groups(booklet)
    return {g: ids for g, ids in gs.items() if g and len(ids) >= MIN_CHUNKS and not _ORDINAL_ONLY.match(g)}


_INDEX = {}


def _index(booklet):
    key = (booklet.sha256, len(booklet.chunks))
    if key not in _INDEX:
        cands = candidates(booklet)
        names = list(cands)
        docs = [f"{g} {g} {g} " + " ".join(booklet.chunks[i].text for i in cands[g]) for g in names]
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
        return [c.id for c in booklet.chunks], ""
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
