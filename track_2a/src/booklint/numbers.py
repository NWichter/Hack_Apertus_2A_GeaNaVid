"""Deterministic number check: which numbers of the claim (amounts, percentages, years, durations) occur in a text."""

import re

from .textnorm import clean

_SCALE = {
    "mio": 1e6, "million": 1e6, "millionen": 1e6, "millions": 1e6, "milione": 1e6, "milioni": 1e6,
    "mrd": 1e9, "milliarde": 1e9, "milliarden": 1e9, "milliard": 1e9, "milliards": 1e9, "miliardo": 1e9, "miliardi": 1e9,
    "tausend": 1e3, "mille": 1e3, "mila": 1e3,
}
_WORDS = {
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "zwölf": 12,
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "douze": 12,
    "quattro": 4, "cinque": 5, "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "dodici": 12,
    "hälfte": 0.5, "moitié": 0.5, "metà": 0.5,
}
_NUM = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:['’  ]\d{3})+|\d+(?:[.,]\d+)?)\s*(%|prozent|pour\s*cent|per\s*cento)?"
    r"(?:\s*(" + "|".join(sorted(_SCALE, key=len, reverse=True)) + r")\b)?",
    re.I,
)
_WORD = re.compile(r"\b(" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")\b", re.I)


def extract(text):
    """Set of numeric values; a number with a scale word adds both the raw and the scaled value."""
    text = clean(text)
    out = []
    for m in _NUM.finditer(text):
        raw = re.sub(r"['’  ]", "", m.group(1)).replace(",", ".")
        try:
            v = float(raw)
        except ValueError:
            continue
        unit = (m.group(3) or "").lower()
        values = {v}
        if unit in _SCALE:
            values.add(v * _SCALE[unit])
        out.append({"text": m.group(0).strip(), "values": values, "percent": bool(m.group(2))})
    for m in _WORD.finditer(text):
        out.append({"text": m.group(0), "values": {_WORDS[m.group(1).lower()]}, "percent": False})
    return out


def _flat(nums):
    return [v for n in nums for v in n["values"]]


def _same(a, b):
    return abs(a - b) <= max(1e-9, 0.005 * max(abs(a), abs(b)))


def check(claim, texts):
    """Claim numbers missing from the texts. Small integers (< 3) and article-like numbers are ignored."""
    nums = [n for n in extract(claim) if max(n["values"]) >= 3 or n["percent"]]
    pool = _flat(extract(" ".join(texts)))
    missing = [n["text"] for n in nums if not any(_same(v, p) for v in n["values"] for p in pool)]
    return {"claim": [n["text"] for n in nums], "missing": missing}
