import json
import math
import re

PROMPT_VERSION = "nli-v1"
REASONING_PROMPTS = {"nli-v3", "nli-v5"}
LANG_NAMES = {"de": "German", "fr": "French", "it": "Italian"}

SYSTEM = """You check claims against the official Swiss voting booklet ("Explanations of the Federal Council"). You get numbered passages from one booklet and a claim. Judge the claim ONLY by what the passages say. Do not use outside knowledge and do not judge whether the claim is true in the world.

Labels:
- entailment: the passages state the claim or directly imply it. Paraphrase, translation and rounding are fine.
- contradiction: the passages state something incompatible with the claim, e.g. a different number, date or amount, the opposite direction or recommendation, a negation, a different actor, or a stronger or weaker obligation.
- neutral: the passages do not cover what the claim says, or cover the topic but neither confirm nor refute the specific statement.

Check attribution: if the claim says the Federal Council, Parliament, the committee or the legal text says something, the passages must show that this actor says it. Check every detail of the claim (numbers, dates, who, what, conditions). If one detail is contradicted, answer contradiction. If one essential detail is missing and nothing contradicts the claim, answer neutral.

Answer in JSON: first "evidence", the numbers of the passages that decide the label (empty list if neutral), then "label"."""

SYSTEM_V2 = """You check claims against the official Swiss voting booklet ("Explanations of the Federal Council"). You get numbered passages from one booklet and a claim. Judge the claim ONLY by what the passages say. Do not use outside knowledge and do not judge whether the claim is true in the world.

Labels:
- entailment: the passages state the claim or directly imply it. Paraphrase, translation, other number formats and rounding are fine ("9.5 million" = "nine and a half million").
- contradiction: the passages say something incompatible about the SAME thing: a different value for the same number, date or amount, the opposite direction, the opposite recommendation or position of the same actor, or an explicit negation.
- neutral: the passages do not mention the specific detail the claim states (a number, date, forecast, measure, condition), even if they discuss the topic. A missing detail is NOT a contradiction.

Who says what: each passage starts with its context in parentheses (proposal, section heading, and a note when the text comes from the initiative or referendum committee). Text without such a note is the official explanation of the Federal Council and Parliament; "Federal Council and Parliament" covers claims about either of them, and the Federal Assembly is the Parliament.
- A claim that the Federal Council or Parliament argues X is entailed only by their own text. If only the committee says X and the Federal Council says the opposite, it is a contradiction. If only the committee says X and the Federal Council says nothing about X, it is neutral.
- Phrases like "according to the voting text", "the booklet says" or "it is claimed" refer to the booklet as a whole, not only to the legal text.

Answer in JSON: first "evidence", the numbers of the passages that decide the label (empty list if neutral), then "label"."""

SYSTEM_V3 = SYSTEM_V2.replace(
    'Answer in JSON: first "evidence", the numbers of the passages that decide the label (empty list if neutral), then "label".',
    'Answer in JSON: first "evidence", the numbers of the passages that decide the label (empty list if neutral), then "check", one or two short sentences that compare the claim detail by detail with the passages (who says it, numbers, dates, direction), then "label".',
)

_DOMAIN = """

Booklet conventions: the official text (without a committee note in the context) is the position of the Federal Council and Parliament, so it supports claims about either of them; the Federal Assembly is the Parliament. Phrases like "according to the voting text", "the booklet says" or "it is claimed" refer to the booklet as a whole, not only to the legal text. Text marked as coming from a committee is the committee's position, not the Federal Council's."""
_ANSWER = '\n\nAnswer in JSON: first "evidence"'
SYSTEM_V4 = SYSTEM.replace(_ANSWER, _DOMAIN + _ANSWER)
SYSTEM_V5 = SYSTEM_V4.replace(
    'then "label".',
    'then "check", one or two short sentences that compare the claim detail by detail with the passages (who says it, numbers, dates, direction), then "label".',
)

SYSTEM_V6 = SYSTEM.replace(
    """- contradiction: the passages state something incompatible with the claim, e.g. a different number, date or amount, the opposite direction or recommendation, a negation, a different actor, or a stronger or weaker obligation.
- neutral: the passages do not cover what the claim says, or cover the topic but neither confirm nor refute the specific statement.""",
    """- contradiction: the passages make a statement about the same point as the claim, but with a different detail: another number, date, amount or duration, another actor, the opposite position, recommendation or direction, a negation, another scope or condition, or a stronger or weaker obligation.
- neutral: the passages make no statement about the point of the claim. They may discuss the topic, but they neither confirm nor refute the specific statement.

Most claims restate one statement of the booklet, sometimes with one detail changed. Find the passage with the closest statement and compare it with the claim before you decide.""",
)

PROMPTS = {
    "nli-v1": SYSTEM,
    "nli-v2": SYSTEM_V2,
    "nli-v3": SYSTEM_V3,
    "nli-v4": SYSTEM_V4,
    "nli-v5": SYSTEM_V5,
    "nli-v6": SYSTEM_V6,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "evidence": {"type": "array", "items": {"type": "integer"}, "maxItems": 4},
        "label": {"type": "string", "enum": ["entailment", "neutral", "contradiction"]},
    },
    "required": ["evidence", "label"],
    "additionalProperties": False,
}


def user_message(
    passages, claim, claim_lang, booklet_lang, translation=None, note=None
):
    lines = [f"[{i}] {p}" for i, p in enumerate(passages, start=1)]
    body = (
        "Passages from the booklet:\n" + "\n".join(lines)
        if lines
        else "Passages from the booklet: (none)"
    )
    claim_part = f"Claim ({LANG_NAMES.get(claim_lang, claim_lang)}): {claim}"
    if translation:
        claim_part += f"\nClaim translated to {LANG_NAMES.get(booklet_lang, booklet_lang)}: {translation}"
    if note:
        claim_part += f"\nNote: {note}"
    return f"{body}\n\n{claim_part}"


def build_messages(
    passages,
    claim,
    claim_lang,
    booklet_lang,
    translation=None,
    prompt=PROMPT_VERSION,
    examples=(),
    note=None,
):
    messages = [{"role": "system", "content": PROMPTS[prompt]}]
    for ex in examples:
        messages.append(
            {
                "role": "user",
                "content": user_message(
                    ex["passages"],
                    ex["claim"],
                    ex["claim_language"],
                    ex["booklet_language"],
                ),
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    {"evidence": ex["evidence"], "label": ex["label"]}
                ),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": user_message(
                passages, claim, claim_lang, booklet_lang, translation, note
            ),
        }
    )
    return messages


SCHEMA_REASONING = {
    "type": "object",
    "properties": {
        "evidence": {"type": "array", "items": {"type": "integer"}, "maxItems": 4},
        "check": {"type": "string", "maxLength": 400},
        "label": {"type": "string", "enum": ["entailment", "neutral", "contradiction"]},
    },
    "required": ["evidence", "check", "label"],
    "additionalProperties": False,
}


def nli_params(prompt=PROMPT_VERSION):
    reasoning = prompt in REASONING_PROMPTS
    schema = SCHEMA_REASONING if reasoning else SCHEMA
    max_tokens = 220 if reasoning else 60
    return {
        "temperature": 0,
        "max_tokens": max_tokens,
        "logprobs": True,
        "top_logprobs": 10,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "nli", "schema": schema, "strict": True},
        },
    }


def label_probs(rec):
    """Probability of each label from the first token of the label value."""
    lp = rec.get("logprobs")
    if not lp:
        return None
    text, starts = "", []
    for t in lp:
        starts.append(len(text))
        text += t["token"]
    m = re.search(r'"label"\s*:\s*"', text)
    if not m:
        return None
    pos = m.end()
    idx = next((i for i, s in enumerate(starts) if s + len(lp[i]["token"]) > pos), None)
    if idx is None:
        return None
    mass = {"entailment": 0.0, "neutral": 0.0, "contradiction": 0.0}
    for tok, logprob in lp[idx]["top"]:
        t = tok.strip().strip('"').lower()
        for name in mass:
            if t and name.startswith(t[:3]) and len(t) >= 1:
                mass[name] += math.exp(logprob)
                break
    total = sum(mass.values())
    if total <= 0:
        return None
    return {k: v / total for k, v in mass.items()}


def parse(rec, n_passages):
    content = rec.get("content", "")
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        try:
            data = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            data = {}
    if not isinstance(data, dict):
        data = {}
    label = data.get("label")
    if label not in ("entailment", "neutral", "contradiction"):
        low = content.lower()
        label = next(
            (x for x in ("contradiction", "entailment", "neutral") if x in low), None
        )
    evidence = []
    for e in data.get("evidence", []) or []:
        try:
            e = int(str(e).strip("P[] "))
        except ValueError:
            continue
        if 1 <= e <= n_passages and e not in evidence:
            evidence.append(e)
    return label, evidence


TRANSLATE_SYSTEM = "You translate short political claims between German, French and Italian. Keep numbers, names and meaning exactly. Output only the translation."


def translate_messages(claim, src, dst):
    return [
        {"role": "system", "content": TRANSLATE_SYSTEM},
        {
            "role": "user",
            "content": f"Translate from {LANG_NAMES.get(src, src)} to {LANG_NAMES.get(dst, dst)}:\n{claim}",
        },
    ]


RELEVANCE_SYSTEM = "You help to fact-check claims against an official Swiss voting booklet. Decide whether the passage contains information that supports or contradicts the claim (numbers, dates, actors, positions, rules). Answer only yes or no."


def relevance_messages(passage, claim):
    return [
        {"role": "system", "content": RELEVANCE_SYSTEM},
        {"role": "user", "content": f"Claim: {claim}\n\nPassage: {passage}\n\nIs the passage relevant for checking the claim? Answer yes or no."},
    ]


def yes_prob(rec):
    lp = rec.get("logprobs")
    if not lp:
        t = rec.get("content", "").strip().lower()
        return 1.0 if t.startswith("yes") else 0.0
    yes = no = 0.0
    for tok, logprob in lp[0]["top"]:
        t = tok.strip().lower()
        if t.startswith("yes") or t == "y":
            yes += math.exp(logprob)
        elif t.startswith("no") or t == "n":
            no += math.exp(logprob)
    return yes / (yes + no) if yes + no > 0 else 0.0


DECOMPOSE_SYSTEM = "Split a political claim into its atomic factual statements, so that each can be checked on its own: who says or does what, each number, date or amount, each condition. Keep the wording and language of the claim and keep the attribution (for example \"The Federal Council says that ...\") in every statement. Return 1 to 4 statements."

DECOMPOSE_SCHEMA = {
    "type": "object",
    "properties": {"facts": {"type": "array", "items": {"type": "string", "maxLength": 300}, "minItems": 1, "maxItems": 4}},
    "required": ["facts"],
    "additionalProperties": False,
}


def decompose_messages(claim):
    return [
        {"role": "system", "content": DECOMPOSE_SYSTEM},
        {"role": "user", "content": f"Claim: {claim}"},
    ]


def decompose_params():
    return {
        "temperature": 0,
        "max_tokens": 300,
        "response_format": {"type": "json_schema", "json_schema": {"name": "facts", "schema": DECOMPOSE_SCHEMA, "strict": True}},
    }


def verify_facts_params(n):
    schema = {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {"type": "string", "enum": ["entailment", "neutral", "contradiction"]},
                "minItems": n,
                "maxItems": n,
            }
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    }
    return {
        "temperature": 0,
        "max_tokens": 20 + 8 * n,
        "response_format": {"type": "json_schema", "json_schema": {"name": "verdicts", "schema": schema, "strict": True}},
    }


def verify_facts_messages(passages, facts, prompt=PROMPT_VERSION):
    system = PROMPTS[prompt].split("\n\nAnswer in JSON")[0] + "\n\nYou get several statements. Answer in JSON with \"verdicts\", one label per statement in the given order."
    lines = "\n".join(f"[{i}] {p}" for i, p in enumerate(passages, start=1)) or "(none)"
    facts_part = "\n".join(f"{i}. {f}" for i, f in enumerate(facts, start=1))
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Passages from the booklet:\n{lines}\n\nStatements:\n{facts_part}"},
    ]


def aggregate(verdicts):
    if not verdicts:
        return None
    if "contradiction" in verdicts:
        return "contradiction"
    if all(v == "entailment" for v in verdicts):
        return "entailment"
    return "neutral"


RECHECK_SYSTEM = """You check one claim against numbered passages from the official Swiss voting booklet. A first reading found that the passages neither confirm nor refute the claim. Look again, only for a contradiction.

A contradiction: the passages speak about the same thing as the claim but state a different detail, e.g. another number, percentage, amount, date or duration; another actor who decides, pays or is responsible; the opposite position or recommendation of the same actor; the opposite direction (more or less, allowed or forbidden, yes or no); another scope or condition.
Not a contradiction: the passages do not mention the claim's detail at all, or only discuss the topic in general.

Answer in JSON: "claim_detail", the decisive detail of the claim (short); "passage", the number of the passage that speaks about the same thing (0 if none); "passage_detail", what that passage says about it (short, empty if none); then "verdict"."""

RECHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_detail": {"type": "string", "maxLength": 200},
        "passage": {"type": "integer"},
        "passage_detail": {"type": "string", "maxLength": 200},
        "verdict": {"type": "string", "enum": ["contradiction", "no_contradiction"]},
    },
    "required": ["claim_detail", "passage", "passage_detail", "verdict"],
    "additionalProperties": False,
}


RECHECK_ENTAILED_SYSTEM = RECHECK_SYSTEM.replace(
    "A first reading found that the passages neither confirm nor refute the claim. Look again, only for a contradiction.",
    "A first reading found that the passages support the claim. Look again, only for a contradiction: check who holds the position, the direction and every detail.",
)


def recheck_messages(passages, claim, claim_lang, booklet_lang, translation=None, first="neutral"):
    system = RECHECK_ENTAILED_SYSTEM if first == "entailment" else RECHECK_SYSTEM
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message(passages, claim, claim_lang, booklet_lang, translation)},
    ]


def recheck_params():
    return {
        "temperature": 0,
        "max_tokens": 200,
        "logprobs": True,
        "top_logprobs": 10,
        "response_format": {"type": "json_schema", "json_schema": {"name": "recheck", "schema": RECHECK_SCHEMA, "strict": True}},
    }


def contradiction_prob(rec):
    """Probability of "contradiction" from the first token of the verdict value; None without logprobs."""
    lp = rec.get("logprobs")
    content = rec.get("content", "")
    if not lp:
        return 1.0 if '"verdict": "contradiction"' in content.replace('":"', '": "') else 0.0
    text, starts = "", []
    for t in lp:
        starts.append(len(text))
        text += t["token"]
    m = re.search(r'"verdict"\s*:\s*"', text)
    if not m:
        return None
    idx = next((i for i, s in enumerate(starts) if s + len(lp[i]["token"]) > m.end()), None)
    if idx is None:
        return None
    yes = no = 0.0
    for tok, logprob in lp[idx]["top"]:
        t = tok.strip().strip('"').lower()
        if t and "contradiction".startswith(t[:4]) and len(t) >= 2:
            yes += math.exp(logprob)
        elif t and "no_contradiction".startswith(t[:2]):
            no += math.exp(logprob)
    return yes / (yes + no) if yes + no > 0 else None


TRANSLATE_PASSAGES_SYSTEM = "You translate numbered passages of a Swiss voting booklet. Translate every passage completely and keep its number, the text in parentheses at its start, all numbers, names and the meaning exactly. Use the official Swiss terms of the target language."


def translate_passages_messages(passages, src, dst):
    lines = "\n".join(f"[{i}] {p}" for i, p in enumerate(passages, start=1))
    return [
        {"role": "system", "content": TRANSLATE_PASSAGES_SYSTEM},
        {"role": "user", "content": f"Translate from {LANG_NAMES.get(src, src)} to {LANG_NAMES.get(dst, dst)}. Answer in JSON with \"passages\", one translation per passage in the given order.\n\n{lines}"},
    ]


def translate_passages_params(n):
    schema = {
        "type": "object",
        "properties": {"passages": {"type": "array", "items": {"type": "string"}, "minItems": n, "maxItems": n}},
        "required": ["passages"],
        "additionalProperties": False,
    }
    return {
        "temperature": 0,
        "max_tokens": 4000,
        "response_format": {"type": "json_schema", "json_schema": {"name": "passages", "schema": schema, "strict": True}},
    }
