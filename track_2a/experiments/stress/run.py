"""Run booklint through the OST entrypoint on one half of the stress set and score it.

python experiments/stress/run.py <model> <dev|holdout> <A|B> <name> [--workers 2] [--no-cache] [-- extra CLI args]
-> runs/stress/<split>/<model>/<name>-<task>.jsonl and .summary.json
The scoring is the same as the stress set's own evaluation (macro-F1; OST evidence rule with the gold page as passage).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/stress-synth"
ENV = ROOT.parents[1] / "Hack_Apertus_Apertool" / "intern" / ".env"


def norm(text):
    text = unicodedata.normalize("NFKC", text or "").replace("­", "")
    text = re.sub(r"(\w) ?-\s*\n\s*(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def macro_f1(gold, pred):
    f = []
    for c in (0, 1, 2):
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    return sum(f) / 3


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))] if xs else None


def score(rows, preds):
    gold = [r["entailment_label"] for r in rows]
    pred = [preds[r["id"]]["label"] for r in rows]
    ev = [
        any(
            len(norm(e.get("text"))) <= 5000
            and fuzz.partial_ratio(norm(e.get("text")), norm(r["reference_string"]))
            >= 90
            for e in (preds[r["id"]].get("evidence") or [])[:5]
            if e.get("text")
        )
        for r in rows
        if r["entailment_label"] != 1
    ]
    tok = [preds[r["id"]].get("metrics", {}).get("input_tokens", 0) for r in rows]
    ms = [preds[r["id"]].get("metrics", {}).get("inference_time_ms", 0) for r in rows]
    conf = Counter(f"{g}->{p}" for g, p in zip(gold, pred) if g != p)
    return {
        "n": len(rows),
        "macro_f1": round(macro_f1(gold, pred), 4),
        "evidence_score": round(sum(ev) / len(ev), 4) if ev else None,
        "input_tokens_mean": round(sum(tok) / len(tok)),
        "ms_mean": round(sum(ms) / len(ms)),
        "ms_p95": p95(ms),
        "errors": dict(conf.most_common()),
    }


def main():
    argv = sys.argv[1:]
    extra = argv[argv.index("--") + 1 :] if "--" in argv else []
    argv = argv[: argv.index("--")] if "--" in argv else argv
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("split", choices=["dev", "holdout", "dev2", "holdout2"])
    ap.add_argument("task", choices=["A", "B"])
    ap.add_argument("name")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--src", default=str(ROOT / "src"), help="booklint source tree (e.g. an older commit's worktree)")
    ap.add_argument("--opts", default="", help="JSON object of Options fields (BOOKLINT_OPTIONS)")
    a = ap.parse_args(argv)
    sp = json.loads((D / "split.json").read_text())
    suffix = "-b" if a.split.endswith("2") else ""  # second set (14b): clean-b.jsonl, cases_A-b.jsonl
    dates = set(sp["set_b"][a.split] if suffix else sp[a.split])
    rows = [json.loads(x) for x in (D / f"clean{suffix}.jsonl").open(encoding="utf-8")]
    rows = [r for r in rows if r["booklet_date"] in dates]
    keep = {f"{r['id']}-{a.task}" for r in rows}
    cases = [
        x
        for x in (D / f"cases_{a.task}{suffix}.jsonl").open(encoding="utf-8")
        if json.loads(x)["id"] in keep
    ]
    out = ROOT / "runs/stress" / a.split / a.model / f"{a.name}-{a.task}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not a.score_only:
        env = dict(
            os.environ,
            PYTHONPATH=a.src,
            BOOKLINT_ENV_FILE=str(ENV),
            BOOKLET_ROOT=str(D / "booklets"),
            PYTHONIOENCODING="utf-8",
            BOOKLINT_OPTIONS=a.opts,
        )
        for k in ("BASE_URL", "API_KEY"):
            env.pop(k, None)
        t0 = time.time()
        procs, parts = [], []
        for k in range(a.workers):
            with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
                f.writelines(cases[k :: a.workers])
            part = out.with_name(f"{out.stem}.part{k}.jsonl")
            parts.append(part)
            cmd = [sys.executable, "-m", "booklint", "--input", f.name, "--output", str(part), "--model", a.model]
            cmd += (["--no-cache"] if a.no_cache else []) + extra
            procs.append(subprocess.Popen(cmd, env=env, cwd=str(ROOT), stderr=subprocess.DEVNULL))
        rcs = [pr.wait() for pr in procs]
        with out.open("w", encoding="utf-8") as fo:
            for part in parts:
                fo.write(part.read_text(encoding="utf-8"))
                part.unlink()
        print("exit", rcs, round(time.time() - t0), "s")
    preds = {}
    for line in out.open(encoding="utf-8"):
        p = json.loads(line)
        preds[p["id"].rsplit("-", 1)[0]] = p
    s = score(rows, preds)
    s.update(
        {
            "model": a.model,
            "split": a.split,
            "task": a.task,
            "name": a.name,
            "extra": extra,
            "opts": a.opts,
        }
    )
    out.with_suffix(".summary.json").write_text(
        json.dumps(s, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(s))


if __name__ == "__main__":
    main()
