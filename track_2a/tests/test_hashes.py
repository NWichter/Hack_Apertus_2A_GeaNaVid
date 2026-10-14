"""Recorded SHA-256 of the data files must match the checked-out bytes (guards against CRLF conversion)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "check_hashes", ROOT / "experiments" / "check_hashes.py"
)
check_hashes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_hashes)


def test_recorded_hashes_match():
    results = [
        (label, want, got)
        for label, want, got in check_hashes.checks()
        if got is not None
    ]
    assert len(results) >= 15
    bad = [label for label, want, got in results if want != got]
    assert not bad, bad
