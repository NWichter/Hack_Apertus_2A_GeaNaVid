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
1 neutral = blank, 2 contradiction = no), the page and the sentence of the booklet that decides it, the cited
passages, token usage and time come out.

From `track_2a/`:

```bash
cp .env.example .env          # set LLM_NAME, LLM_BASE_URL, LLM_API_KEY (OpenAI-compatible Apertus endpoint)
make run                      # Docker: default pipeline on the held-out split data/v1/test.jsonl (497 claims)
make run LIMIT=30             # quick check
make run MODES=retrieval,baseline   # plus the whole-booklet baseline (~20 k tokens per claim)
```

`make run` prints a table (macro-F1 with 95 % bootstrap interval, F1 per class, macro-F1 for same- and
cross-language claims, retrieval hit@5, tokens (all and input only) and Apertus calls per claim, Apertus
seconds, `inference_time_ms` mean and p95) and writes it to
`runs/make-run/summary.md`, with one prediction file per model and mode next to it.

## OST task format

**The command for OST is `booklint predict --case <file>`.** It reads the input of slide 24 of the OST session
(2026-10-02) and prints the output of slide 25, nothing else. Both tasks:

- **Advanced:** `{"id", "booklet": {"path"}, "vote", "claim": {"text"}}`: the system finds the evidence in the PDF.
- **Beginner:** `{"id", "reference": {"text"}, "claim": {"text"}}`: the claim is compared with the reference.

`--case` takes one JSON object, a JSON list or a JSONL file (one case per line); `-` reads stdin. One object
gives pretty-printed JSON, otherwise one line per case, written and flushed as soon as the case is done.
`-o FILE` writes to a file instead of stdout. No language field is needed: the claim language is detected,
and a `vote` title in another language than the booklet is translated by Apertus before the proposal is
located.

```json
{"id": "case-0042", "label": 0, "label_name": "entailment",
 "evidence": [{"page": 7, "text": "…verbatim sentence…"}],
 "metrics": {"input_tokens": 1650, "output_tokens": 40, "inference_time_ms": 1820}}
```

- `evidence` is required for entailment and contradiction and may be empty for neutral (we always return
  `[]`). `page` is the 1-based PDF page. `--evidence-unit sentence` (default) returns the deciding sentence(s),
  `--evidence-unit paragraph` the whole text block(s) around them.
- `metrics` holds the input and output tokens reported by the API and the wall time of the case in ms (with a
  warm response cache this is not inference time; use `--no-cache` for timing). OST measures tokens through
  its proxy and time itself (mean and p95).
- A case that fails (missing PDF, no text layer, endpoint error, missing claim) never stops the batch: it is
  answered neutral with empty evidence, zero metrics and an extra field `error`, and a line goes to stderr.

**Docker.** Booklet paths in the cases are file paths inside the container. Mount the booklets and the case
file, and set `BOOKLET_ROOT` when the paths in the cases are relative (`booklets/2024_11_24_de.pdf`): a
relative path is then read below `BOOKLET_ROOT`; without it, relative to the working directory `/work`.
A path that does not exist there is also looked up below `/work`, `/work/booklets`, `/data`, `/booklets` and
next to the case file, then by file name inside those folders; the path taken is printed on stderr
(`booklet '…' not found at '…', using '…'`). URLs (bk.admin.ch) are downloaded and cached in `/work/.cache`.
Add `-T` to `docker compose run` when it runs without a terminal.

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
  such as split words. `evidence_sentences`: up to two such spans, best first; `char_start`/`char_end` are
  offsets in the booklet text (all chunk texts joined by `"\n\n"`, the same convention as the chunk offsets
  in `evidence`).
- Neutral: `page` and `evidence_sentence` are `null`, `evidence_sentences` and `evidence` are empty.
- `evidence`: the same spans as `{page, text}` (slide-25 form), or the whole text blocks with
  `--evidence-unit paragraph`.

The sentence is chosen after the decision without any Apertus call: the cited passages, the other top-5
BM25 passages and the 4 best blocks of the section the claim names are split into sentences, and the sentence
that covers most of the (translated) claim wins (idf-weighted word stems plus character 5-grams, so split words
still match; cited passages get a 1.2 bonus, sentences of the named section a factor 2). On the test split the
chosen sentence lies in OST's gold section for 86 % (8B) and 88 % (70B) of the entailment/contradiction answers,
and on a gold page for 87 % / 89 % (`docs/ITERATIONS.md`).

Default pipeline (`--mode retrieval`): find the proposal by its title (or, without a title, from the claim;
no LLM), let Apertus translate cross-lingual claims into the booklet language, retrieve 5 passages with BM25
(plus neighbours and the recommendation section for recommendation claims; passages of the section the claim
names, such as "the summary", "the committee" or "the voting text", rank higher: `--section-boost 1.5`), and ask
Apertus for evidence and label under a strict JSON schema. With the 8B model the prompt carries 3 development examples, unsure
claims (p < 0.9) are split into atomic statements, a "neutral" answer is checked once more only for a contradiction
(`--recheck`, one more call for about a third of the claims), and "Ausschuss" / "commission" in a claim translation is
set back to the booklet's word for the committee (`--committee-terms`). Other modes: `baseline` (whole booklet, the baseline OST
recommends), `easy` (Beginner task: the reference text, in v1.0 `reference_string`), `ladder`, `pages`, `section`, `full`, `oracle`,
`claim-only`. Optional, off by default: `--crossling parallel` (search the other language version),
`--cascade apertus-v1.5-70b`, `--rerank yesno`, `--retriever hybrid` (needs `pip install .[dense]`),
`--calib`, `--numbers hint|rule`, `--render compact` (shorter passage headers, about −7 % tokens).
Beginner (`easy`): the reference is the context, the claim is not translated; 8B with the same 3 examples.
Measurements: `docs/EXPERIMENTS-v1.md`; how the defaults improved round by round: `docs/ITERATIONS.md`.

Requirements: Docker; network access to bk.admin.ch (booklets are downloaded and cached, not
shipped); an OpenAI-compatible endpoint serving Apertus v1.5 (8B or 70B). No GPU and no local
model weights are needed. Without Docker: `pip install -e .[test]`, then `booklint …` and
`python -m pytest`.

## Data

| File                                           | Content                                                                                                                           | Licence       |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| `data/v1/v1.0.jsonl`                           | OST benchmark `OSTswiss/MNLIoverSwissVotingBooklets` v1.0 (HF commit adca9a5), 1,495 claims                                       | MIT           |
| `data/v1/{dev,dev_s,test}.jsonl`, `split.json` | split by voting date (seed 2026, `experiments/v1/split.py`): 998 dev, 450 dev subset for ablations, 497 test; ids `v1-NNNN` added | MIT (derived) |
| `data/archive/demo-2026-10-01/`                | the earlier 28-row demo and its cross-lingual variants (archived)                                                                 | MIT           |
| `data/edge_cases.jsonl`                        | 24 synthetic stress pairs (ours, written by Gemini 3.8 Flash via Antigravity, not reviewed by a person, not part of the OST benchmark), see `data/README.md` | CDLA-Permissive-2.0 |

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
