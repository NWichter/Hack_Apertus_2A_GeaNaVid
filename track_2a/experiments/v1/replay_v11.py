"""The reported runs on OST v1.1 (v1.0 without 7 faulty rows, data/v1/v1.1-removed.json), 0 new calls.

1. Defaults and Beginner runs are replayed from the response cache with the options in their config, on
   <split>_v11 (full summary incl. evidence; a cache miss is an error).
2. Every run is also filtered: the stored v1.0 predictions without the removed rows (labels and tokens
   cannot change). The whole-booklet baseline is only filtered: its page texts changed after 2026-10-02
   (ingest clean-up), so its prompts are no longer in the cache.
Output: runs/v1/<split>_v11/<model>/<name>.* and runs/v1/v1.1-filtered.json
python experiments/v1/replay_v11.py [--no-replay]
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from booklint.metrics import macro_f1  # noqa: E402
from run import load  # noqa: E402

MODELS = ("apertus-v1.5-8b", "apertus-v1.5-70b")
REPLAY = {
    "test": ["final-v2", "beginner-default"],
    "dev_s": ["final-v2"],
    "dev_rest": ["final-v2"],
}
FILTER = {
    "test": ["baseline", "final-v2", "beginner-default"],
    "dev_s": ["baseline", "final-v2"],
    "dev_rest": ["final-v2"],
}


def replay():
    for split, names in REPLAY.items():
        for model in MODELS:
            for name in names:
                config = ROOT / "runs" / "v1" / split / model / f"{name}.config.json"
                opts = json.loads(config.read_text(encoding="utf-8"))["options"]
                cmd = [
                    sys.executable,
                    str(ROOT / "experiments" / "v1" / "run.py"),
                    "--split",
                    f"{split}_v11",
                    "--model",
                    model,
                    "--name",
                    name,
                    "--opts",
                    json.dumps(opts),
                    "--offline",
                    "--workers",
                    "4",
                ]
                subprocess.run(cmd, check=True, cwd=ROOT)


def filtered():
    removed = set(
        json.loads(
            (ROOT / "data" / "v1" / "v1.1-removed.json").read_text(encoding="utf-8")
        )["removed"]
    )
    out = {}
    for split, names in FILTER.items():
        gold = {r["id"]: int(r["entailment_label"]) for r in load(split)}
        for model in MODELS:
            for name in names:
                path = ROOT / "runs" / "v1" / split / model / f"{name}.jsonl"
                preds = [
                    p
                    for p in map(json.loads, path.open(encoding="utf-8"))
                    if p["id"] not in removed
                ]
                f1 = macro_f1(
                    [gold[p["id"]] for p in preds],
                    [int(p["entailment_label"]) for p in preds],
                )[0]
                tokens = sum(p["usage"]["prompt_tokens"] for p in preds) / len(preds)
                out[f"{split}/{model}/{name}"] = {
                    "n": len(preds),
                    "macro_f1": round(f1, 4),
                    "input_tokens_mean": round(tokens, 1),
                }
                print(split, model, name, out[f"{split}/{model}/{name}"])
    (ROOT / "runs" / "v1" / "v1.1-filtered.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    if "--no-replay" not in sys.argv:
        replay()
    filtered()
