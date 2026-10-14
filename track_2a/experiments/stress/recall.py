"""Retrieval only (translations from the response cache): is the gold page among the hits? Dev half of the stress set.
python experiments/stress/recall.py <model> [k=5] [section_boost=1.5] ...
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
D = ROOT / "data/stress-synth"
os.environ.setdefault(
    "BOOKLINT_ENV_FILE",
    str(ROOT.parents[1] / "Hack_Apertus_Apertool" / "intern" / ".env"),
)
os.environ.pop("BASE_URL", None)
os.environ.pop("API_KEY", None)

from booklint.config import Settings  # noqa: E402
from booklint.llm import LLM, Usage  # noqa: E402
from booklint.pipeline import Options, Pipeline, committee_terms  # noqa: E402
from booklint.proposal import locate  # noqa: E402
from booklint.textnorm import detect_language  # noqa: E402


def main():
    model = sys.argv[1]
    opts = {}
    for kv in sys.argv[2:]:
        k, v = kv.split("=")
        opts[k] = type(getattr(Options(), k))(v)
    split = opts.pop("split", "dev") if "split" in opts else "dev"
    pipe = Pipeline(LLM(Settings.from_env(model)), Options(**opts))
    dates = set(json.loads((D / "split.json").read_text())[split])
    rows = [
        r
        for r in map(json.loads, (D / "clean.jsonl").open(encoding="utf-8"))
        if r["booklet_date"] in dates
    ]
    hit = n = 0
    by = {}
    for r in rows:
        src = str(D / "booklets" / r["booklet_path"])
        b, retr = pipe.booklet(src)
        usage = Usage()
        tr = None
        if r["claim_language"] != b.language:
            tr = pipe._translate(r["claim"], r["claim_language"], b.language, usage)
            tr = committee_terms(r["claim"], tr, b.language)
        queries = [r["claim"]] + ([tr] if tr else [])
        region, _ = locate(b, r["vote"])
        hits, _, _ = pipe._hits(
            src, b, retr, queries, r["claim"], r["claim_language"], region, tr, usage
        )
        ok = r["reference_page"] in {b.chunks[i].page for i in hits}
        hit += ok
        n += 1
        key = r["label_name"]
        by.setdefault(key, [0, 0])
        by[key][0] += ok
        by[key][1] += 1
    print(
        model,
        opts,
        f"gold page in hits {hit}/{n} = {hit / n:.3f}",
        {k: f"{a}/{b}" for k, (a, b) in by.items()},
    )


if __name__ == "__main__":
    main()
