"""Tests for OST Slide 25 specification conformance and Beginner/Advanced dual task compatibility."""

import io
import json
import math
import sys
from unittest.mock import patch

import pytest

from booklint.cli import main
from booklint.ingest import Booklet, Chunk
from booklint.llm import Call
from booklint.pipeline import Options, Pipeline, format_slide25
from booklint.retrieve import Retriever


def _logprobs(content, label):
    pre, post = content.split('"label": "')
    return [
        {"token": pre + '"label": "', "top": [[pre + '"label": "', 0.0]]},
        {"token": post, "top": [[label[:3], math.log(0.99)], ["xyz", math.log(0.01)]]},
    ]


class MockLLM:
    model = "mock-apertus"

    def __init__(self, label="entailment"):
        self.label = label
        self.calls = []

    def chat(self, messages, usage, purpose, model=None, **params):
        self.calls.append((purpose, messages))
        if purpose == "translate":
            return {"content": "Translated claim"}
        evidence = [] if self.label == "neutral" else [1]
        content = json.dumps({"evidence": evidence, "label": self.label})
        usage.add(Call(purpose, "mock-apertus", 150, 25, 0.02, False))
        return {"content": content, "logprobs": _logprobs(content, self.label)}


def _sample_booklet():
    paras = [
        ("Vorlage 1", "Die Kantone dürfen eine Liegenschaftssteuer auf Zweitliegenschaften erheben."),
        ("Vorlage 2", "Die elektronische Identität E-ID ist freiwillig und für alle Bürger kostenlos."),
    ]
    chunks, pos = [], 0
    for page, (heading, text) in enumerate(paras, start=1):
        chunks.append(
            Chunk(len(chunks), page, text, heading, heading, "", pos, pos + len(text))
        )
        pos += len(text) + 2
    return Booklet("test.pdf", "0" * 64, "de", 5, chunks, 0.0)


# ==============================================================================
# 1. Slide 25 Root Keys and Types
# ==============================================================================

@pytest.mark.parametrize("label,expected_int", [
    ("entailment", 0),
    ("neutral", 1),
    ("contradiction", 2),
])
def test_slide25_schema_and_root_keys(label, expected_int):
    llm = MockLLM(label=label)
    pipe = Pipeline(llm, Options(scope="booklet", decompose=False, fewshot=0))
    b = _sample_booklet()
    pipe._booklets["test.pdf"] = (b, Retriever(b))

    raw_out = pipe.check(
        claim="Die elektronische Identität ist kostenlos.",
        booklet_source="test.pdf",
        claim_lang="de",
        case_id="case-123",
    )
    s25 = format_slide25(raw_out, case_id="case-123")

    # Strict Root Keys
    assert set(s25.keys()) == {"id", "label", "label_name", "evidence", "metrics"}

    # ID
    assert isinstance(s25["id"], str)
    assert s25["id"] == "case-123"

    # Label & Label Name
    assert isinstance(s25["label"], int)
    assert s25["label"] == expected_int
    assert isinstance(s25["label_name"], str)
    assert s25["label_name"] == label

    # Evidence
    assert isinstance(s25["evidence"], list)
    if expected_int == 1:
        # OST allows empty evidence for neutral; we always return [] there.
        assert s25["evidence"] == []
    else:
        assert len(s25["evidence"]) > 0
        for ev in s25["evidence"]:
            assert set(ev.keys()) == {"page", "text"}
            assert isinstance(ev["page"], int)
            assert isinstance(ev["text"], str)
            assert len(ev["text"]) > 0

    # Metrics
    assert set(s25["metrics"].keys()) == {"input_tokens", "output_tokens", "inference_time_ms"}
    assert isinstance(s25["metrics"]["input_tokens"], int)
    assert isinstance(s25["metrics"]["output_tokens"], int)
    assert isinstance(s25["metrics"]["inference_time_ms"], int)
    assert s25["metrics"]["input_tokens"] >= 0
    assert s25["metrics"]["output_tokens"] >= 0
    assert s25["metrics"]["inference_time_ms"] >= 0


# ==============================================================================
# 2. Beginner Task (given --reference / reference)
# ==============================================================================

def test_beginner_task_standalone_reference():
    """Beginner task does not provide a booklet, only a reference text passage."""
    llm = MockLLM(label="entailment")
    pipe = Pipeline(llm, Options(decompose=False, fewshot=0))

    ref = (
        "Die Vorlage betrifft die elektronische Identität. "
        "Die elektronische Identität E-ID ist freiwillig und für alle Bürger kostenlos."
    )
    claim = "Die E-ID ist freiwillig."

    s25 = pipe.predict(claim=claim, gold_reference=ref, case_id="beg-01")

    assert set(s25.keys()) == {"id", "label", "label_name", "evidence", "metrics"}
    assert s25["id"] == "beg-01"
    assert s25["label"] == 0
    assert s25["label_name"] == "entailment"
    assert len(s25["evidence"]) > 0
    assert s25["evidence"][0]["page"] >= 1
    assert "freiwillig" in s25["evidence"][0]["text"]
    assert s25["metrics"]["input_tokens"] > 0


def test_beginner_task_neutral_has_empty_evidence():
    llm = MockLLM(label="neutral")
    pipe = Pipeline(llm, Options(decompose=False, fewshot=0))

    ref = "Hier steht etwas über die Besteuerung von Liegenschaften."
    claim = "Die E-ID ist kostenlos."

    s25 = pipe.predict(claim=claim, gold_reference=ref, case_id="beg-02")
    assert s25["label"] == 1
    assert s25["label_name"] == "neutral"
    assert s25["evidence"] == []


# ==============================================================================
# 3. Advanced Task (given booklet, vote, claim)
# ==============================================================================

def test_advanced_task_with_booklet_and_vote():
    llm = MockLLM(label="contradiction")
    pipe = Pipeline(llm, Options(scope="vote", decompose=False, fewshot=0))
    b = _sample_booklet()
    pipe._booklets["test.pdf"] = (b, Retriever(b))

    s25 = pipe.predict(
        claim="Die E-ID kostet 100 Franken.",
        booklet_source="test.pdf",
        vote="Vorlage 2",
        case_id="adv-01",
    )

    assert set(s25.keys()) == {"id", "label", "label_name", "evidence", "metrics"}
    assert s25["id"] == "adv-01"
    assert s25["label"] == 2
    assert s25["label_name"] == "contradiction"
    assert len(s25["evidence"]) > 0
    assert s25["evidence"][0]["page"] == 2
    assert "kostenlos" in s25["evidence"][0]["text"]


# ==============================================================================
# 4. CLI Execution: predict and check --json
# ==============================================================================

def test_cli_predict_beginner_json(monkeypatch):
    """Verify `booklint predict` CLI command output conforms strictly to OST Slide 25."""
    monkeypatch.setenv("LLM_BASE_URL", "http://fake-test-endpoint")
    monkeypatch.setenv("LLM_API_KEY", "fake-api-key")
    stdout_buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout_buf)

    with patch("booklint.cli.LLM", return_value=MockLLM(label="entailment")):
        main([
            "predict",
            "--id", "cli-beg-01",
            "--claim", "Die E-ID ist kostenlos.",
            "--reference", "Die elektronische Identität E-ID ist freiwillig und für alle Bürger kostenlos.",
            "--mode", "easy",
        ])

    output = stdout_buf.getvalue()
    data = json.loads(output)
    assert set(data.keys()) == {"id", "label", "label_name", "evidence", "metrics"}
    assert data["id"] == "cli-beg-01"
    assert data["label"] == 0
    assert data["label_name"] == "entailment"
    assert len(data["evidence"]) >= 1
    assert set(data["evidence"][0].keys()) == {"page", "text"}
    assert set(data["metrics"].keys()) == {"input_tokens", "output_tokens", "inference_time_ms"}


def test_cli_check_json(monkeypatch):
    """Verify `booklint check --json` output conforms strictly to OST Slide 25."""
    monkeypatch.setenv("LLM_BASE_URL", "http://fake-test-endpoint")
    monkeypatch.setenv("LLM_API_KEY", "fake-api-key")
    stdout_buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout_buf)

    with patch("booklint.cli.LLM", return_value=MockLLM(label="neutral")):
        main([
            "check",
            "--id", "cli-chk-neutral",
            "--claim", "Etwas ganz anderes.",
            "--reference", "Ein Text über ein anderes Thema.",
            "--json",
        ])

    output = stdout_buf.getvalue()
    data = json.loads(output)
    assert set(data.keys()) == {"id", "label", "label_name", "evidence", "metrics"}
    assert data["id"] == "cli-chk-neutral"
    assert data["label"] == 1
    assert data["label_name"] == "neutral"
    assert data["evidence"] == []
    assert set(data["metrics"].keys()) == {"input_tokens", "output_tokens", "inference_time_ms"}


def test_cli_predict_reads_ost_case_format(monkeypatch, tmp_path):
    """Input as on OST slide 24: nested claim/reference objects, one object or JSONL."""
    monkeypatch.setenv("LLM_BASE_URL", "http://fake-test-endpoint")
    monkeypatch.setenv("LLM_API_KEY", "fake-api-key")
    case = {"id": "case-0043", "reference": {"text": "Die E-ID ist freiwillig und kostenlos."},
            "claim": {"text": "Die E-ID ist kostenlos."}}
    single = tmp_path / "case.json"
    single.write_text(json.dumps(case), encoding="utf-8")
    many = tmp_path / "cases.jsonl"
    many.write_text("\n".join(json.dumps(dict(case, id=f"c{i}")) for i in range(2)), encoding="utf-8")

    for path, ids in ((single, ["case-0043"]), (many, ["c0", "c1"])):
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        with patch("booklint.cli.LLM", return_value=MockLLM(label="entailment")):
            main(["predict", "--case", str(path)])
        text = buf.getvalue().strip()
        out = [json.loads(text)] if len(ids) == 1 else [json.loads(line) for line in text.splitlines()]
        assert [o["id"] for o in out] == ids
        for o in out:
            assert set(o) == {"id", "label", "label_name", "evidence", "metrics"}
            assert o["label"] == 0 and o["evidence"]


def test_run_rows_reads_nested_and_flat_cases():
    from booklint.cli import run_rows

    b = _sample_booklet()
    pipe = Pipeline(MockLLM(label="contradiction"), Options(scope="booklet", decompose=False, fewshot=0))
    pipe._booklets["test.pdf"] = (b, Retriever(b))
    rows = [
        {"id": "adv", "booklet": {"path": "test.pdf"}, "vote": "Vorlage 2", "claim": {"text": "Die E-ID kostet 100 Franken."}},
        {"id": "beg", "reference": {"text": "Die E-ID ist kostenlos."}, "claim": {"text": "Die E-ID kostet etwas."}},
        {"id": "flat", "booklet_url": "test.pdf", "claim": "Die E-ID kostet 100 Franken.", "claim_language": "de"},
    ]
    out = run_rows(pipe, rows, 1)
    assert [o["id"] for o in out] == ["adv", "beg", "flat"]
    for o in out:
        assert "error" not in o
        assert o["label"] == 2 and o["evidence"]
