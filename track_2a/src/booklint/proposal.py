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


def rank(booklet, query):
    """Proposal groups ordered by BM25 of the query over group label (boosted) and group text."""
    cands = candidates(booklet)
    if len(cands) < 2:
        return list(cands)
    names = list(cands)
    docs = [f"{g} {g} {g} " + " ".join(booklet.chunks[i].text for i in cands[g]) for g in names]
    scores = BM25(docs, b=0.3).scores(query)
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
