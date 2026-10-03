"""Sentence-level evidence and the decision/answer/page/sentence output. No network, no LLM endpoint."""

import json
import math

import pytest

from booklint import sentences
from booklint.ingest import Booklet, Chunk
from booklint.llm import Call
from booklint.pipeline import Options, Pipeline
from booklint.retrieve import Retriever


def _texts(text):
    return [text[s:e] for s, e in sentences.split(text)]


def test_split_keeps_abbreviations_ordinals_and_articles():
    text = (
        "Gemäss Art. 5 Abs. 2 BV gilt dies z. B. ab dem 1. Januar 2025 für alle Kantone. "
        "Die Kosten steigen bis 2030. Danach sinken sie wieder deutlich unter das heutige Niveau."
    )
    assert _texts(text) == [
        "Gemäss Art. 5 Abs. 2 BV gilt dies z. B. ab dem 1. Januar 2025 für alle Kantone.",
        "Die Kosten steigen bis 2030.",
        "Danach sinken sie wieder deutlich unter das heutige Niveau.",
    ]
    fr = "Le Conseil fédéral recommande de rejeter l'initiative. Elle coûterait env. 3 milliards de francs par an."
    assert len(_texts(fr)) == 2
    it = "L'Assemblea federale raccomanda di respingere l'iniziativa. Il Consiglio federale è dello stesso parere."
    assert len(_texts(it)) == 2


def test_split_merges_fragments():
    assert _texts("Ja. Bundesrat und Parlament empfehlen, die Vorlage anzunehmen.") == [
        "Ja. Bundesrat und Parlament empfehlen, die Vorlage anzunehmen."
    ]


def _booklet():
    paras = [
        (
            "Im Überblick",
            "Die Vorlage betrifft die Kinderbetreuung. Bundesrat und Parlament wollen bei der direkten "
            "Bundes steuer den maximalen Abzug für die Drittbetreuung von 10100 auf 25000 Franken pro Kind erhöhen. "
            "Sie wollen damit Familie und Beruf besser vereinbar machen.",
        ),
        ("Argumente", "Das Komitee hält die Vorlage für einen Steuerbonus für Reiche."),
        (
            "Empfehlung",
            "Aus all diesen Gründen empfehlen Bundesrat und Parlament, die Änderung anzunehmen.",
        ),
    ]
    chunks, pos = [], 0
    for page, (heading, text) in enumerate(paras, start=3):
        chunks.append(
            Chunk(
                len(chunks),
                page,
                text,
                heading,
                "Erste Vorlage: Kinderdrittbetreuungskosten",
                "",
                pos,
                pos + len(text),
            )
        )
        pos += len(text) + 2
    return Booklet("mem.pdf", "0" * 64, "de", 10, chunks, 0.0)


def test_select_returns_original_text_with_booklet_offsets():
    b = _booklet()
    full = "\n\n".join(c.text for c in b.chunks)
    claim = "Der Abzug für die Drittbetreuung bei der direkten Bundessteuer steigt auf 25 000 Franken pro Kind."
    picked = sentences.select(b.chunks, [claim], Retriever(b).bm25.idf)
    best = picked[0]
    assert best["text"].startswith(
        "Bundesrat und Parlament wollen bei der direkten Bundes steuer"
    )
    assert best["text"].endswith("pro Kind erhöhen.")
    assert full[best["char_start"] : best["char_end"]] == best["text"]
    assert best["page"] == 3 and best["chunk_id"] == 0


def test_select_prefers_cited_chunk_on_near_tie():
    b = _booklet()
    claim = "Bundesrat und Parlament empfehlen, die Änderung anzunehmen."
    picked = sentences.select(b.chunks, [claim], preferred=[2])
    assert picked[0]["chunk_id"] == 2


def _logprobs(content, label):
    pre, post = content.split('"label": "')
    return [
        {"token": pre + '"label": "', "top": [[pre + '"label": "', 0.0]]},
        {"token": post, "top": [[label[:3], math.log(0.99)], ["xyz", math.log(0.01)]]},
    ]


class LabelLLM:
    model = "fake"

    def __init__(self, label):
        self.label = label

    def chat(self, messages, usage, purpose, model=None, **params):
        evidence = [] if self.label == "neutral" else [1]
        content = json.dumps({"evidence": evidence, "label": self.label})
        usage.add(Call(purpose, "fake", 100, 10, 0.01, False))
        return {"content": content, "logprobs": _logprobs(content, self.label)}


def _check(label):
    b = _booklet()
    pipe = Pipeline(
        LabelLLM(label), Options(scope="booklet", decompose=False, fewshot=0)
    )
    pipe._booklets["mem.pdf"] = (b, Retriever(b))
    return pipe.check(
        "Der Abzug für die Drittbetreuung bei der direkten Bundessteuer steigt auf 25 000 Franken pro Kind.",
        "mem.pdf",
        "de",
    )


@pytest.mark.parametrize(
    "label,decision,answer", [("entailment", 0, "yes"), ("contradiction", 2, "no")]
)
def test_output_has_decision_page_and_sentence(label, decision, answer):
    out = _check(label)
    assert (
        out["decision"] == out["entailment_label"] == decision
        and out["answer"] == answer
    )
    assert out["page"] == out["evidence_sentences"][0]["page"] == 3
    assert "25000 Franken pro Kind" in out["evidence_sentence"]
    assert set(out["evidence_sentences"][0]) == {
        "text",
        "page",
        "char_start",
        "char_end",
        "chunk_id",
    }
    assert out["evidence"]


def test_neutral_has_no_page_sentence_or_evidence():
    out = _check("neutral")
    assert (out["decision"], out["answer"]) == (1, "blank")
    assert out["page"] is None and out["evidence_sentence"] is None
    assert out["evidence_sentences"] == [] and out["evidence"] == []
