"""Check every SHA-256 the repository records for its data against the files on disk.

- data/manifest.json: OST v1.0, the derived splits, the edge cases;
- data/stress-synth/MANIFEST.json and MANIFEST-b.json: each manifest's own hash (MANIFEST*.sha256) and the hashes of
  the data files that were copied into the repository (set b files carry the suffix "-b"); booklet PDFs only if they
  were downloaded (git-ignored).

Line endings matter: .gitattributes marks these files -text, so a clone on Windows or Linux has the same bytes.
python experiments/check_hashes.py     (exit code 1 on any mismatch)
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STRESS = DATA / "stress-synth"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(obj, key=""):
    if isinstance(obj, dict):
        if isinstance(obj.get("sha256"), str):
            yield key, obj
        for k, v in obj.items():
            yield from _walk(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, key)


def checks():
    """(label, expected, actual or None if the file is absent and optional)."""
    out = []
    man = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    for name, entry in _walk(man):
        path = next(
            (
                p
                for p in (
                    DATA / (entry.get("path") or name),
                    DATA / "v1" / name,
                    DATA / name,
                )
                if p.is_file()
            ),
            None,
        )
        out.append(
            (
                f"data/manifest.json: {name}",
                entry["sha256"],
                sha(path) if path else "missing",
            )
        )
    for suffix in ("", "-b"):
        manifest = STRESS / f"MANIFEST{suffix}.json"
        recorded = (
            (STRESS / f"MANIFEST{suffix}.sha256").read_text(encoding="utf-8").split()[0]
        )
        out.append((f"{manifest.name} (own hash)", recorded, sha(manifest)))
        m = json.loads(manifest.read_text(encoding="utf-8"))
        for name, entry in m["files"].items():
            stem, dot, ext = name.rpartition(".")
            path = STRESS / (f"{stem}{suffix}.{ext}" if suffix else name)
            if path.is_file():
                out.append(
                    (f"{manifest.name}: {path.name}", entry["sha256"], sha(path))
                )
        for name, digest in m["booklets"].items():
            pdf = STRESS / "booklets" / name
            out.append(
                (
                    f"{manifest.name}: booklets/{name}",
                    digest,
                    sha(pdf) if pdf.is_file() else None,
                )
            )
    return out


def main():
    bad = 0
    n = 0
    skipped = 0
    for label, want, got in checks():
        if got is None:
            skipped += 1
            continue
        n += 1
        if want != got:
            bad += 1
            print("MISMATCH", label, want[:12], got[:12])
    print(f"{n} hashes checked, {bad} mismatches, {skipped} optional PDFs not present")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
