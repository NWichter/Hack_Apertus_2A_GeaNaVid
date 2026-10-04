"""Checks after the OST session of 2026-10-02 on the test split (runs/v1/test).

python experiments/v1/ost_checks.py replay     # stored default runs from the cache (0 calls): labels, evidence unit
python experiments/v1/ost_checks.py nolang     # default pipeline without claim_language (as in OST's input)
python experiments/v1/ost_checks.py breakdown  # stored runs broken down as on OST slide 28
python experiments/v1/ost_checks.py vote       # vote title from another language version of the same booklet
CACHE_DIR=<dir without llm/> python experiments/v1/ost_checks.py cold   # 50 test cases, no response cache, 1 worker
Output: runs/v1/test/ost-checks-<part>.json; nolang also writes runs/v1/test/<model>/default-nolang.*
"""

import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from booklint.config import Settings  # noqa: E402
from booklint.cli import run_rows  # noqa: E402
from booklint.llm import LLM, RETRIES, Usage, redact  # noqa: E402
from booklint.metrics import breakdown, efficiency, macro_f1  # noqa: E402
from booklint.pipeline import Options, Pipeline, foreign_title  # noqa: E402
from booklint.proposal import candidates, locate  # noqa: E402
from booklint.retrieval_eval import gold_chunks  # noqa: E402
from booklint.textnorm import detect_language, fold  # noqa: E402

TEST = ROOT / "runs" / "v1" / "test"
DEFAULT_RUNS = {
    "apertus-v1.5-8b": "final-v2",
    "apertus-v1.5-70b": "r1-secboost",
}
COLD_NAME = "cold50-v2"
BEGINNER_RUNS = {"apertus-v1.5-8b": "easy-fs3", "apertus-v1.5-70b": "easy"}


def load_rows():
    return [
        json.loads(line)
        for line in (ROOT / "data/v1/test.jsonl").open(encoding="utf-8")
    ]


def load_run(model, name):
    path = TEST / model / f"{name}.jsonl"
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def stored_options(model, name):
    return json.loads(
        (TEST / model / f"{name}.config.json").read_text(encoding="utf-8")
    )["options"]


def norm(text):
    return re.sub(r"[^0-9a-z]+", "", fold(text))


def offline(llm):
    def refuse(**_):
        raise RuntimeError("cache miss in an offline replay")

    llm.client.chat.completions.create = refuse
    return llm


def predict(pipeline, rows, workers, use_lang=True):
    for r in rows:
        pipeline.booklet(r["booklet_url"])

    def one(r):
        try:
            out = pipeline.check(
                r["claim"],
                r["booklet_url"],
                r["claim_language"] if use_lang else None,
                r["reference_string"],
                r.get("vote"),
            )
        except Exception as exc:
            out = {
                "entailment_label": 1,
                "label": 1,
                "label_name": "neutral",
                "evidence": [],
                "hits": [],
                "retrieved_ids": [],
                "error": redact(repr(exc))[:300],
                "ladder_step": "error",
                "usage": {
                    "llm_calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "llm_seconds": 0.0,
                },
            }
        out["id"] = r["id"]
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, rows))


def evidence_stats(pipeline, rows, preds):
    """E/C answers: does the first evidence item lie inside the gold section, is its page a gold page."""
    n = strict = lenient = any_inside = page = 0
    chars = []
    for r, p in zip(rows, preds):
        if p["label"] == 1 or not p["evidence"]:
            continue
        booklet, _ = pipeline.booklet(r["booklet_url"])
        ref = norm(r["reference_string"])
        gold_pages = {
            booklet.chunks[i].page for i in gold_chunks(booklet, r["reference_string"])
        }
        first = norm(p["evidence"][0]["text"])
        n += 1
        strict += len(first) >= 10 and first in ref
        lenient += len(first) >= 10 and first[:80] in ref
        any_inside += any(
            len(norm(e["text"])) >= 10 and norm(e["text"]) in ref for e in p["evidence"]
        )
        page += p["evidence"][0]["page"] in gold_pages
        chars.append(sum(len(e["text"]) for e in p["evidence"]))
    chars.sort()
    return {
        "ec_answers": n,
        "first_item_inside_gold": round(strict / n, 4),
        "first_item_first_80_chars_inside_gold": round(lenient / n, 4),
        "any_item_inside_gold": round(any_inside / n, 4),
        "first_item_on_gold_page": round(page / n, 4),
        "evidence_chars_median": chars[len(chars) // 2],
        "evidence_chars_mean": round(sum(chars) / len(chars)),
        "evidence_items_mean": round(
            sum(len(p["evidence"]) for p in preds if p["label"] != 1 and p["evidence"])
            / n,
            2,
        ),
    }


def replay():
    rows = load_rows()
    report = {}
    for model, name in DEFAULT_RUNS.items():
        stored = load_run(model, name)
        opts = stored_options(model, name)
        llm = offline(LLM(Settings.from_env(model)))
        res = {}
        for unit in ("sentence", "paragraph"):
            pipeline = Pipeline(llm, Options(**{**opts, "evidence_unit": unit}))
            preds = predict(pipeline, rows, 4)
            same_label = sum(
                p["label"] == s["entailment_label"] for p, s in zip(preds, stored)
            )
            gold = [int(r["entailment_label"]) for r in rows]
            res[unit] = {
                "macro_f1": round(macro_f1(gold, [p["label"] for p in preds])[0], 4),
                "labels_identical_to_stored_run": f"{same_label}/{len(rows)}",
                "errors": sum("error" in p for p in preds),
                "uncached_calls": sum(
                    p["usage"]["llm_calls"] - p["usage"].get("cached_calls", 0)
                    for p in preds
                ),
                **evidence_stats(pipeline, rows, preds),
            }
            if unit == "sentence":
                res[unit]["evidence_changed_vs_stored"] = sum(
                    [e["text"] for e in p["evidence"]]
                    != [e["text"] for e in s.get("evidence_sentences", [])]
                    for p, s in zip(preds, stored)
                    if p["label"] != 1
                )
        report[model] = {"run": name, **res}
        print(model, json.dumps(res, indent=1), flush=True)
    out = TEST / "ost-checks-replay.json"
    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def nolang():
    rows = load_rows()
    detected = Counter((r["claim_language"], detect_language(r["claim"])) for r in rows)
    report = {
        "claim_language_detection": {
            f"{g}->{d}": n for (g, d), n in sorted(detected.items())
        }
    }
    for model, name in DEFAULT_RUNS.items():
        opts = stored_options(model, name)
        llm = LLM(Settings.from_env(model))
        pipeline = Pipeline(llm, Options(**opts))
        t0 = time.perf_counter()
        preds = predict(pipeline, rows, 4, use_lang=False)
        wall = time.perf_counter() - t0
        gold = [
            gold_chunks(pipeline.booklet(r["booklet_url"])[0], r["reference_string"])
            for r in rows
        ]
        summary = breakdown(rows, preds, gold)
        stored = load_run(model, name)
        summary.update(
            {
                "model": model,
                "name": "default-nolang",
                "split": "test",
                "wall_s": round(wall, 1),
                "retries": dict(RETRIES),
                "workers": 4,
                "uncached_calls": sum(
                    p["usage"]["llm_calls"] - p["usage"].get("cached_calls", 0)
                    for p in preds
                ),
                "labels_changed_vs_with_language": sum(
                    p["label"] != s["entailment_label"] for p, s in zip(preds, stored)
                ),
                "rows_with_other_claim_language": sum(
                    p.get("claim_language") != r["claim_language"]
                    for p, r in zip(preds, rows)
                ),
            }
        )
        out = TEST / model
        with (out / "default-nolang.jsonl").open(
            "w", encoding="utf-8", newline="\n"
        ) as fh:
            for p in preds:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
        config = {
            "name": "default-nolang",
            "split": "test",
            "model": model,
            "options": asdict(Options(**opts)),
            "claim_language": "detected (not taken from the data)",
            "split_seed": 2026,
            "rows": len(rows),
            "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "command": " ".join(sys.argv),
        }
        (out / "default-nolang.config.json").write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (out / "default-nolang.summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        report[model] = {
            k: summary[k]
            for k in (
                "macro_f1",
                "ci95",
                "macro_f1_same",
                "macro_f1_cross",
                "tokens_mean",
                "input_tokens_mean",
                "uncached_calls",
                "labels_changed_vs_with_language",
                "rows_with_other_claim_language",
                "errors",
            )
        }
        print(model, report[model], flush=True)
    (TEST / "ost-checks-nolang.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def slide28(rows, preds):
    gold = [int(r["entailment_label"]) for r in rows]
    pred = [int(p.get("label", p.get("entailment_label", 1))) for p in preds]

    def f1(idx):
        return (
            {
                "n": len(idx),
                "macro_f1": round(
                    macro_f1([gold[i] for i in idx], [pred[i] for i in idx])[0], 4
                ),
            }
            if idx
            else None
        )

    out = {"all": f1(list(range(len(rows))))}
    for lang in ("de", "fr", "it"):
        out[f"claim_{lang}"] = f1(
            [i for i, r in enumerate(rows) if r["claim_language"] == lang]
        )
        out[f"booklet_{lang}"] = f1(
            [i for i, r in enumerate(rows) if r["reference_language"] == lang]
        )
    out["same_language"] = f1(
        [
            i
            for i, r in enumerate(rows)
            if r["claim_language"] == r["reference_language"]
        ]
    )
    out["cross_lingual"] = f1(
        [
            i
            for i, r in enumerate(rows)
            if r["claim_language"] != r["reference_language"]
        ]
    )
    return out


def breakdown28():
    rows = load_rows()
    report = {}
    for task, runs in (("advanced", DEFAULT_RUNS), ("beginner", BEGINNER_RUNS)):
        for model, name in runs.items():
            report[f"{task} {model} ({name})"] = slide28(rows, load_run(model, name))
    nolang_runs = {m: "default-nolang" for m in DEFAULT_RUNS}
    for model, name in nolang_runs.items():
        if (TEST / model / f"{name}.jsonl").is_file():
            report[f"advanced without claim_language {model} ({name})"] = slide28(
                rows, load_run(model, name)
            )
    print(json.dumps(report, indent=1))
    (TEST / "ost-checks-slide28.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def foreign_votes(rows, pipeline):
    """Pairs (booklet, vote title of the same proposal in another language version of the same voting date).
    Proposals are matched by their position in the booklet; dates whose versions differ in structure are skipped."""
    titles = {}
    for r in rows:
        titles.setdefault(r["booklet_publish_date"], {}).setdefault(r["reference_language"], {})[r["vote"]] = r["booklet_url"]
    position = {}
    for date, langs in titles.items():
        for lang, votes in langs.items():
            for vote, url in votes.items():
                booklet, _ = pipeline.booklet(url)
                _, group = locate(booklet, vote)
                cands = candidates(booklet)
                order = sorted(cands, key=lambda g: min(cands[g]))
                position[(date, lang, vote)] = (order.index(group) if group in order else None, len(order), group)
    pairs = []
    for (date, lang, vote), (idx, n, group) in position.items():
        for lang2, votes2 in titles[date].items():
            if lang2 == lang or idx is None:
                continue
            for vote2 in votes2:
                idx2, n2, _ = position[(date, lang2, vote2)]
                if idx2 == idx and n2 == n:
                    pairs.append({"url": titles[date][lang][vote], "booklet_lang": lang, "vote": vote2,
                                  "vote_lang": lang2, "gold_proposal": group})
    return pairs


def vote():
    rows = load_rows()
    report = {}
    for model in DEFAULT_RUNS:
        llm = LLM(Settings.from_env(model))
        pipeline = Pipeline(llm, Options())
        pairs = foreign_votes(rows, pipeline)
        same = [r for r in rows if foreign_title(r["vote"], pipeline.booklet(r["booklet_url"])[0].language,
                                                 pipeline.booklet(r["booklet_url"])[1].bm25.idf)]

        def one(pair):
            booklet, retriever = pipeline.booklet(pair["url"])
            usage = Usage()
            _, old = locate(booklet, pair["vote"])
            src = foreign_title(pair["vote"], booklet.language, retriever.bm25.idf)
            translated = pipeline._translate(pair["vote"], src, booklet.language, usage, "translate-vote") if src else None
            _, new = locate(booklet, translated or pair["vote"])
            u = usage.summary()
            return dict(pair, detected=src, translation=translated, old=old, new=new,
                        calls=u["llm_calls"] - u["cached_calls"], input_tokens=u["prompt_tokens"])

        with ThreadPoolExecutor(max_workers=4) as pool:
            res = list(pool.map(one, pairs))
        n = len(res)
        report[model] = {
            "pairs": n,
            "test_rows_whose_own_vote_counts_as_foreign": len(same),
            "foreign_title_detected": sum(r["detected"] is not None for r in res),
            "source_language_right": sum(r["detected"] == r["vote_lang"] for r in res),
            "right_proposal_without_translation": sum(r["old"] == r["gold_proposal"] for r in res),
            "right_proposal_with_translation": sum(r["new"] == r["gold_proposal"] for r in res),
            "input_tokens_per_translation": round(sum(r["input_tokens"] for r in res) / max(1, sum(r["translation"] is not None for r in res)), 1),
            "new_calls": sum(r["calls"] for r in res),
            "misses": [{k: r[k] for k in ("booklet_lang", "vote", "translation", "gold_proposal", "new")}
                       for r in res if r["new"] != r["gold_proposal"]],
        }
        print(model, {k: v for k, v in report[model].items() if k != "misses"}, flush=True)
    (TEST / "ost-checks-vote.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cold(name=COLD_NAME, models=None, opts=None):
    """Like `booklint run --no-cache --workers 1` on 50 seeded test cases in OST's input format (no language field).
    Run it with a CACHE_DIR whose llm/ folder is empty, so the stored answers of the other runs stay untouched.
    Optional arguments: cold <name> <model,model> <options as JSON>."""
    import random

    rows = load_rows()
    sample = sorted(random.Random(2026).sample(range(len(rows)), 50))
    gold_rows = [rows[i] for i in sample]
    cases = [{"id": r["id"], "booklet": {"path": r["booklet_url"]}, "vote": r["vote"], "claim": {"text": r["claim"]}}
             for r in gold_rows]
    report = {"ids": [r["id"] for r in gold_rows]}
    for model in (models.split(",") if models else DEFAULT_RUNS):
        RETRIES.update({k: 0 for k in RETRIES})
        pipeline = Pipeline(LLM(Settings.from_env(model), use_cache=False), Options(**json.loads(opts or "{}")))
        t0 = time.perf_counter()
        for c in cases:
            pipeline.booklet(c["booklet"]["path"])
        parse = {b.source: b.ingest_seconds for b, _ in pipeline._booklets.values()}
        t1 = time.perf_counter()
        preds = run_rows(pipeline, cases, 1)
        wall = time.perf_counter() - t1
        summary = breakdown(gold_rows, preds)
        summary.update({"model": model, "name": name, "split": "test", "workers": 1, "response_cache": False,
                        "wall_s": round(wall, 1), "preload_s": round(t1 - t0, 1),
                        "booklets": len(parse), "uncached_calls": sum(p["usage"].get("llm_calls", 0) for p in preds),
                        "retries": dict(RETRIES), **efficiency(preds)})
        out = TEST / model
        with (out / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
            for p in preds:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
        (out / f"{name}.summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report[model] = {k: summary.get(k) for k in ("macro_f1", "errors", "input_tokens_mean", "input_tokens_sum",
                                                     "tokens_mean", "llm_calls_mean", "inference_ms_mean",
                                                     "inference_ms_p95", "llm_seconds_mean", "llm_seconds_p95",
                                                     "wall_s", "uncached_calls", "retries")}
        print(model, report[model], flush=True)
    (TEST / f"ost-checks-{name}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    {"replay": replay, "nolang": nolang, "breakdown": breakdown28, "vote": vote, "cold": cold}[sys.argv[1]](*sys.argv[2:])
