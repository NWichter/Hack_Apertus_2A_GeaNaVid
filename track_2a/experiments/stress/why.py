"""Why are dev-half stress errors wrong? Re-runs the errors of a stored run in-process (response cache: no new
calls if the code is unchanged) and prints gold page, retrieved pages, label, confidence and step.
python experiments/stress/why.py <model> <name>   (dev half, task A)
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
    str(ROOT / ".env"),
)
os.environ.pop("BASE_URL", None)
os.environ.pop("API_KEY", None)

from booklint.config import Settings  # noqa: E402
from booklint.llm import LLM  # noqa: E402
from booklint.pipeline import Options, Pipeline  # noqa: E402


def main():
    model, name = sys.argv[1], sys.argv[2]
    rows = {
        r["id"]: r for r in map(json.loads, (D / "clean.jsonl").open(encoding="utf-8"))
    }
    preds = [
        json.loads(x)
        for x in (ROOT / f"runs/stress/dev/{model}/{name}-A.jsonl").open(
            encoding="utf-8"
        )
    ]
    pipe = Pipeline(LLM(Settings.from_env(model)), Options())
    for p in preds:
        r = rows[p["id"].rsplit("-", 1)[0]]
        if p["label"] == r["entailment_label"]:
            continue
        out = pipe.check(
            r["claim"],
            str(D / "booklets" / r["booklet_path"]),
            r["claim_language"],
            "",
            r["vote"],
        )
        b, _ = pipe.booklet(str(D / "booklets" / r["booklet_path"]))
        pages = [b.chunks[i].page for i in out["retrieved_ids"]]
        hit_pages = [b.chunks[i].page for i in out["hits"]]
        print(
            f"{r['id']:28s} gold {r['entailment_label']} pred {out['label']} conf {out['confidence']} step {out['ladder_step']}"
            f" | gold p.{r['reference_page']} in hits {r['reference_page'] in hit_pages} in retrieved"
            f" {r['reference_page'] in pages} | hits {sorted(set(hit_pages))} | {r['phenomenon']} | {r['claim'][:80]}"
        )


if __name__ == "__main__":
    main()
