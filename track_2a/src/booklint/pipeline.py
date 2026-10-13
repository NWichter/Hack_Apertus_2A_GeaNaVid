import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import LABELS, numbers, sentences
from .ingest import Chunk, ingest, page_texts
from .llm import Usage
from .nli import (
    PROMPT_VERSION,
    aggregate,
    contradiction_prob,
    recheck_messages,
    recheck_params,
    translate_passages_messages,
    translate_passages_params,
    build_messages,
    decompose_messages,
    decompose_params,
    label_probs,
    nli_params,
    parse,
    relevance_messages,
    translate_messages,
    verify_facts_messages,
    verify_facts_params,
    yes_prob,
)
from .proposal import locate
from .retrieval_eval import gold_chunks
from .retrieve import Retriever, map_parallel, parallel_url
from .sections import PREFER, claim_cue, classify, factors
from .textnorm import detect_language, language_scores, tokens

_RECOMMEND_CLAIM = re.compile(
    r"empf[eiä]|recomm|racc?omand|ablehn|annehm|rejet|accept|respin|accett|parole", re.I
)
_RECOMMEND_HEAD = re.compile(
    r"empfehlung|recommandation|raccomandazione|position|posizione|abstimmungsfrage|question|domanda",
    re.I,
)

MODES = (
    "ladder",
    "retrieval",
    "pages",
    "section",
    "full",
    "baseline",
    "easy",
    "oracle",
    "claim-only",
)
FEWSHOT_FILE = Path(__file__).with_name("fewshot.json")
ANSWERS = {"entailment": "yes", "neutral": "blank", "contradiction": "no"}
SECTION_NAMES = {
    "committee": "text of the committee",
    "authorities": "arguments of the Federal Council and Parliament",
    "recommendation": "question, recommendations and votes",
    "legal": "voting text (legal text)",
    "debate": "debate in Parliament",
    "overview": "overview",
    "context": "explanation",
}


@dataclass
class Options:
    mode: str = "retrieval"
    k: int = 5
    neighbors: int = 1
    scope: str = "vote"
    retriever: str = "bm25"
    pool: int = 15
    rerank: str = ""
    translate: bool = True
    crossling: str = "none"
    numbers: str = ""
    decompose: object = None
    tau_decompose: float = 0.9
    fewshot: int = -1
    calib: dict = field(default_factory=dict)
    cascade: str = ""
    tau_cascade: float = 0.75
    escalate: str = "pages"
    prompt: str = PROMPT_VERSION
    route: bool = True
    evidence_bonus: float = 1.2
    tau: float = 0.75
    neutral_bias: float = 0.0
    max_evidence: int = 3
    evidence_unit: str = "sentence"
    section_boost: float = 1.5
    evidence_section: float = 2.0
    evidence_section_pool: int = 4
    render: str = "full"
    translate_reference: bool = False
    committee_terms: object = None
    translate_passages: bool = False
    recheck: object = None
    recheck_min_bm25: float = 0.0
    tau_recheck: float = 0.5
    recheck_context: str = "all"
    recheck_entailment: bool = False
    tau_recheck_entailment: float = 0.5


_COMMITTEE = re.compile(r"komitee|comité|comitato", re.I)
_COMMITTEE_TERMS = {
    "de": [(r"\b([Dd])er Ausschuss\b", r"\1as Komitee"), (r"\bAusschusses\b", "Komitees"), (r"\bAusschuss\b", "Komitee")],
    "fr": [(r"\b([Ll])a commission\b", r"\1e comité"), (r"\bcommission\b", "comité")],
    "it": [(r"\b([Ll])a commissione\b", lambda m: ("I" if m.group(1) == "L" else "i") + "l comitato"), (r"\bcommissione\b", "comitato")],
}


def committee_terms(claim, translation, lang):
    """Booklets call the initiative or referendum committee Komitee / comité / comitato; Apertus often translates
    "comitato" as "Ausschuss", which hides the committee pages from retrieval."""
    if not translation or not _COMMITTEE.search(claim) or _COMMITTEE.search(translation):
        return translation
    for pattern, repl in _COMMITTEE_TERMS.get(lang, []):
        translation = re.sub(pattern, repl, translation)
    return translation


def foreign_title(text, booklet_lang, vocabulary):
    """Source language of a vote title written in another language than the booklet, else None.
    Titles in the booklet language have all their words in the booklet (1,495 of 1,495 v1.0 rows)."""
    words = [t for t in tokens(text) if not t[0].isdigit()]
    if not words:
        return None
    coverage = sum(t in vocabulary for t in words) / len(words)
    scores = language_scores(text)
    best = max(scores, key=scores.get)
    if coverage < 0.5 or (coverage < 0.9 and best != booklet_lang):
        others = {k: v for k, v in scores.items() if k != booklet_lang}
        return max(others, key=others.get)
    return None


def small_model(model):
    return "8b" in (model or "").lower()


def fewshot_for(n, model):
    """-1 = auto: 3 dev examples for the 8B model, none for larger models (few-shot hurt 70B on dev_s)."""
    if n >= 0:
        return n
    return 3 if small_model(model) else 0


def load_examples(n):
    if n <= 0 or not FEWSHOT_FILE.is_file():
        return []
    return json.loads(FEWSHOT_FILE.read_text(encoding="utf-8"))[:n]


def apply_bias(probs, bias):
    if not probs or not bias:
        return probs
    logits = {k: math.log(max(v, 1e-9)) + bias.get(k, 0.0) for k, v in probs.items()}
    m = max(logits.values())
    z = sum(math.exp(v - m) for v in logits.values())
    return {k: math.exp(v - m) / z for k, v in logits.items()}


def format_slide25(out, case_id=None):
    cid = case_id if case_id is not None else out.get("id", "")
    cid_str = str(cid) if cid is not None else ""
    lbl = int(out.get("label", out.get("entailment_label", 1)))
    if lbl not in (0, 1, 2):
        lbl = 1
    lbl_name = ("entailment", "neutral", "contradiction")[lbl]

    if lbl == 1 or lbl_name == "neutral":
        ev = []
    else:
        raw_ev = out.get("evidence", [])
        if not raw_ev and out.get("evidence_sentences"):
            raw_ev = out["evidence_sentences"]
        ev = [
            {"page": int(item["page"]), "text": str(item["text"])}
            for item in raw_ev
            if "page" in item and "text" in item and item["page"] is not None and item["text"]
        ]
        if not ev and out.get("evidence_sentence"):
            page = int(out.get("page") or 1)
            ev = [{"page": page, "text": str(out["evidence_sentence"])}]

    metrics = out.get("metrics")
    usage = out.get("usage", {})
    if not isinstance(metrics, dict) or "input_tokens" not in metrics:
        metrics_dict = {
            "input_tokens": int(usage.get("prompt_tokens", 0)),
            "output_tokens": int(usage.get("completion_tokens", 0)),
            "inference_time_ms": int(round(out.get("latency_s", 0.0) * 1000)),
        }
    else:
        metrics_dict = {
            "input_tokens": int(metrics.get("input_tokens", usage.get("prompt_tokens", 0))),
            "output_tokens": int(metrics.get("output_tokens", usage.get("completion_tokens", 0))),
            "inference_time_ms": int(metrics.get("inference_time_ms", round(out.get("latency_s", 0.0) * 1000))),
        }

    return {
        "id": cid_str,
        "label": lbl,
        "label_name": lbl_name,
        "evidence": ev,
        "metrics": metrics_dict,
    }


class Pipeline:
    def __init__(self, llm, options):
        self.llm = llm
        self.opt = options
        self._booklets = {}
        self._kinds = {}
        small = small_model(getattr(llm, "model", ""))
        self.decompose = options.decompose if options.decompose is not None else small
        self.recheck = options.recheck if options.recheck is not None else small
        self.committee_terms = options.committee_terms if options.committee_terms is not None else small
        self.examples = load_examples(fewshot_for(options.fewshot, getattr(llm, "model", "")))

    def booklet(self, source):
        if source not in self._booklets:
            b = ingest(source)
            self._booklets[source] = (b, Retriever(b))
        return self._booklets[source]

    def kinds(self, booklet):
        if booklet.source not in self._kinds:
            self._kinds[booklet.source] = classify(booklet)
        return self._kinds[booklet.source]

    def _render(self, booklet, ids):
        """Passages for the prompt. "compact": the proposal title only when it changes, the section type instead of
        the page note (which repeats a whole sentence on every committee passage)."""
        if self.opt.render != "compact":
            return [booklet.chunks[i].render() for i in ids]
        kinds = self.kinds(booklet)
        out, last = [], None
        for i in ids:
            c = booklet.chunks[i]
            parts = [f"p. {c.page}"]
            if c.group and c.group != last:
                parts.append(c.group)
            last = c.group
            if c.heading:
                parts.append(c.heading)
            if SECTION_NAMES.get(kinds[i]):
                parts.append(SECTION_NAMES[kinds[i]])
            out.append(f"({'; '.join(parts)}) {c.text}")
        return out

    def _translate(self, claim, src, dst, usage, purpose="translate"):
        rec = self.llm.chat(
            translate_messages(claim, src, dst),
            usage,
            purpose,
            temperature=0,
            max_tokens=200,
        )
        return rec["content"].strip()

    def _judge(
        self,
        passages,
        claim,
        claim_lang,
        booklet_lang,
        translation,
        usage,
        step,
        note=None,
        model=None,
    ):
        messages = build_messages(
            passages,
            claim,
            claim_lang,
            booklet_lang,
            translation,
            self.opt.prompt,
            self.examples,
            note,
        )
        rec = self.llm.chat(
            messages, usage, step, model=model, **nli_params(self.opt.prompt)
        )
        label, evidence = parse(rec, len(passages))
        probs = label_probs(rec)
        raw = dict(probs) if probs else None
        bias = dict(self.opt.calib)
        if self.opt.neutral_bias:
            bias["neutral"] = bias.get("neutral", 0.0) + self.opt.neutral_bias
        if probs and bias:
            probs = apply_bias(probs, bias)
            label = max(probs, key=probs.get)
        if label is None:
            label = max(probs, key=probs.get) if probs else "neutral"
        confidence = probs[label] if probs else None
        return {
            "label": label,
            "evidence": evidence,
            "probs": probs,
            "raw_probs": raw,
            "confidence": confidence,
            "step": step,
        }

    def _recheck(self, passages, claim, claim_lang, booklet_lang, translation, usage, first="neutral"):
        rec = self.llm.chat(
            recheck_messages(passages, claim, claim_lang, booklet_lang, translation, first),
            usage,
            "recheck" if first == "neutral" else "recheck-entailment",
            **recheck_params(),
        )
        try:
            data = json.loads(rec["content"])
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        p = contradiction_prob(rec)
        if p is None:
            p = 1.0 if data.get("verdict") == "contradiction" else 0.0
        try:
            passage = int(data.get("passage") or 0)
        except (TypeError, ValueError):
            passage = 0
        return {"first": first, "p_contradiction": round(p, 4), "passage": passage,
                "claim_detail": data.get("claim_detail"), "passage_detail": data.get("passage_detail")}

    def _parallel_hits(self, source, booklet, claim, claim_lang, k):
        url = parallel_url(source, claim_lang)
        if not url:
            return None
        try:
            other, other_ret = self.booklet(url)
        except Exception:
            return None
        if other.language != claim_lang or other.pages != booklet.pages:
            return None
        ranked, _ = other_ret.rank([claim])
        return map_parallel(other, ranked[: self.opt.pool], booklet)

    def _rank(self, booklet, retriever, queries, region):
        allowed = set(region)
        bm25, best = retriever.rank(queries)
        bm25 = [i for i in bm25 if i in allowed]
        if self.opt.retriever == "bm25":
            return bm25, best
        from .dense import query_scores

        sims = query_scores(booklet, queries)
        dense = sorted(region, key=lambda i: -sims[i])
        if self.opt.retriever == "dense":
            return dense, best
        fused = {}
        for ranking in (bm25[:50], dense[:50]):
            for r, i in enumerate(ranking):
                fused[i] = fused.get(i, 0.0) + 1.0 / (60 + r)
        return sorted(fused, key=lambda i: -fused[i]), best

    def _rerank(self, booklet, ids, claim, translation, usage):
        query = translation or claim
        scored = []
        for i in ids:
            rec = self.llm.chat(
                relevance_messages(booklet.chunks[i].render(), query),
                usage,
                "rerank",
                temperature=0,
                max_tokens=1,
                logprobs=True,
                top_logprobs=5,
            )
            scored.append((yes_prob(rec), -ids.index(i), i))
        return [i for _, _, i in sorted(scored, reverse=True)]

    def _hits(
        self,
        source,
        booklet,
        retriever,
        queries,
        claim,
        claim_lang,
        region,
        translation,
        usage,
    ):
        k = self.opt.k
        anchor = "direct"
        ranked, best = self._rank(booklet, retriever, queries, region)
        if self.opt.section_boost != 1.0:
            want = PREFER.get(claim_cue(*queries), set())
            kinds = self.kinds(booklet)
            score = {i: (self.opt.section_boost if kinds[i] in want else 1.0) / (60 + r) for r, i in enumerate(ranked)}
            ranked = sorted(ranked, key=lambda i: -score[i])
        if claim_lang != booklet.language and self.opt.crossling in (
            "parallel",
            "both",
        ):
            par = self._parallel_hits(source, booklet, claim, claim_lang, k)
            if par is not None:
                anchor = "parallel"
                allowed = set(region)
                par = [i for i in par if i in allowed] or par
                if self.opt.crossling == "both":
                    mixed = []
                    for a, b in zip(par, ranked):
                        mixed += [x for x in (a, b) if x not in mixed]
                    par = mixed
                ranked = par + [i for i in ranked if i not in par]
        if self.opt.rerank:
            pool = ranked[: self.opt.pool]
            ranked = (
                self._rerank(booklet, pool, claim, translation, usage)
                + ranked[self.opt.pool :]
            )
        hits = ranked[:k]
        if self.opt.route and hits and _RECOMMEND_CLAIM.search(" ".join(queries)):
            groups = {booklet.chunks[i].group for i in hits[:2]}
            extra = [
                c.id
                for c in booklet.chunks
                if c.group in groups
                and _RECOMMEND_HEAD.search(c.heading)
                and c.id not in hits
            ]
            hits = hits + extra[:4]
        return hits, best, anchor

    def _number_note(self, claim, passages, scope_texts):
        if not self.opt.numbers:
            return None, None
        chk = numbers.check(claim, passages)
        chk["missing_scope"] = numbers.check(claim, scope_texts)["missing"]
        note = None
        if "hint" in self.opt.numbers and chk["missing"]:
            note = "these numbers of the claim do not occur in the passages: " + ", ".join(chk["missing"])
        return chk, note

    def _decompose(self, passages, claim, translation, usage, model=None):
        rec = self.llm.chat(
            decompose_messages(translation or claim),
            usage,
            "decompose",
            model=model,
            **decompose_params(),
        )
        try:
            facts = [
                f for f in json.loads(rec["content"]).get("facts", []) if f.strip()
            ][:4]
        except (json.JSONDecodeError, AttributeError):
            facts = []
        if len(facts) < 2:
            return None, facts
        rec = self.llm.chat(
            verify_facts_messages(passages, facts, self.opt.prompt),
            usage,
            "verify-facts",
            model=model,
            **verify_facts_params(len(facts)),
        )
        try:
            verdicts = json.loads(rec["content"]).get("verdicts", [])
        except (json.JSONDecodeError, AttributeError):
            verdicts = []
        return aggregate(verdicts), facts

    def predict(
        self,
        claim,
        booklet_source=None,
        claim_lang=None,
        gold_reference=None,
        vote=None,
        case_id=None,
    ):
        out = self.check(
            claim,
            booklet_source=booklet_source,
            claim_lang=claim_lang,
            gold_reference=gold_reference,
            vote=vote,
            case_id=case_id,
        )
        return format_slide25(out, case_id=case_id)

    def check(
        self,
        claim,
        booklet_source=None,
        claim_lang=None,
        gold_reference=None,
        vote=None,
        case_id=None,
    ):
        t0 = time.perf_counter()
        usage = Usage()
        mode = self.opt.mode

        if not booklet_source and not gold_reference:
            raise ValueError("Either booklet_source or gold_reference must be provided.")

        if booklet_source:
            booklet, retriever = self.booklet(booklet_source)
            booklet_lang = booklet.language
            chunks = booklet.chunks
        else:
            booklet, retriever = None, None
            booklet_lang = detect_language(gold_reference or claim)
            raw_paras = [p.strip() for p in (gold_reference or "").split("\n\n") if p.strip()]
            if not raw_paras and gold_reference:
                raw_paras = [gold_reference.strip()]
            chunks = []
            pos = 0
            for idx, p in enumerate(raw_paras):
                chunks.append(Chunk(idx, 1, p, "Reference", "Reference", "", pos, pos + len(p)))
                pos += len(p) + 2
            if mode not in ("easy", "oracle", "claim-only"):
                mode = "easy"

        claim_lang = claim_lang or detect_language(claim)
        translation = None
        if (
            self.opt.translate
            and claim_lang != booklet_lang
            and mode != "claim-only"
            and (mode != "easy" or self.opt.translate_reference)
        ):
            translation = self._translate(claim, claim_lang, booklet_lang, usage)
            if self.committee_terms:
                translation = committee_terms(claim, translation, booklet_lang)
        queries = [claim] + ([translation] if translation else [])

        region = [c.id for c in chunks]
        proposal = ""
        vote_translation = None
        if booklet is not None:
            if self.opt.scope == "vote" and vote:
                vote_lang = foreign_title(vote, booklet_lang, retriever.bm25.idf) if self.opt.translate else None
                if vote_lang:
                    vote_translation = self._translate(vote, vote_lang, booklet_lang, usage, "translate-vote")
                region, proposal = locate(booklet, vote_translation or vote)
            elif self.opt.scope == "claim" or (self.opt.scope == "vote" and not vote):
                region, proposal = locate(booklet, " ".join(queries))

        hits, best, anchor, retrieved = [], 0.0, "none", []
        if mode not in ("baseline", "easy", "oracle", "claim-only", "full") and retriever is not None:
            hits, best, anchor = self._hits(
                booklet_source,
                booklet,
                retriever,
                queries,
                claim,
                claim_lang,
                region,
                translation,
                usage,
            )
            retrieved = retriever.expand(hits, self.opt.neighbors)
        elif mode in ("easy", "oracle") and not booklet:
            hits = list(region)
            retrieved = list(region)
            best = 1.0
            anchor = "reference"

        state = {}

        def run(ids, step, model=None):
            passages = self._render(booklet, ids) if booklet is not None else [chunks[i].render() for i in ids]
            chk, note = self._number_note(claim, passages, [chunks[i].text for i in region])
            judge_lang, judge_translation, judge_passages = booklet_lang, translation, passages
            if self.opt.translate_passages and claim_lang != booklet_lang and passages:
                rec = self.llm.chat(translate_passages_messages(passages, booklet_lang, claim_lang), usage,
                                    "translate-passages", **translate_passages_params(len(passages)))
                try:
                    out = json.loads(rec["content"]).get("passages", [])
                except (json.JSONDecodeError, AttributeError):
                    out = []
                if len(out) == len(passages) and all(isinstance(x, str) and x.strip() for x in out):
                    judge_lang, judge_translation, judge_passages = claim_lang, None, out
            result = self._judge(
                judge_passages,
                claim,
                claim_lang,
                judge_lang,
                judge_translation,
                usage,
                step,
                note,
                model,
            )
            result["ids"] = [ids[e - 1] for e in result["evidence"] if 0 <= e - 1 < len(ids)]
            result["numbers"] = chk
            state["passages"] = passages
            state["ids"] = ids
            return result

        if mode in ("oracle", "easy"):
            gold = [
                p.strip() for p in (gold_reference or "").split("\n\n") if p.strip()
            ]
            if not gold and gold_reference:
                gold = [gold_reference.strip()]
            state["passages"] = gold
            chk, note = self._number_note(claim, gold, gold)
            result = self._judge(
                gold,
                claim,
                claim_lang,
                booklet_lang,
                translation,
                usage,
                mode,
                note,
            )
            matching_ids = []
            if result.get("evidence"):
                for e in result["evidence"]:
                    if 0 <= e - 1 < len(chunks):
                        matching_ids.append(chunks[e - 1].id)
            result["ids"] = matching_ids
            result["numbers"] = chk
        elif mode == "baseline":
            pages = [
                (n, f"(p. {n}) {t}")
                for n, t in enumerate(page_texts(booklet_source), start=1)
                if t
            ]
            state["passages"] = [p for _, p in pages]
            result = self._judge(
                state["passages"],
                claim,
                claim_lang,
                booklet_lang,
                translation,
                usage,
                "baseline",
            )
            cited_pages = {pages[e - 1][0] for e in result["evidence"] if 0 <= e - 1 < len(pages)}
            result["ids"] = [c.id for c in chunks if c.page in cited_pages]
            result["numbers"] = None
        elif mode == "claim-only":
            result = self._judge(
                [], claim, claim_lang, booklet_lang, None, usage, "claim-only"
            )
            result["ids"], result["numbers"] = [], None
        elif mode == "full":
            result = run([c.id for c in chunks], "full")
        elif mode == "section":
            result = run(
                region if proposal else (retriever.section_of(hits[:1]) if retriever else region), "section"
            )
        elif mode == "pages":
            wider = retriever.pages_around(hits[:3]) if retriever else region
            result = run(
                sorted(set(wider) | set(retrieved)), "pages"
            )
        else:
            result = run(retrieved, "retrieval")
            if mode == "ladder":
                unsure = (
                    result["confidence"] is not None
                    and result["confidence"] < self.opt.tau
                )
                unsupported = result["label"] != "neutral" and not result["evidence"]
                if unsure or unsupported:
                    wider = (
                        retriever.pages_around(hits[:3])
                        if (self.opt.escalate == "pages" and retriever)
                        else region
                    )
                    result = run(sorted(set(wider) | set(retrieved)), self.opt.escalate)

        chk = result.get("numbers")
        if "rule" in self.opt.numbers and chk and chk["missing_scope"] and result["label"] == "entailment":
            result = dict(result, label="neutral", step=result["step"] + "+numrule")

        facts = None
        if (
            self.decompose
            and (mode != "easy" or self.opt.decompose is True)
            and result["confidence"] is not None
            and result["confidence"] < self.opt.tau_decompose
            and mode != "claim-only"
        ):
            agg, facts = self._decompose(
                state.get("passages", []), claim, translation, usage
            )
            if agg:
                result = dict(result, label=agg, step=result["step"] + "+decompose")
        recheck = None
        first = result["label"]
        if (
            ((self.recheck and first == "neutral") or (self.opt.recheck_entailment and first == "entailment"))
            and mode not in ("claim-only", "baseline", "easy", "oracle")
            and state.get("passages")
            and best >= self.opt.recheck_min_bm25
        ):
            ids, passages = state.get("ids") or [], state["passages"]
            if self.opt.recheck_context == "hits" and booklet is not None and hits:
                ids = list(hits)
                passages = self._render(booklet, ids)
            recheck = self._recheck(passages, claim, claim_lang, booklet_lang, translation, usage, first)
            tau = self.opt.tau_recheck if first == "neutral" else self.opt.tau_recheck_entailment
            if recheck["p_contradiction"] >= tau:
                n = recheck["passage"]
                result = dict(
                    result,
                    label="contradiction",
                    step=result["step"] + "+recheck",
                    confidence=recheck["p_contradiction"],
                    ids=[ids[n - 1]] if 1 <= n <= len(ids) else [],
                )
        if (
            self.opt.cascade
            and self.opt.cascade != self.llm.model
            and result["confidence"] is not None
            and result["confidence"] < self.opt.tau_cascade
            and mode not in ("claim-only",)
        ):
            passages = state.get("passages", [])
            ids_before = result.get("ids", [])
            big = self._judge(
                passages,
                claim,
                claim_lang,
                booklet_lang,
                translation,
                usage,
                "cascade",
                None,
                self.opt.cascade,
            )
            big["ids"] = (
                ids_before
                if mode in ("oracle", "easy", "baseline")
                else [state["ids"][e - 1] for e in big["evidence"] if 0 <= e - 1 < len(state.get("ids", []))]
            )
            big["numbers"] = result.get("numbers")
            result = big

        label = result["label"]
        lbl_int = LABELS[label]
        cited = [] if lbl_int == 1 else result.get("ids", [])[: self.opt.max_evidence]
        spans = []
        if lbl_int != 1:
            pool = []
            if mode in ("easy", "oracle"):
                if booklet is not None and gold_reference:
                    pool = gold_chunks(booklet, gold_reference)
                if not pool:
                    pool = [c.id for c in chunks]
            elif mode == "baseline":
                pool = list(result.get("ids", []))
            else:
                pool = list(cited) + [i for i in hits[: self.opt.k] if i not in cited]
            if not pool:
                allowed = set(region)
                if retriever is not None:
                    pool = [i for i in retriever.rank(queries)[0] if i in allowed][: self.opt.k]
                else:
                    pool = [c.id for c in chunks]
            idf = retriever.bm25.idf if retriever is not None else None
            boost = {}
            if booklet is not None and mode not in ("easy", "oracle") and (
                self.opt.evidence_section != 1.0 or self.opt.evidence_section_pool
            ):
                kinds = self.kinds(booklet)
                cue = claim_cue(claim, translation)
                if self.opt.evidence_section_pool:
                    want, allowed = PREFER.get(cue, set()), set(region)
                    extra = [i for i in retriever.rank(queries)[0] if i in allowed and kinds[i] in want]
                    pool += [i for i in extra[: self.opt.evidence_section_pool] if i not in pool]
                boost = factors(kinds, cue, pool, self.opt.evidence_section)
            spans = sentences.select(
                [chunks[i] for i in pool if i < len(chunks)],
                ([translation] if translation else []) + [claim],
                idf,
                preferred=cited,
                bonus=self.opt.evidence_bonus,
                factors=boost,
            )
            for sp in spans:
                sp.pop("score", None)

        evidence = []
        if lbl_int != 1:
            if spans and self.opt.evidence_unit == "paragraph":
                seen = []
                for sp in spans:
                    if sp["chunk_id"] not in seen:
                        seen.append(sp["chunk_id"])
                evidence = [{"page": int(chunks[i].page), "text": str(chunks[i].text)} for i in seen]
            elif spans:
                evidence = [{"page": int(s["page"]), "text": str(s["text"])} for s in spans]
            elif cited:
                evidence = [{"page": int(chunks[i].page), "text": str(chunks[i].text)} for i in cited]
            else:
                fallback = retrieved or hits
                if not fallback and retriever is not None:
                    allowed = set(region)
                    fallback = [i for i in retriever.rank(queries)[0] if i in allowed]
                fallback = fallback or list(region)
                if fallback:
                    evidence = [{"page": int(chunks[fallback[0]].page), "text": str(chunks[fallback[0]].text)}]

        u = usage.summary()
        latency_ms = int(round((time.perf_counter() - t0) * 1000))
        metrics = {
            "input_tokens": int(u["prompt_tokens"]),
            "output_tokens": int(u["completion_tokens"]),
            "inference_time_ms": latency_ms,
        }
        rnd = lambda d: {k: round(v, 4) for k, v in d.items()} if d else None  # noqa: E731
        return {
            "id": str(case_id or ""),
            "label": lbl_int,
            "label_name": label,
            "evidence": evidence,
            "metrics": metrics,
            "decision": lbl_int,
            "answer": ANSWERS[label],
            "page": spans[0]["page"] if spans else (evidence[0]["page"] if evidence else None),
            "evidence_sentence": spans[0]["text"] if spans else (evidence[0]["text"] if evidence else None),
            "evidence_sentences": spans,
            "entailment_label": lbl_int,
            "confidence": round(result["confidence"], 4)
            if result["confidence"] is not None
            else None,
            "probs": rnd(result["probs"]),
            "raw_probs": rnd(result.get("raw_probs")),
            "ladder_step": result["step"],
            "claim_language": claim_lang,
            "booklet_language": booklet_lang,
            "translation": translation,
            "vote_translation": vote_translation,
            "proposal": proposal,
            "region_size": len(region),
            "hits": hits,
            "retrieved_ids": retrieved,
            "bm25_best": round(best, 3),
            "anchor": anchor,
            "numbers": result.get("numbers"),
            "facts": facts,
            "recheck": recheck,
            "usage": u,
            "latency_s": round(time.perf_counter() - t0, 3),
            "model": self.llm.model,
            "mode": mode,
            "prompt_version": self.opt.prompt,
        }
