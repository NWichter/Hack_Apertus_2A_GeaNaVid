"""Text extraction and normalisation helpers for the synthetic hold-out booklets."""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pymupdf

TRACK_ROOT = Path(__file__).resolve().parents[2]

_SPACES = re.compile(r"[\s    ]+")
_LOOSE_DROP = re.compile(r"[\s    ­\-‐‑‒–]+")
_DASHES = "-‐‑"


def clean_page(raw: str) -> str:
    """Join PDF lines into running text.

    Some booklets mark real line ends with a trailing space, so a line without
    one was split inside a word. Others never use trailing spaces; there every
    line break becomes a space and soft line-end hyphens are dropped.
    """
    raw = unicodedata.normalize("NFKC", raw.replace("­", ""))
    lines = raw.split("\n")
    nonempty = [l for l in lines if l.strip()]
    trailing = sum(1 for l in nonempty if l[-1:].isspace()) / max(len(nonempty), 1)
    out = [lines[0]]
    for line in lines[1:]:
        prev = out[-1]
        if trailing >= 0.3:
            out.append(line if prev and not prev[-1:].isspace() else " " + line)
        elif (len(prev) > 1 and prev[-1] in _DASHES and prev[-2].isalpha()
              and line[:1].islower()):
            out[-1] = prev[:-1]
            out.append(line)
        else:
            out.append(" " + line)
    text = "".join(out)
    text = re.sub(r"(?<=[.!?:;])\s*[-‑]+\s*(?=[A-ZÀ-ÖØ-Þ«])", " ", text)
    text = re.sub(r"(?<=[a-zà-ÿ][.!?;])(?=[A-ZÀ-ÖØ-Þ«])", " ", text)
    return _SPACES.sub(" ", text).strip()


def loose(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.replace("­", ""))
    text = text.replace("’", "'").replace("‘", "'")
    return _LOOSE_DROP.sub("", text)


@lru_cache(maxsize=None)
def pages(rel_path: str) -> tuple[str, ...]:
    doc = pymupdf.open(TRACK_ROOT / rel_path)
    return tuple(p.get_text() for p in doc)


@lru_cache(maxsize=None)
def clean_pages(rel_path: str) -> tuple[str, ...]:
    return tuple(clean_page(p) for p in pages(rel_path))


@lru_cache(maxsize=None)
def loose_pages(rel_path: str) -> tuple[str, ...]:
    return tuple(loose(p) for p in pages(rel_path))


@lru_cache(maxsize=None)
def loose_doc(rel_path: str) -> str:
    return "".join(loose_pages(rel_path))


@lru_cache(maxsize=None)
def loose_doc_no_folios(rel_path: str) -> str:
    """Loose text with the page number at the top of each page removed."""
    return "".join(loose(re.sub(r"^\s*\d{1,2}(?!\d)", "", p)) for p in pages(rel_path))
