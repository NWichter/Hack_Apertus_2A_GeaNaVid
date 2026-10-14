# Academia Challenges

Submissions must use the Apertus model family.
For Track 2 this means that submitted solutions must be built with Apertus. Other open-weights models can be used to support development, e.g. as automatic judges during evaluation. Their role must be clearly described in the submission report.

💬 In case you have questions, join the conversation on Discord or send an email to “hello@hackapertus.ch”

## How it works

Pick from 5 academia challenges provided by Swiss academic institutions:

- **FHGR:** AI-Powered Job Interview Coach
- **OpenParlData:** Extracting Parliamentary Affairs from PDFs into One Common Structure
- **OST:** Multilingual Natural Language Inference over Swiss Official Voting Booklets
- **UZH:** Detecting Cross-Lingual Semantic Differences in Swiss Government Websites
- **ZHAW:** See It, Say It, Pick It: Vision-Language Grounding for a Real Robot Arm

The challenges incl. submission and judging criteria are described in our **Getting Started guide**:
https://hackapertus.notion.site/getting-started-guide-onlinehack

## Run it

GeaNaVid ships the CLI `booklint`: a voting booklet (PDF path or bk.admin.ch URL), a claim in German,
French or Italian and optionally the title of the proposal (`vote`) go in; the decision (0 entailment = yes,
1 neutral = blank, 2 contradiction = no), for yes and no the page and the sentence of the booklet that decides
it and the cited passages, token usage and time come out.

From `track_2a/`:

```bash
cp .env.example .env          # set LLM_NAME, LLM_BASE_URL, LLM_API_KEY (OpenAI-compatible Apertus endpoint)
make test                     # unit tests in a Python container, no model calls
make run                      # Docker: default pipeline on the test split data/v1/test_v11.jsonl (493 claims, OST v1.1)
make run LIMIT=30             # quick check
make run MODES=retrieval,baseline   # plus the whole-booklet baseline (~20 k tokens per claim)
make ost ROWS=20              # OST's contract: 20 test rows as task A and B through the image, scored like evaluate.py
```

All targets run in Docker and also work from the repository root.

`make run` prints a table (macro-F1 with 95 % bootstrap interval, F1 per class, macro-F1 for same- and
cross-language claims, retrieval hit@5, tokens (all and input only) and Apertus calls per claim, Apertus
seconds, `inference_time_ms` mean and p95) and writes it to
`runs/make-run/summary.md`, with one prediction file per model and mode next to it.

## OST task format

**The image follows OST's Solution API Guide (2026-10-07) and starter repository.** OST runs:

```bash
docker build --platform linux/amd64 -t geanavid .
docker run --rm --platform linux/amd64 -e BASE_URL -e API_KEY \
  -v /abs/path/data:/data:ro -v /abs/path/output:/output \
  geanavid --input /data/cases.jsonl --output /output/predictions.jsonl
```

**Model.** The image default is Apertus v1.5 70B (`ENV LLM_NAME=swiss-ai/Apertus-v1.5-70B` in the `Dockerfile`):
macro-F1 0.965 on the OST v1.1 test split, fewer input tokens than 8B (1,461 vs 2,159) and more robust on older
booklets (stress set). `-e LLM_NAME=apertus-v1.5-8b` runs the faster 8B pipeline.

`BASE_URL` and `API_KEY` (injected by OST at run time) take precedence over `LLM_BASE_URL` / `LLM_API_KEY` and
any `.env`; no key is baked into the image. `booklet.path` is relative to `/data` (`BOOKLET_ROOT=/data` in the
image). The model is `LLM_NAME` (image default `swiss-ai/Apertus-v1.5-70B`). At start one test call checks the name. If the endpoint answers
that the model does not exist (400/404/422, or 401/403 naming the model), the Apertus model of the same size is
taken from its `/models` list, or, without a list, the first of the known spellings it accepts
(`swiss-ai/Apertus-v1.5-70B`, `swiss-ai/Apertus-v1.5-70B-Instruct`, `apertus-v1.5-70b`, ... and the 8B forms; v1.5 names only;
`CANDIDATES` in `src/booklint/llm.py`). Every switch and every failure is printed on stderr with `WARNING`, and
the run ends with a count of failed cases, so a wrong name never turns into silent neutral answers.
The same works without Docker as `booklint --input cases.jsonl --output predictions.jsonl`.

Input, one JSON object per line, task A and B mixed:

- **A (Advanced, document):** `{"id", "vote", "claim": {"text", "language"}, "booklet": {"path", "language"}}`:
  the system finds the evidence in the PDF.
- **B (Beginner, reference):** `{"id", "vote", "claim": {"text", "language"}, "reference": {"text", "language"}}`:
  the claim is compared with the reference.

Also read: a JSON list or one object, a wrapper `{"cases": [...]}`, a UTF-8 BOM, CRLF, flat fields
(`claim` as a string, `booklet_path`, `reference_string`, `hypothesis` / `premise`), `vote` as an object, ids as
numbers; a line that is not valid JSON becomes a failed case instead of stopping the run. Without a language
field the claim language is detected; a `vote` title in another language than the booklet is translated by
Apertus before the proposal is located.

Output, one line per case (`--format json` writes one JSON list instead):

```json
{"id": "case-0042", "label": 0, "label_name": "entailment",
 "evidence": [{"page": 7, "text": "…verbatim sentence…"}, {"page": 9, "text": "…"}],
 "metrics": {"input_tokens": 1650, "output_tokens": 40, "inference_time_ms": 1820}}
```

- `evidence` (entailment and contradiction): up to five verbatim sentences from different passages, best
  first, each with its 1-based PDF page; OST scores a case if one of the first five lies in the gold passage.
  Task B evidence has `"page": null`, as OST asks. Neutral: `[]`. `--evidence-unit paragraph` returns whole
  text blocks instead of sentences.
- `metrics` holds the input and output tokens reported by the API and the wall time of the case in ms (with a
  warm response cache this is not inference time; use `--no-cache` for timing). OST measures tokens through
  its proxy and time itself.
- A case that fails (missing PDF, no text layer, endpoint error, missing claim) never stops the batch: it is
  answered neutral with empty evidence, zero metrics and an extra field `error`, and a line goes to stderr.
  The run exits with code 0.

**Check it like OST.** `make ost ROWS=20` writes OST-format cases with their booklets
(`experiments/v1/ost_cases.py`), runs the image exactly as above with `/data` read-only and scores the output with
`experiments/v1/ost_score.py`, which applies the rules of `evaluate.py` from OST's starter repository (macro-F1 per
task, evidence found if one of the first five quotes lies in the gold passage). On all 986 cases of the test split
(every row as task A and as task B) it gives the same numbers as OST's script: task A 0.965 with 312 of 324 evidence
cases, task B 0.974 (70B, run of 14 October evening, `runs/v1/test_v11/ost-docker-full-1014b/`; the earlier run of
the same day, `ost-docker-full-1014/`, gave task A 0.965 and task B 0.976: the endpoint is not fully deterministic).

**Paths.** A relative booklet path is read below `BOOKLET_ROOT`; a path that does not exist there is also looked
up relative to the working directory, below `/work`, `/work/booklets`, `/data`, `/booklets` and next to the case
file, then by file name inside those folders; the path taken is printed on stderr. URLs (bk.admin.ch) are
downloaded and cached; the cache falls back to the temp directory when its folder is not writable.

With `docker compose` (development, uses `track_2a/.env` and the response cache in `track_2a/.cache`; add `-T`
when it runs without a terminal):

```bash
docker compose build
docker compose run --rm \
  -v /abs/path/booklets:/work/booklets:ro -v /abs/path/cases:/work/cases:ro \
  -e BOOKLET_ROOT=/work \
  booklint predict --case /work/cases/cases.jsonl -o /work/runs/predictions.jsonl
```
`LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY` come from the environment or `track_2a/.env`; the output lands in
`track_2a/runs/`. Single cases from the command line:

```bash
docker compose run --rm booklint predict --booklet <pdf> --claim "…" --vote "…" --id case-0042   # Advanced
docker compose run --rm booklint predict --reference "…" --claim "…" --id case-0043              # Beginner
```

`run` and `bench` also accept files in this nested format, but write extended rows (the slide-25 keys plus
our own fields such as `decision`, `evidence_sentences`, `usage`); only `predict` prints the plain format.

## Other commands

Single claims and own files:

```bash
docker compose run --rm booklint check --booklet <pdf-or-url> --claim "…" [--vote "<proposal title>"]
docker compose run --rm booklint run --input data/v1/test.jsonl --output runs/preds.jsonl
docker compose run --rm booklint bench --input data/v1/test.jsonl --models apertus-v1.5-8b,apertus-v1.5-70b
```

Output per claim (`check --json`, one line per claim in `run`/`bench`/`make run` JSONL):

```json
{
  "decision": 2,
  "answer": "no",
  "page": 19,
  "evidence_sentence": "L'Assemblea federale raccomanda al Popolo e ai Cantoni di respingere l'iniziativa.",
  "evidence_sentences": [
    {"text": "L'Assemblea federale raccomanda al Popolo e ai Cantoni di respingere l'iniziativa.",
     "page": 19, "char_start": 20815, "char_end": 20897, "chunk_id": 86}
  ],
  "entailment_label": 2, "label_name": "contradiction", "confidence": 1.0, "evidence": [ … ], "usage": { … }
}
```

- `decision` = `entailment_label`: 0 entailment (`answer` "yes"), 1 neutral ("blank"), 2 contradiction ("no").
- `page`: 1-based PDF page of the evidence sentence. `evidence_sentence`: the sentence (or two adjacent
  sentences) of the booklet that supports or contradicts the claim, verbatim, including PDF artefacts
  such as split words. `evidence_sentences`: up to five such spans from different passages, best first; `char_start`/`char_end` are
  offsets in the booklet text (all chunk texts joined by `"\n\n"`, the same convention as the chunk offsets
  in `evidence`).
- Neutral: `page` and `evidence_sentence` are `null`, `evidence_sentences` and `evidence` are empty.
- `evidence`: the same spans as `{page, text}` (slide-25 form), or the whole text blocks with
  `--evidence-unit paragraph`.

The sentence is chosen after the decision without any Apertus call: the cited passages, the other top-5
BM25 passages and the 4 best blocks of the section the claim names are split into sentences, and the sentence
that covers most of the (translated) claim wins (idf-weighted word stems plus character 5-grams, so split words
still match; cited passages get a 1.2 bonus, sentences of the named section a factor 2); the next best sentences
of other passages follow, up to five. On the v1.1 test split the first sentence lies in OST's gold section for 86 %
(8B) and 86 % (70B) of the entailment/contradiction answers, and by the rule of OST's `evaluate.py` one of the
five does for 96.9 % / 96.3 % of the gold entailment/contradiction cases (`runs/v1/ost-evidence-test_v11-v5.json`).

Default pipeline (`--mode retrieval`): find the proposal by its title (or, without a title, from the claim;
no LLM), let Apertus translate cross-lingual claims into the booklet language, retrieve 5 passages with BM25
(plus neighbours and the recommendation section for recommendation claims; passages of the section the claim
names, such as "the summary", "the committee" or "the voting text", rank higher: `--section-boost 1.5`), and ask
Apertus for evidence and label under a strict JSON schema. With the 8B model the prompt carries 3 development examples, unsure
claims (p < 0.9) are split into atomic statements, a "neutral" answer is checked once more only for a contradiction
(`--recheck`, only when p(label) < 0.999, `--recheck-below`; one more call for about 2 % of the claims; with 70B the
contradiction is taken only at p ≥ 0.999, `--tau-recheck`), and "Ausschuss" / "commission" in a claim translation is
set back to the booklet's word for the committee (`--committee-terms`). Other modes: `baseline` (whole booklet, the baseline OST
recommends), `easy` (Beginner task: the reference text, in v1.0 `reference_string`), `ladder`, `pages`, `section`, `full`, `oracle`,
`claim-only`. Optional, off by default: `--crossling parallel` (search the other language version),
`--cascade apertus-v1.5-70b`, `--rerank yesno`, `--retriever hybrid` (needs `pip install .[dense]`),
`--calib`, `--numbers hint|rule`. Passage headers: `--render auto` (default: compact for 70B, about −7 % tokens; full for 8B), `full` or `compact`.
Beginner (`easy`): the reference is the context, the claim is not translated; 8B with the same 3 examples.
Measurements: `docs/EXPERIMENTS-v1.md`; how the defaults improved round by round: `docs/ITERATIONS.md`.

Requirements: Docker and an OpenAI-compatible endpoint serving Apertus v1.5 (8B or 70B). In OST's evaluation the
image needs no network besides `BASE_URL`: the booklets are read from `/data`. Network access to bk.admin.ch is only
needed when a case names a booklet by URL (our benchmark files `data/v1/*.jsonl`, `make run`, `make ost` preparation
and the demo); downloaded booklets are cached, not shipped. No GPU and no local
model weights are needed. Without Docker: `pip install -e .[test]`, then `booklint …` and
`python -m pytest`. `python experiments/check_hashes.py` checks the recorded SHA-256 of the data files.

## Data

| File                                           | Content                                                                                                                           | Licence       |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| `data/v1/v1.0.jsonl`                           | OST benchmark `OSTswiss/MNLIoverSwissVotingBooklets` v1.0 (HF commit adca9a5), 1,495 claims; v1.1 (6 Oct.) drops the 7 rows in `data/v1/v1.1-removed.json`, splits with suffix `_v11` in `experiments/v1/run.py` | MIT           |
| `data/v1/{dev,dev_s,test}.jsonl`, `split.json` | split by voting date (seed 2026, `experiments/v1/split.py`): 998 dev, 450 dev subset for ablations, 497 test (493 in v1.1, `test_v11.jsonl`); ids `v1-NNNN` added | MIT (derived) |
| `data/archive/demo-2026-10-01/`                | the earlier 28-row demo and its cross-lingual variants (archived)                                                                 | MIT           |
| `data/edge_cases.jsonl`                        | 24 synthetic stress pairs (ours, written by Gemini 3.8 Flash via Antigravity, not reviewed by a person, not part of the OST benchmark), see `data/README.md` | CDLA-Permissive-2.0 |
| `data/holdout-synth/`                          | 89 synthetic claims on three voting dates of 2018/2019 (not OST), first evaluated after the defaults were fixed (8B once more after the re-check was added) | CDLA-Permissive-2.0 |
| `data/stress-synth/`                           | two synthetic stress sets, 802 claims on 26 voting dates 1998–2018 (not OST; open-model generator and judges), with split and freeze manifests; generation scripts in `experiments/stress/generate/` | CDLA-Permissive-2.0 |

The `data/` directory must not exceed 100 MB.

## 📦 Submission Requirements & Deliverables

❗️ Submissions are not handled on Devpost. Submit through our website only:
http://hackapertus.ch/online-hack/submissions

Requirements differ by challenge. See the description of the challenge you are entering for the exact deliverables.

## ⚖️ Judging Criteria

Judging criteria also differ by challenge. See the respective challenge description.

## Support

**Licensing requirements**
Please check our Terms & Conditions (6. What you build is open source):
https://hackapertus.ch/terms-and-conditions

## FAQ

💡 https://hackapertus.ch/faq

## Contact

💬 In case you have questions, join the conversation on Discord or send an email to “hello@hackapertus.ch”
