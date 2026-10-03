"""Batch robustness of `predict`, evidence unit, evidence fallback, foreign vote titles, language detection."""

import io
import json
import sys
from unittest.mock import patch

from booklint import pipeline as pipeline_module
from booklint.cli import main, normalize_case
from booklint.ingest import Booklet, Chunk
from booklint.llm import Call
from booklint.metrics import efficiency
from booklint.pipeline import Options, Pipeline
from booklint.retrieve import Retriever
from booklint.textnorm import detect_language

from test_slide25 import MockLLM


def _env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake-test-endpoint")
    monkeypatch.setenv("LLM_API_KEY", "fake-api-key")


def test_predict_keeps_going_when_a_case_fails(monkeypatch, tmp_path):
    _env(monkeypatch)
    ok = {
        "id": "ok",
        "reference": {"text": "Die E-ID ist freiwillig und kostenlos."},
        "claim": {"text": "Die E-ID ist kostenlos."},
    }
    missing_pdf = {
        "id": "missing-pdf",
        "booklet": {"path": str(tmp_path / "nope.pdf")},
        "vote": "x",
        "claim": {"text": "Die E-ID ist kostenlos."},
    }
    no_claim = {"id": "no-claim", "reference": {"text": "Text."}}
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        "\n".join(
            json.dumps(c) for c in (ok, missing_pdf, no_claim, dict(ok, id="ok-2"))
        ),
        encoding="utf-8",
    )
    out_file = tmp_path / "out" / "preds.jsonl"
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)

    with patch("booklint.cli.LLM", return_value=MockLLM(label="entailment")):
        main(["predict", "--case", str(cases), "-o", str(out_file)])

    out = [
        json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines()
    ]
    assert [o["id"] for o in out] == ["ok", "missing-pdf", "no-claim", "ok-2"]
    for o in (out[0], out[3]):
        assert "error" not in o and o["label"] == 0 and o["evidence"]
    for o in (out[1], out[2]):
        assert set(o) == {"id", "label", "label_name", "evidence", "metrics", "error"}
        assert o["label"] == 1 and o["label_name"] == "neutral" and o["evidence"] == []
        assert o["metrics"] == {
            "input_tokens": 0,
            "output_tokens": 0,
            "inference_time_ms": 0,
        }
    assert "nope.pdf" in out[1]["error"]
    assert "missing-pdf" in err.getvalue()


def test_predict_single_failing_case_prints_neutral(monkeypatch):
    _env(monkeypatch)
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    with patch("booklint.cli.LLM", return_value=MockLLM(label="entailment")):
        main(
            [
                "predict",
                "--id",
                "x1",
                "--booklet",
                "does-not-exist.pdf",
                "--claim",
                "Etwas.",
            ]
        )
    data = json.loads(buf.getvalue())
    assert (
        data["id"] == "x1"
        and data["label"] == 1
        and data["evidence"] == []
        and "error" in data
    )


def _two_sentence_booklet():
    text = "Das Parlament hat die Vorlage 2019 beraten. Sie ist für alle Bürgerinnen und Bürger kostenlos und wird vom Bund ausgestellt."
    chunks = [
        Chunk(
            0,
            1,
            "Volksabstimmung vom 7. März 2021. Erläuterungen des Bundesrates.",
            "",
            "",
            "",
            0,
            60,
        ),
        Chunk(1, 3, text, "Vorlage 2", "Vorlage 2", "", 62, 62 + len(text)),
    ]
    return Booklet("two.pdf", "1" * 64, "de", 5, chunks, 0.0)


def _pipe(unit="sentence", label="entailment"):
    b = _two_sentence_booklet()
    pipe = Pipeline(
        MockLLM(label=label),
        Options(scope="booklet", decompose=False, fewshot=0, evidence_unit=unit),
    )
    pipe._booklets["two.pdf"] = (b, Retriever(b))
    return pipe


def test_evidence_unit_sentence_vs_paragraph():
    claim = "Die E-ID ist kostenlos und wird vom Bund ausgestellt."
    sent = _pipe("sentence").predict(claim, "two.pdf", "de", case_id="s")
    para = _pipe("paragraph").predict(claim, "two.pdf", "de", case_id="p")
    assert sent["evidence"][0]["text"].startswith("Sie ist für alle")
    assert para["evidence"][0]["text"].startswith("Das Parlament hat")
    assert para["evidence"][0]["page"] == sent["evidence"][0]["page"] == 3


def test_evidence_fallback_uses_retrieved_passage_not_cover(monkeypatch):
    monkeypatch.setattr(pipeline_module.sentences, "select", lambda *a, **k: [])

    class NoCiteLLM(MockLLM):
        def chat(self, messages, usage, purpose, model=None, **params):
            rec = super().chat(messages, usage, purpose, model, **params)
            if purpose != "translate":
                rec["content"] = json.dumps({"evidence": [], "label": self.label})
            return rec

    b = _two_sentence_booklet()
    pipe = Pipeline(
        NoCiteLLM("contradiction"), Options(scope="booklet", decompose=False, fewshot=0)
    )
    pipe._booklets["two.pdf"] = (b, Retriever(b))
    out = pipe.check("Die E-ID kostet 100 Franken und ist Pflicht.", "two.pdf", "de")
    assert out["label"] == 2
    assert out["evidence"][0]["page"] == 3
    assert "Volksabstimmung" not in out["evidence"][0]["text"]


def _proposal_booklet():
    texts = {
        "Erste Vorlage: Liegenschaftssteuer": "Die Kantone dürfen eine Liegenschaftssteuer auf Zweitliegenschaften erheben. Der Eigenmietwert wird abgeschafft.",
        "Zweite Vorlage: E-ID-Gesetz": "Die elektronische Identität ist freiwillig und kostenlos. Der Bund stellt die E-ID aus.",
    }
    chunks, pos = [], 0
    for group, text in texts.items():
        for n in range(8):
            t = f"{text} Abschnitt {n}."
            chunks.append(
                Chunk(
                    len(chunks),
                    1 + len(chunks) // 4,
                    t,
                    group,
                    group,
                    "",
                    pos,
                    pos + len(t),
                )
            )
            pos += len(t) + 2
    return Booklet("prop.pdf", "2" * 64, "de", 6, chunks, 0.0)


class VoteLLM(MockLLM):
    def chat(self, messages, usage, purpose, model=None, **params):
        if purpose == "translate-vote":
            self.calls.append((purpose, messages))
            usage.add(Call(purpose, "mock-apertus", 40, 10, 0.01, False))
            return {
                "content": "Bundesgesetz über die elektronische Identität (E-ID-Gesetz)"
            }
        return super().chat(messages, usage, purpose, model, **params)


def test_foreign_vote_title_is_translated_before_locating_the_proposal():
    b = _proposal_booklet()
    llm = VoteLLM("entailment")
    pipe = Pipeline(llm, Options(scope="vote", decompose=False, fewshot=0))
    pipe._booklets["prop.pdf"] = (b, Retriever(b))
    out = pipe.check(
        "La E-ID est gratuite.",
        "prop.pdf",
        vote="Loi fédérale sur les services d'identification électronique (loi sur l'e-ID)",
    )
    assert [p for p, _ in llm.calls].count("translate-vote") == 1
    assert (
        "French"
        in llm.calls[[p for p, _ in llm.calls].index("translate-vote")][1][-1][
            "content"
        ]
    )
    assert out["vote_translation"].startswith("Bundesgesetz")
    assert out["proposal"] == "Zweite Vorlage: E-ID-Gesetz"


def test_vote_title_in_booklet_language_is_not_translated():
    b = _proposal_booklet()
    llm = VoteLLM("entailment")
    pipe = Pipeline(llm, Options(scope="vote", decompose=False, fewshot=0))
    pipe._booklets["prop.pdf"] = (b, Retriever(b))
    out = pipe.check("Die E-ID ist kostenlos.", "prop.pdf", "de", vote="E-ID-Gesetz")
    assert "translate-vote" not in [p for p, _ in llm.calls]
    assert out["vote_translation"] is None
    assert out["proposal"] == "Zweite Vorlage: E-ID-Gesetz"


def test_detect_language_italian_and_quoted_titles():
    assert (
        detect_language(
            "Se la votazione verrà approvata, l’aliquota ordinaria dell’IVA salirà dal 7,7% all’8,1%."
        )
        == "it"
    )
    assert (
        detect_language(
            "Se il voto viene approvato, la NASA lancerà una nuova missione su Marte entro il 2030."
        )
        == "it"
    )
    assert (
        detect_language(
            "Il Consiglio federale invita il popolo a respingere il decreto federale sull’imposta cantonale."
        )
        == "it"
    )
    assert (
        detect_language(
            "Der Bundesrat spricht sich für die Annahme der Volksinitiative « Oui à la protection des enfants et des jeunes contre la publicité pour le tabac » aus."
        )
        == "de"
    )
    assert (
        detect_language("La proposition entraînera une augmentation de la TVA.") == "fr"
    )
    assert detect_language("Étape d'aménagement 2023 des routes nationales") == "fr"


def test_booklet_root_resolves_relative_paths(monkeypatch):
    monkeypatch.setenv("BOOKLET_ROOT", "/work")
    case = normalize_case(
        {
            "id": "c",
            "booklet": {"path": "booklets/2024_11_24_de.pdf"},
            "claim": {"text": "x"},
        }
    )
    assert case["booklet"].replace("\\", "/") == "/work/booklets/2024_11_24_de.pdf"
    url = "https://www.bk.admin.ch/x.pdf"
    assert normalize_case({"booklet_url": url, "claim": "x"})["booklet"] == url
    monkeypatch.delenv("BOOKLET_ROOT")
    assert (
        normalize_case({"booklet": {"path": "booklets/a.pdf"}, "claim": "x"})["booklet"]
        == "booklets/a.pdf"
    )


def test_efficiency_reports_input_tokens_and_p95():
    preds = [
        {
            "metrics": {
                "input_tokens": 100 * i,
                "output_tokens": 5,
                "inference_time_ms": 10 * i,
            }
        }
        for i in range(1, 21)
    ]
    e = efficiency(preds)
    assert e["input_tokens_sum"] == 100 * 210
    assert e["input_tokens_mean"] == 1050.0
    assert e["inference_ms_mean"] == 105.0
    assert e["inference_ms_p95"] == 190
    legacy = efficiency([{"usage": {"prompt_tokens": 7}, "latency_s": 0.25}])
    assert legacy["input_tokens_mean"] == 7 and legacy["inference_ms_mean"] == 250
