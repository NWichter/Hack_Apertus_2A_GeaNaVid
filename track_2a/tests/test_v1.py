"""Offline tests for the v1 pipeline parts: numbers, calibration, prompts, proposal location, redaction."""

import json
import math

from booklint import numbers
from booklint.ingest import Booklet, Chunk
from booklint.llm import redact
from booklint.nli import aggregate, build_messages, yes_prob
from booklint.pipeline import Options, apply_bias, load_examples
from booklint.proposal import locate


def test_numbers_across_languages_and_scales():
    chk = numbers.check(
        "Der Bund zahlt 400 Millionen Franken, 9 % und 1,7 Millionen Personen",
        ["La Confédération verse 400 millions de francs, 9 pour cent, 1.7 millions de personnes"],
    )
    assert chk["missing"] == []
    assert numbers.check("Kosten: 3 Mrd. Franken", ["3000 Millionen Franken"])["missing"] == []
    assert numbers.check("Le taux passe à 3,5 %", ["Il tasso sale al 2,5 per cento"])["missing"] == ["3,5 %"]
    assert numbers.check("Der Bundesrat sagt, das sei gut", ["x"])["claim"] == []


def test_apply_bias_moves_decision():
    probs = {"entailment": 0.6, "neutral": 0.3, "contradiction": 0.1}
    assert apply_bias(probs, {}) == probs
    out = apply_bias(probs, {"neutral": 1.0})
    assert max(out, key=out.get) == "neutral"
    assert abs(sum(out.values()) - 1) < 1e-9


def test_aggregate_and_yes_prob():
    assert aggregate(["entailment", "contradiction"]) == "contradiction"
    assert aggregate(["entailment", "entailment"]) == "entailment"
    assert aggregate(["entailment", "neutral"]) == "neutral"
    rec = {"logprobs": [{"token": "yes", "top": [["yes", math.log(0.8)], ["no", math.log(0.2)]]}]}
    assert abs(yes_prob(rec) - 0.8) < 1e-9


def test_fewshot_examples_become_turns():
    ex = load_examples(3)
    assert len(ex) == 3 and {e["label"] for e in ex} == {"entailment", "neutral", "contradiction"}
    msgs = build_messages(["(p. 1) Text"], "Claim", "de", "fr", "Affirmation", examples=ex, note="n")
    assert [m["role"] for m in msgs] == ["system"] + ["user", "assistant"] * 3 + ["user"]
    assert json.loads(msgs[2]["content"])["label"] == ex[0]["label"]
    assert "Note: n" in msgs[-1]["content"] and "Affirmation" in msgs[-1]["content"]


def test_fewshot_never_from_ablation_or_test_split():
    from pathlib import Path

    data = Path(__file__).resolve().parents[1] / "data" / "v1"
    ids = {e["id"] for e in load_examples(10)}
    for split in ("dev_s", "test"):
        path = data / f"{split}.jsonl"
        if path.is_file():
            assert not ids & {json.loads(l)["id"] for l in path.open(encoding="utf-8")}


def _booklet():
    chunks = []
    groups = [
        ("Erste Vorlage: Liegenschaftssteuern", "Die Kantone dürfen eine Liegenschaftssteuer auf Zweitliegenschaften erheben."),
        ("Zweite Vorlage: E-ID-Gesetz", "Die elektronische Identität E-ID ist freiwillig und kostenlos."),
    ]
    for g, text in groups:
        for i in range(10):
            chunks.append(Chunk(len(chunks), 4 + len(chunks) // 4, f"{text} Absatz {i}.", "Im Detail", g))
    return Booklet("x.pdf", "0" * 64, "de", 20, chunks, 0.0)


def test_locate_by_vote_title():
    b = _booklet()
    ids, name = locate(b, "Bundesgesetz über den elektronischen Identitätsnachweis (E-ID-Gesetz)")
    assert name == "Zweite Vorlage: E-ID-Gesetz"
    assert all(b.chunks[i].group == name for i in ids)


def test_default_pipeline_is_apertus_only_and_model_aware():
    from booklint.pipeline import Pipeline

    opt = Options()
    assert opt.crossling == "none" and opt.cascade == "" and opt.mode == "retrieval" and opt.scope == "vote"
    assert opt.translate

    class M:
        def __init__(self, model):
            self.model = model

    small, large = Pipeline(M("apertus-v1.5-8b"), Options()), Pipeline(M("apertus-v1.5-70b"), Options())
    assert len(small.examples) == 3 and small.decompose
    assert large.examples == [] and not large.decompose


def test_redact_hides_key_hash():
    assert "3f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c" not in redact("429 for key hash 3f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c")
