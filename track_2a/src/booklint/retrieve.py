import math
import re
from collections import Counter

from .textnorm import tokens


class BM25:
    def __init__(self, texts, k1=1.2, b=0.75):
        self.docs = [tokens(t) for t in texts]
        self.tf = [Counter(d) for d in self.docs]
        self.len = [len(d) for d in self.docs]
        self.avg = sum(self.len) / max(len(self.docs), 1)
        df = Counter(w for d in self.docs for w in set(d))
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query):
        q = Counter(tokens(query))
        out = []
        for tf, length in zip(self.tf, self.len):
            s = 0.0
            norm = self.k1 * (1 - self.b + self.b * length / self.avg)
            for w, qn in q.items():
                f = tf.get(w)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + norm)
            out.append(s)
        return out


class Retriever:
    def __init__(self, booklet):
        self.booklet = booklet
        self.bm25 = BM25([f"{c.heading} {c.text}" for c in booklet.chunks])

    def rank(self, queries):
        """Reciprocal-rank fusion over one BM25 ranking per query string."""
        fused = Counter()
        best = 0.0
        for q in queries:
            sc = self.bm25.scores(q)
            best = max(best, max(sc, default=0.0))
            order = sorted(range(len(sc)), key=lambda i: -sc[i])
            for rank, i in enumerate(order[:50]):
                if sc[i] > 0:
                    fused[i] += 1.0 / (60 + rank)
        return [i for i, _ in fused.most_common()], best

    def expand(self, hit_ids, neighbors=1):
        chunks = self.booklet.chunks
        picked = set()
        for i in hit_ids:
            for j in range(i - neighbors, i + neighbors + 1):
                if 0 <= j < len(chunks) and chunks[j].page == chunks[i].page:
                    picked.add(j)
        return sorted(picked)

    def top_k(self, queries, k=5, neighbors=1):
        ranked, best = self.rank(queries)
        hits = ranked[:k]
        return self.expand(hits, neighbors), hits, best

    def section_of(self, hit_ids):
        groups = {self.booklet.chunks[i].group for i in hit_ids}
        return [c.id for c in self.booklet.chunks if c.group in groups]

    def pages_around(self, hit_ids, radius=1):
        pages = {self.booklet.chunks[i].page + d for i in hit_ids for d in range(-radius, radius + 1)}
        return [c.id for c in self.booklet.chunks if c.page in pages]

    def section(self, queries, k=1):
        ranked, _ = self.rank(queries)
        return self.section_of(ranked[:k])


_URL_NAMES = {"de": "erlaeuterungen_des_bundesrates", "fr": "explications_du_conseil_federal", "it": "spiegazioni_del_consigliofederale"}


def parallel_url(url, lang):
    """URL of another language version of the same booklet (bk.admin.ch naming scheme), or None."""
    m = re.search(r"/dam/(de|fr|it)/(.*?)/(\d{4}-\d{2}-\d{2})_([a-z_]+)\.pdf$", url)
    if not m:
        return None
    return url[: m.start()] + f"/dam/{lang}/{m.group(2)}/{m.group(3)}_{_URL_NAMES[lang]}.pdf"


def map_parallel(src_booklet, src_ids, dst_booklet):
    """Map chunk ids between language versions by page and relative position on the page."""
    def by_page(b):
        pages = {}
        for c in b.chunks:
            pages.setdefault(c.page, []).append(c.id)
        return pages

    src_pages, dst_pages = by_page(src_booklet), by_page(dst_booklet)
    out = []
    for i in src_ids:
        page = src_booklet.chunks[i].page
        src, dst = src_pages.get(page, []), dst_pages.get(page, [])
        if not dst:
            continue
        rel = src.index(i) / max(len(src) - 1, 1)
        j = dst[round(rel * (len(dst) - 1))]
        if j not in out:
            out.append(j)
    return out
