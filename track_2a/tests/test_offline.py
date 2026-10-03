"""Offline tests: no network, no LLM endpoint. The demo booklet is read from BOOKLET_MIRROR when set."""

import json
import math
import os
from pathlib import Path

import pytest

from booklint.llm import Call
from booklint.metrics import evidence_hit, macro_f1
from booklint.nli import label_probs, parse
from booklint.pipeline import Options, Pipeline
from booklint.textnorm import detect_language, tokens

DATA = Path(__file__).resolve().parents[1] / "data" / "archive" / "demo-2026-10-01"


def test_tokens_normalise_numbers_and_stems():
    assert "500000" in tokens("rund 500'000 Personen")
    assert "500000" in tokens("environ 500 000 personnes")
    assert "1.7" in tokens("1,7 Millionen")
    assert tokens("Nachhaltigkeitsinitiative")[0] == "nachha"


def test_detect_language():
    assert (
        detect_language("Der Bundesrat empfiehlt, die Initiative abzulehnen.") == "de"
    )
    assert (
        detect_language("Le Conseil fédéral recommande de rejeter l'initiative.")
        == "fr"
    )
    assert (
        detect_language("Il Consiglio federale raccomanda di respingere l'iniziativa.")
        == "it"
    )


def test_macro_f1():
    f1, per = macro_f1([0, 1, 2, 0], [0, 1, 2, 0])
    assert f1 == 1.0
    f1, _ = macro_f1([0, 0, 1, 2], [0, 0, 0, 0])
    assert round(f1, 3) == 0.222


def test_parse_and_label_probs():
    content = '{"evidence": [2, 9, 2], "label": "contradiction"}'
    rec = {
        "content": content,
        "logprobs": _logprobs(content, {"contr": -0.1, "ent": -2.5, "neutral": -4.0}),
    }
    label, evidence = parse(rec, 5)
    assert label == "contradiction" and evidence == [2]
    probs = label_probs(rec)
    assert max(probs, key=probs.get) == "contradiction"
    assert abs(sum(probs.values()) - 1) < 1e-9


def test_evidence_hit():
    ref = "Erster Absatz mit Text.\n\nSeit Einführung der Personenfreizügigkeit 2002 ist die Bevölkerung um 1,7 Millionen gewachsen."
    assert evidence_hit(
        [
            "Seit Einführung der Personenfreizügigkeit 2002 ist die Bevölkerung um 1,7 Millionen gewachsen."
        ],
        ref,
    )
    assert not evidence_hit(
        ["Ein ganz anderer Absatz über den Zivildienst und seine Dauer."], ref
    )


def _logprobs(content, label_top):
    pre, post = content.split('"label": "')
    toks = [pre + '"label": "', post]
    return [
        {"token": toks[0], "top": [[toks[0], 0.0]]},
        {"token": toks[1], "top": [[t, lp] for t, lp in label_top.items()]},
    ]


class FakeLLM:
    model = "fake"

    def __init__(self):
        self.messages = []

    def chat(self, messages, usage, purpose, model=None, **params):
        self.messages.append(messages)
        user = messages[-1]["content"]
        n = user.count("\n[")
        label = "contradiction" if "500'000" in user else "entailment"
        content = json.dumps({"evidence": [1] if n else [], "label": label})
        usage.add(Call(purpose, "fake", len(user) // 4, 12, 0.01, False))
        return {
            "content": content,
            "logprobs": _logprobs(
                content, {label[:3]: math.log(0.9), "neutral": math.log(0.1)}
            ),
        }


demo_pdf = os.environ.get("BOOKLET_MIRROR")


@pytest.mark.skipif(not demo_pdf, reason="BOOKLET_MIRROR not set")
@pytest.mark.parametrize(
    "mode", ["retrieval", "ladder", "section", "full", "oracle", "claim-only"]
)
def test_pipeline_modes(mode):
    row = json.loads((DATA / "demo.jsonl").read_text(encoding="utf-8").splitlines()[2])
    llm = FakeLLM()
    out = Pipeline(llm, Options(mode=mode)).check(
        row["claim"], row["booklet_url"], row["claim_language"], row["reference_string"]
    )
    assert out["label_name"] in ("entailment", "neutral", "contradiction")
    assert out["usage"]["llm_calls"] >= 1
    if mode in ("retrieval", "ladder", "section", "full"):
        assert out["evidence"] and out["evidence"][0]["page"] >= 1


@pytest.mark.skipif(not demo_pdf, reason="BOOKLET_MIRROR not set")
def test_crosslingual_parallel_anchor():
    row = json.loads(
        (DATA / "demo_crossling.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    out = Pipeline(FakeLLM(), Options(mode="retrieval", crossling="parallel", translate=False)).check(
        row["claim"], row["booklet_url"], row["claim_language"]
    )
    assert out["anchor"] == "parallel"
    assert out["booklet_language"] == row["booklet_language"]
