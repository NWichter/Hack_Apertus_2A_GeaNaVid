"""What is OST's baseline_score? Compare it with our whole-booklet baseline run (per row)."""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
NAMES = ["entailment", "neutral", "contradiction"]


def main(split, model, name):
    rows = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "data" / "v1" / f"{split}.jsonl").open(encoding="utf-8")}
    preds = [json.loads(l) for l in (ROOT / "runs" / "v1" / split / model / f"{name}.jsonl").open(encoding="utf-8")]
    bs, pmax, pgold, correct, ent = [], [], [], [], []
    for p in preds:
        r = rows[p["id"]]
        pr = p.get("raw_probs")
        if not pr:
            continue
        bs.append(r["baseline_score"])
        pmax.append(max(pr.values()))
        pgold.append(pr[NAMES[r["entailment_label"]]])
        correct.append(p["entailment_label"] == r["entailment_label"])
        ent.append(-sum(v * np.log(v + 1e-12) for v in pr.values()))
    bs = np.array(bs)
    out = {
        "n": len(bs),
        "corr_baseline_score_vs_our_pmax": round(float(np.corrcoef(bs, pmax)[0, 1]), 3),
        "corr_vs_our_p_gold": round(float(np.corrcoef(bs, pgold)[0, 1]), 3),
        "corr_vs_our_correct": round(float(np.corrcoef(bs, np.array(correct, float))[0, 1]), 3),
        "baseline_score_mean_when_we_are_right": round(float(bs[np.array(correct)].mean()), 4),
        "baseline_score_mean_when_we_are_wrong": round(float(bs[~np.array(correct)].mean()), 4),
        "our_pmax_mean": round(float(np.mean(pmax)), 4),
        "share_bs_ge_0.6": round(float((bs >= 0.6).mean()), 3),
        "baseline_score_min": round(float(bs.min()), 4),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(*sys.argv[1:4])
