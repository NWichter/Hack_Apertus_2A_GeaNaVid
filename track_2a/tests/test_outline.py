"""Proposal scoping for older booklet layouts (outline fallback, broken font encodings)."""

import json
from pathlib import Path

import pytest

from booklint.ingest import Booklet, Chunk, garbled, ingest
from booklint.proposal import candidates, locate

ROOT = Path(__file__).resolve().parents[1]
STRESS = ROOT / "data" / "stress-synth" / "booklets"


def test_garbled_text():
    assert garbled(
        '911$+88*-5=0"4="HAB*=0*="5=7"4=")5,;8= J592+091AB5621/01024# # B119(;23;9:"E"0AL1?2'
    )
    assert not garbled(
        "Der Bundesrat und das Parlament empfehlen, die Initiative abzulehnen, weil sie zu weit geht."
    )
    assert not garbled("kurz")


def _booklet(groups, outline, pages=20):
    chunks = []
    for page in range(1, pages + 1):
        for k in range(3):
            g = groups.get(page, "")
            text = f"Seite {page} Absatz {k} über das Thema {'Steuern' if page >= 11 else 'Ausschaffung'} und mehr Text."
            chunks.append(Chunk(len(chunks), page, text, "", g))
    return Booklet("x.pdf", f"sha-{len(outline)}-{sorted(set(groups.values()))}", "de", pages, chunks, 0.0, outline)


def test_outline_used_only_without_header_structure():
    outline = [[4, "Erste Vorlage Ausschaffung"], [11, "Zweite Vorlage Steuern"]]
    b = _booklet({}, outline)
    cands = candidates(b)
    assert list(cands) == ["Erste Vorlage Ausschaffung", "Zweite Vorlage Steuern"]
    ids, prop = locate(b, "Steuern")
    assert prop == "Zweite Vorlage Steuern"
    assert {b.chunks[i].page for i in ids} == set(range(11, 21))
    headed = _booklet(
        {
            p: ("Erste Vorlage: A" if p < 11 else "Zweite Vorlage: B")
            for p in range(1, 21)
        },
        outline,
    )
    assert set(candidates(headed)) == {"Erste Vorlage: A", "Zweite Vorlage: B"}


def test_garbled_group_names_are_ignored():
    b = _booklet(
        {
            p: ('911$+88*-5=0"4=' if p < 11 else "J592+091AB5621/01024#")
            for p in range(1, 21)
        },
        [],
    )
    assert candidates(b) == {}
    ids, prop = locate(b, "Steuern")
    assert prop == "" and len(ids) == len(b.chunks)


@pytest.mark.skipif(
    not (STRESS / "2018-03-04_de.pdf").is_file(),
    reason="stress-set PDFs not downloaded",
)
def test_overview_outline_on_2018_booklet():
    b = ingest(str(STRESS / "2018-03-04_de.pdf"))
    assert [p for p, _ in b.outline] == [4, 14]


def test_split_is_fixed():
    split = json.loads((ROOT / "data" / "stress-synth" / "split.json").read_text())
    assert split["dev"] == [
        "2005-06-05",
        "2008-11-30",
        "2010-11-28",
        "2016-06-05",
        "2018-03-04",
    ]
    assert split["holdout"] == [
        "1999-06-13",
        "2002-03-03",
        "2013-03-03",
        "2014-02-09",
        "2017-05-21",
    ]
