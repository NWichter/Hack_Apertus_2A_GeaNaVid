import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import Settings
from .ingest import ingest
from .llm import LLM, redact
from .metrics import breakdown, summarize
from .retrieval_eval import gold_chunks
from .pipeline import MODES, Options, Pipeline, format_slide25

DISCLAIMER = "Automated assessment against the official booklet. Not voting advice."


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def options_from(args, mode=None):
    keys = (
        "k",
        "neighbors",
        "scope",
        "retriever",
        "pool",
        "rerank",
        "crossling",
        "numbers",
        "fewshot",
        "tau",
        "tau_decompose",
        "cascade",
        "tau_cascade",
        "neutral_bias",
        "prompt",
        "evidence_unit",
    )
    kw = {k: getattr(args, k) for k in keys if getattr(args, k, None) is not None}
    for flag in ("translate", "decompose"):
        if getattr(args, flag, None) is not None:
            kw[flag] = getattr(args, flag)
    if args.no_route:
        kw["route"] = False
    if getattr(args, "calib", None):
        kw["calib"] = json.loads(args.calib)
    return Options(mode=mode or args.mode or Options.mode, **kw)


def failure(cid, exc):
    """A failed case is answered neutral with an error note, so a batch never stops."""
    return {
        "id": cid,
        "label": 1,
        "label_name": "neutral",
        "evidence": [],
        "metrics": {
            "input_tokens": 0,
            "output_tokens": 0,
            "inference_time_ms": 0,
        },
        "decision": 1,
        "answer": "blank",
        "page": None,
        "evidence_sentence": None,
        "evidence_sentences": [],
        "entailment_label": 1,
        "error": redact(repr(exc))[:300],
        "retrieved_ids": [],
        "ladder_step": "error",
        "confidence": None,
        "usage": {
            "llm_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "llm_seconds": 0.0,
        },
    }


def check_case(pipeline, c, claim_lang=None):
    if not c["claim"] or not (c["booklet"] or c["reference"]):
        raise ValueError("case needs a claim and a booklet path or a reference text")
    return pipeline.check(
        c["claim"],
        c["booklet"],
        claim_lang or c["claim_lang"],
        c["reference"],
        c["vote"],
        case_id=c["id"],
    )


def run_rows(pipeline, rows, workers):
    cases = [normalize_case(r) for r in rows]
    for c in cases:
        if c["booklet"]:
            try:
                pipeline.booklet(c["booklet"])
            except Exception:
                pass

    def one(c):
        cid = c["id"]
        try:
            out = check_case(pipeline, c)
        except Exception as exc:
            out = failure(cid, exc)
        out["id"] = cid
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, cases))


def chunk_lookup(pipeline):
    def f(row, i):
        booklet, _ = pipeline.booklet(row["booklet_url"])
        return booklet.chunks[i].text

    return f


def cmd_check(args):
    if not args.booklet and not getattr(args, "reference", None):
        sys.exit("Error: either --booklet or --reference must be provided.")
    mode = args.mode
    if not mode and getattr(args, "reference", None) and not args.booklet:
        mode = "easy"
    pipeline = Pipeline(
        LLM(Settings.from_env(args.model)), options_from(args, mode=mode)
    )
    out = pipeline.check(
        args.claim,
        args.booklet,
        args.claim_lang,
        gold_reference=getattr(args, "reference", None),
        vote=args.vote,
        case_id=getattr(args, "id", ""),
    )
    if args.json:
        s25 = format_slide25(out, case_id=getattr(args, "id", ""))
        print(json.dumps(s25, ensure_ascii=False, indent=2))
        return
    print(
        f"Decision: {out['decision']} ({out['answer']}, {out['label_name']})  confidence: {out['confidence']}  step: {out['ladder_step']}"
    )
    for e in out.get("evidence_sentences", []):
        print(f'  p. {e["page"]}: "{e["text"]}"')
    u = out["usage"]
    print(
        f"Tokens in/out: {u['prompt_tokens']}/{u['completion_tokens']}  calls: {u['llm_calls']}  time: {out['latency_s']} s"
    )
    print(DISCLAIMER)


def _field(value, key):
    return value.get(key) if isinstance(value, dict) else value


def resolve_booklet(path):
    """Relative booklet paths are read below BOOKLET_ROOT when it is set."""
    root = os.environ.get("BOOKLET_ROOT")
    if not path or not root or "://" in path or Path(path).is_absolute():
        return path
    return str(Path(root) / path)


def normalize_case(r):
    """Flat dataset rows and OST task cases (slide 24: booklet.path, claim.text, reference.text) -> one shape."""
    return {
        "id": str(r.get("id") or ""),
        "claim": _field(r.get("claim"), "text"),
        "booklet": resolve_booklet(
            _field(r.get("booklet"), "path") or r.get("booklet_path") or r.get("booklet_url")
        ),
        "reference": _field(r.get("reference"), "text") or r.get("reference_string"),
        "vote": r.get("vote"),
        "claim_lang": r.get("claim_language"),
    }


def read_cases(path):
    """A file with one JSON object, a JSON list, or JSONL; "-" reads stdin."""
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
        items = data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        items = [json.loads(line) for line in raw.splitlines() if line.strip()]
    return [normalize_case(c) for c in items]


def cmd_predict(args):
    if args.case:
        cases = read_cases(args.case)
    else:
        if not args.claim or not (args.booklet or args.reference):
            sys.exit(
                "Error: give --case FILE, or --claim with --booklet or --reference."
            )
        cases = [
            {
                "id": args.id,
                "claim": args.claim,
                "booklet": args.booklet,
                "reference": args.reference,
                "vote": args.vote,
                "claim_lang": args.claim_lang,
            }
        ]
    llm = LLM(Settings.from_env(args.model), use_cache=not args.no_cache)
    pipelines = {}
    single = len(cases) == 1 and not (args.case and args.case.endswith(".jsonl"))
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        sink = open(args.output, "w", encoding="utf-8", newline="\n")
    else:
        sink = sys.stdout
    try:
        for c in cases:
            try:
                mode = args.mode or (None if c["booklet"] else "easy")
                if mode not in pipelines:
                    pipelines[mode] = Pipeline(llm, options_from(args, mode=mode))
                case = dict(c, reference=None if c["booklet"] else c["reference"])
                result = format_slide25(check_case(pipelines[mode], case, args.claim_lang), case_id=c["id"])
            except Exception as exc:
                failed = failure(c["id"], exc)
                result = dict(format_slide25(failed, case_id=c["id"]), error=failed["error"])
                print(f"case {c['id']!r} failed: {failed['error']}", file=sys.stderr)
            indent = 2 if single else None
            sink.write(json.dumps(result, ensure_ascii=False, indent=indent) + "\n")
            sink.flush()
    finally:
        if sink is not sys.stdout:
            sink.close()


def cmd_run(args):
    rows = read_jsonl(args.input)[: args.limit or None]
    pipeline = Pipeline(
        LLM(Settings.from_env(args.model), use_cache=not args.no_cache),
        options_from(args),
    )
    preds = run_rows(pipeline, rows, args.workers)
    write_jsonl(args.output, preds)
    if all("entailment_label" in r for r in rows):
        print(
            json.dumps(
                summarize(rows, preds, chunk_lookup(pipeline)),
                ensure_ascii=False,
                indent=2,
            )
        )


def cmd_eval(args):
    rows, preds = read_jsonl(args.input), read_jsonl(args.pred)
    print(json.dumps(summarize(rows, preds), ensure_ascii=False, indent=2))
    if args.errors:
        names = {0: "E", 1: "N", 2: "C"}
        for r, p in zip(rows, preds):
            gold_lbl = int(r.get("label", r.get("entailment_label", 1)))
            pred_lbl = int(p.get("label", p.get("entailment_label", 1)))
            if gold_lbl == pred_lbl:
                continue
            print(
                f"\n--- {r.get('id')} gold {names[gold_lbl]} pred {names[pred_lbl]}"
                f" conf {p.get('confidence')} step {p.get('ladder_step')} {r.get('hard_type', '')}"
            )
            print(f"claim: {r['claim']}")
            print(f"gold:  {r['reference_string'][:400]}")
            for e in p.get("evidence", [])[:2]:
                print(f"cited p.{e['page']}: {e['text'][:300]}")


def cmd_ingest(args):
    b = ingest(args.booklet, use_cache=False)
    groups = {}
    for c in b.chunks:
        groups.setdefault(c.group, []).append(c.page)
    print(
        f"{b.source}: language {b.language}, {b.pages} pages, {len(b.chunks)} chunks, {b.ingest_seconds} s"
    )
    for g, pages in groups.items():
        print(
            f"  {g or '(front matter)'}: pages {min(pages)}-{max(pages)}, {len(pages)} chunks"
        )


COLUMNS = [
    "n",
    "macro_f1",
    "ci95",
    "f1_e",
    "f1_n",
    "f1_c",
    "macro_f1_same",
    "macro_f1_cross",
    "recall_hit",
    "tokens_mean",
    "input_tokens_mean",
    "llm_calls_mean",
    "llm_seconds_p50",
    "inference_ms_mean",
    "inference_ms_p95",
    "errors",
]


def cmd_bench(args):
    rows = [r for path in args.input for r in read_jsonl(path)][: args.limit or None]
    out_dir = Path(args.out_dir)
    results = []
    for model in args.models.split(","):
        settings = Settings.from_env(model or None)
        llm = LLM(settings, use_cache=not args.no_cache)
        for mode in args.modes.split(","):
            pipeline = Pipeline(llm, options_from(args, mode))
            t0 = time.perf_counter()
            preds = run_rows(pipeline, rows, args.workers)
            wall = time.perf_counter() - t0
            name = f"{settings.model}__{mode}__{pipeline.opt.prompt}{args.tag}"
            write_jsonl(out_dir / f"{name}.jsonl", preds)
            gold = [
                gold_chunks(
                    pipeline.booklet(r["booklet_url"])[0], r.get("reference_string", "")
                )
                for r in rows
            ]
            s = breakdown(rows, preds, gold)
            s.update(
                {
                    "model": settings.model,
                    "mode": f"{mode} {pipeline.opt.prompt}{args.tag}",
                    "wall_s": round(wall, 1),
                    "errors": sum("error" in p for p in preds),
                }
            )
            results.append(s)
            print(
                f"{name}: macro-F1 {s['macro_f1']} {s['ci95']}  tokens {s['tokens_mean']}  errors {s['errors']}",
                file=sys.stderr,
            )
    (out_dir / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "| model | mode | " + " | ".join(COLUMNS) + " |",
        "|" + "---|" * (len(COLUMNS) + 2),
    ]
    for s in results:
        lines.append(
            f"| {s['model']} | {s['mode']} | "
            + " | ".join(str(s.get(c)) for c in COLUMNS)
            + " |"
        )
    table = "\n".join(lines)
    (out_dir / "summary.md").write_text(
        f"Input: {', '.join(args.input)} ({len(rows)} pairs)\n\n{table}\n",
        encoding="utf-8",
    )
    print(table)


def add_common(p):
    p.add_argument("--model", default=None, help="model name, default LLM_NAME")
    p.add_argument(
        "--mode", default=None, choices=MODES, help=f"default {Options.mode}"
    )
    p.add_argument("--k", type=int, default=None)
    p.add_argument("--neighbors", type=int, default=None)
    p.add_argument(
        "--scope",
        default=None,
        choices=["vote", "claim", "booklet"],
        help="search only the proposal named by the row's vote field (vote), the proposal found from the claim, or the whole booklet",
    )
    p.add_argument(
        "--retriever",
        default=None,
        choices=["bm25", "hybrid", "dense"],
        help="hybrid/dense need the extra [dense]",
    )
    p.add_argument("--pool", type=int, default=None)
    p.add_argument(
        "--rerank",
        default=None,
        choices=["", "yesno"],
        help="Apertus yes/no relevance rerank of the top pool",
    )
    p.add_argument(
        "--translate",
        dest="translate",
        action="store_true",
        default=None,
        help="translate cross-lingual claims into the booklet language with Apertus",
    )
    p.add_argument("--no-translate", dest="translate", action="store_false")
    p.add_argument(
        "--crossling",
        default=None,
        choices=["parallel", "both", "none"],
        help="optional: search the other language version of the booklet (not part of the default pipeline)",
    )
    p.add_argument("--numbers", default=None, choices=["", "hint", "rule", "hint+rule"])
    p.add_argument(
        "--fewshot",
        type=int,
        default=None,
        help="dev examples in the prompt (default -1: 3 for 8B models, 0 otherwise)",
    )
    p.add_argument(
        "--decompose",
        dest="decompose",
        action="store_true",
        default=None,
        help="split unsure claims into atomic statements (default: on for 8B models)",
    )
    p.add_argument("--no-decompose", dest="decompose", action="store_false")
    p.add_argument("--tau-decompose", dest="tau_decompose", type=float, default=None)
    p.add_argument(
        "--cascade",
        default=None,
        help="optional: re-ask this model when unsure (e.g. apertus-v1.5-70b)",
    )
    p.add_argument("--tau-cascade", dest="tau_cascade", type=float, default=None)
    p.add_argument(
        "--calib", default=None, help='label log-offsets as JSON, e.g. {"neutral": 0.5}'
    )
    p.add_argument("--tau", type=float, default=None)
    p.add_argument("--neutral-bias", type=float, default=None)
    p.add_argument(
        "--prompt",
        default=None,
        choices=["nli-v1", "nli-v2", "nli-v3", "nli-v4", "nli-v5"],
    )
    p.add_argument(
        "--no-route",
        action="store_true",
        help="disable the recommendation-section routing",
    )
    p.add_argument(
        "--evidence-unit",
        dest="evidence_unit",
        default=None,
        choices=["sentence", "paragraph"],
        help="evidence text: the deciding sentence(s) (default) or the whole paragraph(s) around them",
    )


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="booklint", description="Check claims against Swiss voting booklets."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="one claim against one booklet or reference")
    p.add_argument("--id", default="", help="case id string")
    p.add_argument(
        "--booklet", default=None, help="PDF path or URL (required for advanced task)"
    )
    p.add_argument("--claim", required=True)
    p.add_argument(
        "--reference",
        "--reference-string",
        dest="reference",
        default=None,
        help="reference string/passage (for beginner task)",
    )
    p.add_argument("--claim-lang", default=None)
    p.add_argument(
        "--vote",
        default=None,
        help="title of the proposal the claim is about (optional)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="print the OST output format (slide 25) as JSON",
    )
    add_common(p)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser(
        "predict", help="OST output format (JSON) for one case or a file of cases"
    )
    p.add_argument(
        "--case",
        default=None,
        help='OST input case(s): JSON object, list or JSONL file; "-" = stdin',
    )
    p.add_argument("--id", default="", help="case id string")
    p.add_argument("--booklet", default=None, help="PDF path or URL (advanced task)")
    p.add_argument("--claim", default=None)
    p.add_argument(
        "--reference",
        "--reference-string",
        dest="reference",
        default=None,
        help="reference passage (beginner task)",
    )
    p.add_argument("--claim-lang", default=None)
    p.add_argument(
        "--vote",
        default=None,
        help="title of the proposal the claim is about (optional)",
    )
    p.add_argument(
        "--output", "-o", default=None, help="write the JSON here instead of stdout"
    )
    p.add_argument(
        "--no-cache", action="store_true", help="do not reuse cached LLM answers"
    )
    add_common(p)
    p.set_defaults(fn=cmd_predict)

    p = sub.add_parser("run", help="predict a JSONL file in the dataset format")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--no-cache", action="store_true")
    add_common(p)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("eval", help="score predictions against gold labels")
    p.add_argument("--input", required=True)
    p.add_argument("--pred", required=True)
    p.add_argument(
        "--errors", action="store_true", help="print every misclassified pair"
    )
    p.set_defaults(fn=cmd_eval)

    p = sub.add_parser("ingest", help="parse a booklet and show its proposals")
    p.add_argument("--booklet", required=True)
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("bench", help="compare models and modes on gold files")
    p.add_argument("--input", required=True, nargs="+")
    p.add_argument("--models", default="")
    p.add_argument("--modes", default="retrieval")
    p.add_argument("--out-dir", default="runs/latest")
    p.add_argument("--tag", default="", help="suffix for result file names")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--no-cache", action="store_true")
    add_common(p)
    p.set_defaults(fn=cmd_bench)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
