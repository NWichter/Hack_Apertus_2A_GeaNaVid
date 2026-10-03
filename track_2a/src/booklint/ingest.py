"""PDF booklet -> ordered text chunks with page, heading and proposal group. No LLM calls."""

import hashlib
import json
import os
import re
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf as fitz

from .config import cache_dir
from .textnorm import clean, detect_language

INGEST_VERSION = "ingest-v5"
_ORDINAL = re.compile(
    r"^(\d+\s+)?((erste|zweite|dritte|vierte|fünfte|sechste)\s+vorlage"
    r"|(premier|deuxième|troisième|quatrième|cinquième|sixième)\s+objet"
    r"|(primo|secondo|terzo|quarto|quinto|sesto)\s+oggetto)",
    re.IGNORECASE,
)
_YES_NO = {"ja", "nein", "oui", "non", "sì", "si", "no"}
_URL = re.compile(r"/dam/(de|fr|it)/.*?/(\d{4}-\d{2}-\d{2})_[^/]+\.pdf$")


@dataclass
class Chunk:
    id: int
    page: int
    text: str
    heading: str
    group: str
    note: str = ""
    char_start: int = 0
    char_end: int = 0

    def render(self):
        ctx = " / ".join(x for x in (self.group, self.note, self.heading) if x)
        return f"(p. {self.page}; {ctx}) {self.text}" if ctx else f"(p. {self.page}) {self.text}"


@dataclass
class Booklet:
    source: str
    sha256: str
    language: str
    pages: int
    chunks: list
    ingest_seconds: float

    def group_of(self, chunk_ids):
        return {self.chunks[i].group for i in chunk_ids}


def _download(url, target):
    mirror = os.environ.get("BOOKLET_MIRROR")
    m = _URL.search(url)
    if mirror and m:
        local = Path(mirror) / f"{m.group(2)}_{m.group(1)}.pdf"
        if local.is_file():
            target.write_bytes(local.read_bytes())
            return
    req = urllib.request.Request(
        url, headers={"User-Agent": "booklint/0.1 (research prototype)"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                target.write_bytes(resp.read())
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def fetch(source):
    if re.match(r"https?://", source):
        target = (
            cache_dir()
            / "pdf"
            / (hashlib.sha1(source.encode()).hexdigest()[:16] + ".pdf")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file():
            _download(source, target)
        return target
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(source)
    return path


def _line_text(line):
    parts = []
    for span in line["spans"]:
        t = span["text"]
        if span["flags"] & 1 and t.strip().isdigit():
            continue
        parts.append(t)
    return "".join(parts)


_NO_JOIN = {"und", "oder", "bzw", "sowie", "et", "ou", "e", "o", "od"}


def _block_text(block):
    out = ""
    for line in block["lines"]:
        t = _line_text(line).strip()
        if not t:
            continue
        first = t.split()[0].lower()
        if out.endswith("­"):
            out = out[:-1] + t
        elif re.search(r"[^\W\d_] ?-$", out) and t[:1].islower() and first not in _NO_JOIN:
            out = re.sub(r" ?-$", "", out) + t
        else:
            out = f"{out} {t}" if out else t
    return clean(out)


def _is_bold(block):
    chars = bold = 0
    for line in block["lines"]:
        for s in line["spans"]:
            n = len(s["text"].strip())
            chars += n
            if s["flags"] & 16 or "bold" in s["font"].lower():
                bold += n
    return chars > 0 and bold / chars > 0.6


def _blocks(page):
    height = page.rect.height
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        text = _block_text(b)
        if not text:
            continue
        size = max(s["size"] for line in b["lines"] for s in line["spans"])
        x0, y0, x1, y1 = b["bbox"]
        if y1 < 0.08 * height and size <= 9.5:
            kind = "header"
        elif y0 > 0.92 * height and size <= 9.5:
            kind = "footer"
        elif len(text.split()) <= 14 and (_is_bold(b) or size >= 11) and not text.endswith(".") and text.lower() not in _YES_NO:
            kind = "heading"
        else:
            kind = "text"
        out.append({"kind": kind, "text": text, "x0": x0, "y0": y0, "size": size})
    return out


def _strip_page_no(text):
    return re.sub(r"^(\d+\s+)+|(\s+\d+)+$", "", text).strip()


def _parse(path):
    doc = fitz.open(path)
    pages = [_blocks(page) for page in doc]
    notes = {}
    for pno, blocks in enumerate(pages, start=1):
        for b in blocks:
            text = _strip_page_no(b["text"])
            if b["kind"] in ("header", "footer") and len(text.split()) > 8 and not _ORDINAL.match(text):
                notes[pno] = text
                notes.setdefault(pno - 1 if pno % 2 else pno + 1, text)
    chunks, group, last_heading = [], "", ""
    full_len = 0
    for pno, blocks in enumerate(pages, start=1):
        tops = [_strip_page_no(b["text"]) for b in blocks if b["kind"] == "header"]
        tops = [t for t in tops if t and not t.isdigit() and (len(t.split()) <= 8 or _ORDINAL.match(t))]
        header = next((t for t in tops if _ORDINAL.match(t)), tops[0] if tops else "")
        title = next((b["text"] for b in blocks if b["kind"] == "heading" and _ORDINAL.match(b["text"])), "")
        if header:
            group = header
        elif title:
            group = title
        headings = sorted((b for b in blocks if b["kind"] == "heading"), key=lambda b: b["y0"])
        for b in sorted((b for b in blocks if b["kind"] == "text"), key=lambda b: (round(b["y0"]), b["x0"])):
            above = [h for h in headings if h["y0"] <= b["y0"] + 12]
            heading = above[-1]["text"] if above else last_heading
            start = full_len
            full_len += len(b["text"]) + 2
            chunks.append(Chunk(len(chunks), pno, b["text"], heading, group, notes.get(pno, ""), start, start + len(b["text"])))
        if headings:
            last_heading = headings[-1]["text"]
    sample = " ".join(c.text for c in chunks[:200])
    return chunks, len(doc), detect_language(sample) if sample else "?"


def page_texts(source):
    """Plain text per page (PyMuPDF reading order), for the whole-booklet baseline."""
    path = fetch(source)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    target = cache_dir() / "booklets" / f"{sha[:20]}.pages-v1.json"
    if target.is_file():
        return json.loads(target.read_text(encoding="utf-8"))
    with fitz.open(path) as doc:
        pages = [clean(page.get_text("text")) for page in doc]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    return pages


def ingest(source, use_cache=True):
    path = fetch(source)
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    target = cache_dir() / "booklets" / f"{sha[:20]}.{INGEST_VERSION}.json"
    if use_cache and target.is_file():
        raw = json.loads(target.read_text(encoding="utf-8"))
        raw["chunks"] = [Chunk(**c) for c in raw["chunks"]]
        raw["source"] = source
        return Booklet(**raw)
    t0 = time.perf_counter()
    chunks, pages, lang = _parse(path)
    if sum(len(c.text) for c in chunks) < 500:
        raise ValueError(
            f"{source}: no text layer (scanned booklet), OCR fallback not implemented"
        )
    booklet = Booklet(
        source, sha, lang, pages, chunks, round(time.perf_counter() - t0, 3)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(booklet)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return booklet
