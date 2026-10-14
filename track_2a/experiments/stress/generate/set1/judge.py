"""Step 3: blind check by two other open models (Gemma 4 31B, Qwen3-235B-A22B-2507).

The judge sees only the claim and the text of the whole proposal in the booklet (booklet language,
with page markers) – no label, no evidence, not the page used for generation.
python judge.py gemma|qwen  → data/judge_<name>.jsonl (resumable)
"""

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from common import DATA, SPEC, openrouter, parse_json, proposal_text

JUDGES = {
    "gemma": ("google/gemma-4-31b-it", 4),
    "qwen": ("qwen/qwen3-235b-a22b-2507", 4),
}
RANGES = {key: (date, rng) for date, key, rng, _ in SPEC}

SYSTEM = """You are an annotator for a natural language inference (NLI) benchmark on Swiss federal voting booklets.
You get a CLAIM (German, French or Italian) and the BOOKLET TEXT about one proposal (the official explanations of the
Federal Council; its language may differ from the claim). Decide, using only the BOOKLET TEXT:
- "entailment": the booklet text supports the claim.
- "contradiction": the booklet text states something incompatible with the claim (other number, actor, direction,
  recommendation, or a negation of what it says).
- "neutral": the booklet text neither supports nor contradicts the claim (e.g. the claim adds facts, numbers or
  positions that the text does not give).
Attribution phrases ("the Federal Council thinks", "the committee argues", "according to the summary") name whose
statement it is; if the booklet attributes the opposite view to that speaker, it is a contradiction. Do not use
outside knowledge, even if you know the claim is true or false in reality.
Answer with one JSON object only:
{"label": "entailment|neutral|contradiction", "page": <PDF page number of the deciding text or null>,
 "quote": "the deciding sentence copied from the booklet text, or empty for neutral", "reason": "one short sentence"}"""


def main():
    name = sys.argv[1]
    model, workers = JUDGES[name]
    rows = [json.loads(x) for x in (DATA / "candidates.jsonl").open(encoding="utf-8")]
    rows = [r for r in rows if not r["checks"]]
    out_path = DATA / f"judge_{name}.jsonl"
    done = {}
    if out_path.exists():
        for line in out_path.open(encoding="utf-8"):
            j = json.loads(line)
            if j.get("label"):
                done[j["id"]] = j
    todo = [r for r in rows if r["id"] not in done]
    if name == "qwen" and "--all" not in sys.argv:
        # Budget: run Qwen only where Gemma agrees with the generator (otherwise the item is disputed anyway).
        gemma = {}
        for line in (DATA / "judge_gemma.jsonl").open(encoding="utf-8"):
            j = json.loads(line)
            if j.get("label"):
                gemma[j["id"]] = j["label"]
        todo = [r for r in todo if gemma.get(r["id"]) == r["label_name"]]
    print(f"{name}: {len(done)} done, {len(todo)} to do", flush=True)
    lock = threading.Lock()

    def one(r):
        date, rng = RANGES[r["proposal_key"]]
        text = proposal_text(date, rng, r["booklet_language"])
        msg = f"CLAIM: {r['claim']}\n\nPROPOSAL: {r['vote']}\n\nBOOKLET TEXT:\n{text}"
        rec = {"id": r["id"], "model": model}
        try:
            msgs = [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": msg},
            ]
            resp = None
            if (
                name == "gemma"
            ):  # free variant first; on 429 the paid variant of the same model
                try:
                    resp = openrouter(
                        model + ":free", msgs, max_tokens=1500, temperature=0, retries=1
                    )
                except Exception:  # noqa: BLE001
                    resp = None
            if resp is None:
                resp = openrouter(model, msgs, max_tokens=1500, temperature=0)
            rec["served_model"] = resp.get("model")
            content = resp["choices"][0]["message"].get("content") or ""
            rec["raw"] = content
            rec["usage"] = resp.get("usage")
            obj = parse_json(content)
            lab = str(obj.get("label", "")).strip().lower()
            rec.update(
                label=lab
                if lab in ("entailment", "neutral", "contradiction")
                else None,
                page=obj.get("page"),
                quote=obj.get("quote"),
                reason=obj.get("reason"),
            )
        except Exception as exc:  # noqa: BLE001
            rec["error"] = repr(exc)[:300]
        with lock:
            with out_path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, todo))
    got = [json.loads(x) for x in out_path.open(encoding="utf-8")]
    print(
        name,
        "labelled:",
        sum(1 for j in got if j.get("label")),
        "errors:",
        sum(1 for j in got if not j.get("label")),
    )


if __name__ == "__main__":
    main()
