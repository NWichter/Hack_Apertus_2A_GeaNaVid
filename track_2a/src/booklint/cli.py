import argparse
import json
import os
import re
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
        "tau_recheck",
        "cascade",
        "tau_cascade",
        "neutral_bias",
        "prompt",
        "evidence_unit",
        "section_boost",
        "render",
    )
    kw = {k: getattr(args, k) for k in keys if getattr(args, k, None) is not None}
    for flag in ("translate", "decompose", "recheck", "committee_terms"):
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
    if c.get("error"):
        raise ValueError(c["error"])
    if not c["claim"] or not (c["booklet"] or c["reference"]):
        raise ValueError("case needs a claim and a booklet path or a reference text")
    out = pipeline.check(
        c["claim"],
        c["booklet"],
        claim_lang or c["claim_lang"],
        c["reference"],
        c["vote"],
        case_id=c["id"],
    )
    if not c["booklet"] and c.get("reference_page"):
        # Beginner case whose reference carries its page: cite that page instead of 1.
        for item in out.get("evidence", []) + out.get("evidence_sentences", []):
            item["page"] = c["reference_page"]
        if out.get("page") is not None:
            out["page"] = c["reference_page"]
    return out


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


FALLBACK_DIRS = ("/work", "/work/booklets", "/data", "/booklets")
_resolved = {}


def _booklet_candidates(path, case_dir):
    rel = Path(path)
    root = os.environ.get("BOOKLET_ROOT")
    dirs = [root] if root else []
    dirs += [None, *FALLBACK_DIRS]
    if case_dir:
        dirs.append(case_dir)
    for d in dirs:
        yield rel if d is None else Path(d) / rel
    name_dirs = [d for d in (root, case_dir, *FALLBACK_DIRS) if d]
    for d in name_dirs:
        base = Path(d)
        if base.is_dir():
            yield from sorted(base.rglob(rel.name))


def resolve_booklet(path, case_dir=None):
    """Booklet path as given; a relative path is read below BOOKLET_ROOT when it is set. A path that does not
    exist is also looked up below the usual mount points, next to the case file and by file name; the path
    taken is reported on stderr."""
    if path and path.lower().startswith("file://"):
        path = path[7:]
    if not path or "://" in path:
        return path
    root = os.environ.get("BOOKLET_ROOT")
    primary = path if Path(path).is_absolute() or not root else str(Path(root) / path)
    if Path(primary).is_file():
        return primary
    key = (path, root, str(case_dir or ""))
    if key not in _resolved:
        found = next(
            (c for c in _booklet_candidates(path, case_dir) if c.is_file()), None
        )
        _resolved[key] = str(found) if found else primary
        if found:
            print(
                f"booklet {path!r} not found at {primary!r}, using {str(found)!r}",
                file=sys.stderr,
            )
    return _resolved[key]


def _text(value, *keys):
    """A non-empty string, or the first non-empty string under one of `keys` of a dict; a list is joined."""
    if isinstance(value, dict):
        return next((t for t in (_text(value.get(k)) for k in keys) if t), None)
    if isinstance(value, list):
        parts = [_text(v, *keys) for v in value]
        return "\n\n".join(p for p in parts if p) or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _first(r, *keys):
    return next((r[k] for k in keys if r.get(k) not in (None, "", {}, [])), None)


LANGS = {"de", "fr", "it"}


def _lang(*values):
    for v in values:
        v = (_text(v) or "").lower()[:2]
        if v in LANGS:
            return v
    return None


def _page(value):
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


def normalize_case(r, case_dir=None):
    """Flat dataset rows and OST task cases (slide 24: booklet.path, claim.text, reference.text) -> one shape.
    Also accepted: plain strings instead of the nested objects, `url`/`file` for the booklet, `title` for a
    nested vote, `hypothesis`/`premise`, a language next to the claim and a page next to the reference."""
    if not isinstance(r, dict):
        r = {"_error": f"case is a {type(r).__name__}, not a JSON object"}
    claim = _first(r, "claim", "hypothesis", "claim_text", "statement")
    booklet = _first(
        r,
        "booklet",
        "booklet_path",
        "booklet_url",
        "booklet_file",
        "pdf",
        "pdf_path",
        "document",
    )
    reference = _first(
        r,
        "reference",
        "reference_string",
        "reference_text",
        "premise",
        "passage",
        "context",
    )
    vote = _first(r, "vote", "vote_title", "proposal", "title")
    cid = _first(r, "id", "case_id", "uid", "pair_id")
    return {
        "id": "" if cid is None else str(cid),
        "claim": _text(claim, "text", "claim"),
        "booklet": resolve_booklet(
            _text(booklet, "path", "file", "pdf", "url", "booklet_path", "booklet_url"),
            case_dir,
        ),
        "reference": _text(reference, "text", "reference_string", "passage"),
        "reference_page": _page(_first(reference, "page", "page_number", "pdf_page"))
        if isinstance(reference, dict)
        else _page(r.get("reference_page")),
        "vote": _text(vote, "title", "text", "name", "vote"),
        "claim_lang": _lang(
            r.get("claim_language"),
            r.get("claim_lang"),
            claim.get("language") if isinstance(claim, dict) else None,
            claim.get("lang") if isinstance(claim, dict) else None,
        ),
        "error": r.get("_error"),
    }


def _items(data):
    """A case object, a list of cases, or an object that wraps the list ({"cases": [...]})."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and not any(
        k in data for k in ("claim", "hypothesis", "claim_text")
    ):
        for key in ("cases", "data", "items", "instances", "examples", "rows"):
            if isinstance(data.get(key), list):
                return data[key]
    return [data]


def read_cases(path):
    """A file with one JSON object, a JSON list (or an object wrapping it), or JSONL; "-" reads stdin.
    A UTF-8 BOM is ignored; a JSONL line that is not valid JSON becomes a failed case, not a crash."""
    if path == "-":
        buffer = getattr(sys.stdin, "buffer", None)
        raw = (
            buffer.read().decode("utf-8-sig", errors="replace")
            if buffer
            else sys.stdin.read().lstrip("﻿")
        )
    else:
        raw = Path(path).read_bytes().decode("utf-8-sig", errors="replace")
    try:
        items = _items(json.loads(raw))
    except json.JSONDecodeError:
        items = []
        for n, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                items.extend(_items(json.loads(line)))
            except json.JSONDecodeError as exc:
                found = re.search(r'"(?:id|case_id)"\s*:\s*"?([^",}]+)', line)
                items.append(
                    {
                        "id": found.group(1) if found else f"line-{n}",
                        "_error": f"invalid JSON on line {n}: {exc}",
                    }
                )
    case_dir = None if path == "-" else str(Path(path).resolve().parent)
    return [normalize_case(c, case_dir) for c in items]


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
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        sink = open(args.output, "w", encoding="utf-8", newline="\n")
    else:
        sink = sys.stdout
    # One compact line per case, so the output is always valid JSONL; pretty only for one case on a terminal.
    single = (
        len(cases) == 1
        and sink is sys.stdout
        and sys.stdout.isatty()
        and args.format == "jsonl"
    )
    as_list = args.format == "json"
    if as_list:
        sink.write("[\n")
    try:
        for n, c in enumerate(cases):
            try:
                mode = args.mode or (None if c["booklet"] else "easy")
                if mode not in pipelines:
                    pipelines[mode] = Pipeline(llm, options_from(args, mode=mode))
                case = dict(c, reference=None if c["booklet"] else c["reference"])
                result = format_slide25(
                    check_case(pipelines[mode], case, args.claim_lang), case_id=c["id"]
                )
            except Exception as exc:
                failed = failure(c["id"], exc)
                result = dict(
                    format_slide25(failed, case_id=c["id"]), error=failed["error"]
                )
                print(f"case {c['id']!r} failed: {failed['error']}", file=sys.stderr)
            indent = 2 if single else None
            line = json.dumps(result, ensure_ascii=False, indent=indent)
            sink.write(
                (",\n" if as_list and n else "") + line + ("" if as_list else "\n")
            )
            sink.flush()
    finally:
        if as_list:
            sink.write("\n]\n")
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
        "--recheck",
        dest="recheck",
        action="store_true",
        default=None,
        help="ask once more, only for a contradiction, when the answer is neutral (default: on for 8B models)",
    )
    p.add_argument("--no-recheck", dest="recheck", action="store_false")
    p.add_argument("--tau-recheck", dest="tau_recheck", type=float, default=None)
    p.add_argument(
        "--committee-terms",
        dest="committee_terms",
        action="store_true",
        default=None,
        help="restore Komitee / comité / comitato in claim translations (default: on for 8B models)",
    )
    p.add_argument("--no-committee-terms", dest="committee_terms", action="store_false")
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
    p.add_argument(
        "--section-boost",
        dest="section_boost",
        type=float,
        default=None,
        help="ranking factor for passages of the section the claim names (summary, committee, voting text, ...); 1 = off, default 1.5",
    )
    p.add_argument(
        "--render",
        default=None,
        choices=["full", "compact"],
        help="passage headers: full (default) or compact (proposal title once, section type instead of the page note)",
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
    p.add_argument(
        "--format",
        default="jsonl",
        choices=["jsonl", "json"],
        help="jsonl: one JSON object per line (default); json: one JSON list",
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
