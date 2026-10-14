"""Synthetic edge cases: consistent gold labels, marked as synthetic, kept apart from OST v1.0."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
NAMES = {0: "entailment", 1: "neutral", 2: "contradiction"}


def _rows():
    return [
        json.loads(line)
        for line in (DATA / "edge_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_edge_cases_are_gold_pairs_marked_synthetic():
    rows = _rows()
    assert len(rows) == 24
    assert len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        assert (
            r["claim"]
            and r["reference_string"]
            and r["claim_language"]
            and r["reference_language"]
        )
        assert NAMES[r["label"]] == r["label_name"]
        assert "metrics" not in r
        assert (
            r["provenance"]["synthetic"] is True
            and r["provenance"]["reviewed"] is False
        )
        if r["label"] == 1:
            assert r["evidence"] == []
        else:
            assert r["evidence"] and all(
                set(e) == {"page", "text"} and e["text"] for e in r["evidence"]
            )
    assert {r["label"] for r in rows} == {0, 1, 2}


def test_edge_cases_not_mixed_into_ost_split():
    assert not (DATA / "v1" / "edge_cases.jsonl").exists()
    ids = {r["id"] for r in _rows()}
    for name in ("v1.0.jsonl", "dev.jsonl", "dev_s.jsonl", "test.jsonl"):
        for line in (DATA / "v1" / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                assert json.loads(line).get("id") not in ids


def test_no_stored_run_uses_edge_cases():
    runs = DATA.parent / "runs" / "v1"
    ids = {r["id"] for r in _rows()}
    claims = {r["claim"] for r in _rows()}
    split_ids = {}
    for split in ("test", "dev_s"):
        split_ids[split] = {
            json.loads(line)["id"]
            for line in (DATA / "v1" / f"{split}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        }
    for path in runs.glob("*/*/*.jsonl"):
        split = path.parts[-3]
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            assert row.get("id") not in ids, path
            claim = row.get("claim")
            claim = (
                claim.get("text") if isinstance(claim, dict) else claim
            )  # OST case format
            assert claim not in claims, path
            if split in split_ids:
                assert row.get("id") in split_ids[split], path
    for path in runs.glob("*/*/*.config.json"):
        assert "edge" not in path.read_text(encoding="utf-8"), path
