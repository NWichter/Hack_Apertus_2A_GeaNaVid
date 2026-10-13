"""Input variants the hidden OST cases might use besides slide 24, and the output contract of `predict`."""

import io
import json
import sys
from unittest.mock import patch

from booklint.cli import main, normalize_case, read_cases

from test_slide25 import MockLLM

SLIDE25 = {"id", "label", "label_name", "evidence", "metrics"}


def _env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake-test-endpoint")
    monkeypatch.setenv("LLM_API_KEY", "fake-api-key")


def test_nested_and_flat_cases_give_the_same_shape():
    nested = {
        "id": "case-0042",
        "booklet": {"path": "https://example.org/b_de.pdf"},
        "vote": "Titel",
        "claim": {"text": "Eine Behauptung."},
    }
    flat = {
        "id": "case-0042",
        "booklet_path": "https://example.org/b_de.pdf",
        "vote": "Titel",
        "claim": "Eine Behauptung.",
    }
    url = {
        "id": "case-0042",
        "booklet": {"url": "https://example.org/b_de.pdf"},
        "vote": {"title": "Titel"},
        "claim": {"text": "Eine Behauptung."},
    }
    plain = {
        "id": "case-0042",
        "booklet": "https://example.org/b_de.pdf",
        "vote": "Titel",
        "hypothesis": "Eine Behauptung.",
    }
    shapes = [normalize_case(c) for c in (nested, flat, url, plain)]
    for s in shapes:
        assert (s["id"], s["claim"], s["booklet"], s["vote"]) == (
            "case-0042",
            "Eine Behauptung.",
            "https://example.org/b_de.pdf",
            "Titel",
        )


def test_beginner_variants_language_and_int_id():
    c = normalize_case(
        {
            "id": 7,
            "reference": {"text": "Referenz.", "page": "12"},
            "claim": {"text": "Claim.", "language": "FR"},
        }
    )
    assert (c["id"], c["reference"], c["claim_lang"]) == ("7", "Referenz.", "fr")
    c = normalize_case(
        {
            "id": "b",
            "premise": ["Absatz eins.", {"text": "Absatz zwei."}],
            "claim": "Claim.",
        }
    )
    assert c["reference"] == "Absatz eins.\n\nAbsatz zwei."
    assert (
        normalize_case(
            {"id": "c", "reference_string": "R.", "claim": "C.", "claim_language": "xx"}
        )["claim_lang"]
        is None
    )


def test_read_cases_bom_wrapper_crlf_and_broken_line(tmp_path):
    one = {"id": "a", "reference": {"text": "R."}, "claim": {"text": "C."}}
    wrapped = tmp_path / "wrapped.json"
    wrapped.write_bytes(
        ("﻿" + json.dumps({"cases": [one, dict(one, id="b")]})).encode("utf-8")
    )
    assert [c["id"] for c in read_cases(str(wrapped))] == ["a", "b"]
    jsonl = tmp_path / "cases.jsonl"
    jsonl.write_bytes(
        (
            "﻿"
            + json.dumps(one)
            + "\r\n"
            + '{"id": "bad", "claim": {"text": "x"\r\n'
            + json.dumps(dict(one, id="c"))
            + "\r\n"
        ).encode("utf-8")
    )
    cases = read_cases(str(jsonl))
    assert [c["id"] for c in cases] == ["a", "bad", "c"]
    assert cases[1]["error"] and not cases[0]["error"]


def test_predict_output_is_jsonl_slide25_for_every_variant(monkeypatch, tmp_path):
    _env(monkeypatch)
    cases = [
        {
            "id": "nested",
            "reference": {"text": "Die E-ID ist freiwillig und kostenlos.", "page": 4},
            "claim": {"text": "Die E-ID ist kostenlos."},
        },
        {
            "id": "flat",
            "reference_string": "Die E-ID ist freiwillig und kostenlos.",
            "claim": "Die E-ID ist kostenlos.",
        },
        {
            "id": 3,
            "premise": "Die E-ID ist freiwillig und kostenlos.",
            "hypothesis": "Die E-ID ist kostenlos.",
        },
        {
            "id": "missing-pdf",
            "booklet": {"path": str(tmp_path / "nope.pdf")},
            "vote": {"title": "x"},
            "claim": {"text": "C."},
        },
        "not an object",
    ]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    out = tmp_path / "preds.jsonl"
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    with patch("booklint.cli.LLM", return_value=MockLLM(label="entailment")):
        main(["predict", "--case", str(path), "-o", str(out)])
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5
    rows = [json.loads(line) for line in lines]
    assert [r["id"] for r in rows] == ["nested", "flat", "3", "missing-pdf", ""]
    for r in rows:
        assert SLIDE25 <= set(r) <= SLIDE25 | {"error"}
        assert (
            r["label"] in (0, 1, 2)
            and r["label_name"]
            == ["entailment", "neutral", "contradiction"][r["label"]]
        )
        assert set(r["metrics"]) == {
            "input_tokens",
            "output_tokens",
            "inference_time_ms",
        }
        assert all(isinstance(v, int) for v in r["metrics"].values())
        assert all(
            set(e) == {"page", "text"} and (e["page"] is None or isinstance(e["page"], int)) and e["text"]
            for e in r["evidence"]
        )
    assert rows[0]["label"] == 0 and {e["page"] for e in rows[0]["evidence"]} == {None}
    # task B without a page on the reference: "page": null, as OST's Solution API Guide asks
    assert rows[1]["evidence"] and all(e["page"] is None for e in rows[1]["evidence"])
    assert rows[3]["label"] == 1 and rows[3]["evidence"] == [] and "error" in rows[3]


def test_single_case_to_a_pipe_is_one_line_and_json_list_format(monkeypatch, tmp_path):
    _env(monkeypatch)
    case = {
        "id": "one",
        "reference": {"text": "Die E-ID ist kostenlos."},
        "claim": {"text": "Die E-ID ist kostenlos."},
    }
    path = tmp_path / "case.json"
    path.write_text(json.dumps(case), encoding="utf-8")
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    with patch("booklint.cli.LLM", return_value=MockLLM(label="entailment")):
        main(["predict", "--case", str(path)])
    assert (
        len(buf.getvalue().splitlines()) == 1
        and json.loads(buf.getvalue())["id"] == "one"
    )
    out = tmp_path / "preds.json"
    with patch("booklint.cli.LLM", return_value=MockLLM(label="entailment")):
        main(["predict", "--case", str(path), "--format", "json", "-o", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data[0]["id"] == "one"


def test_ost_entrypoint_input_output_and_env_names(monkeypatch, tmp_path):
    """OST runs `<entrypoint> --input /data/cases.jsonl --output /output/predictions.jsonl` with BASE_URL / API_KEY."""
    for k in ("LLM_BASE_URL", "LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("BASE_URL", "http://fake-proxy")
    monkeypatch.setenv("API_KEY", "fake-team-key")
    monkeypatch.setenv("BOOKLINT_ENV_FILE", str(tmp_path / "none.env"))
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        json.dumps({"id": "v1.1-row-1-B", "reference": {"text": "Die E-ID ist kostenlos.", "language": "de"},
                    "vote": "E-ID", "claim": {"text": "La E-ID est gratuite.", "language": "fr"}}) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "output" / "predictions.jsonl"
    with patch("booklint.cli.LLM", return_value=MockLLM(label="entailment")) as llm:
        main(["--input", str(cases), "--output", str(out)])
    settings = llm.call_args[0][0]
    assert (settings.base_url, settings.api_key) == ("http://fake-proxy", "fake-team-key")
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["id"] == "v1.1-row-1-B" and row["label"] == 0


def test_resolve_model_maps_size_to_the_endpoint_name():
    from types import SimpleNamespace

    from booklint import llm as llm_module

    ids = ["swiss-ai/Apertus-v1.5-70B-Instruct", "swiss-ai/Apertus-v1.5-8B-Instruct", "other/model-8b"]

    class Client:
        base_url = "http://x"

        def with_options(self, **_):
            return SimpleNamespace(models=SimpleNamespace(list=lambda: SimpleNamespace(data=[SimpleNamespace(id=i) for i in ids])))

    llm_module._RESOLVED.clear()
    assert llm_module.resolve_model(Client(), "apertus-v1.5-8b") == "swiss-ai/Apertus-v1.5-8B-Instruct"
    llm_module._RESOLVED.clear()
    assert llm_module.resolve_model(Client(), "apertus-v1.5-70b") == "swiss-ai/Apertus-v1.5-70B-Instruct"
    llm_module._RESOLVED.clear()
    assert llm_module.resolve_model(Client(), "swiss-ai/Apertus-v1.5-8B-Instruct") == "swiss-ai/Apertus-v1.5-8B-Instruct"
