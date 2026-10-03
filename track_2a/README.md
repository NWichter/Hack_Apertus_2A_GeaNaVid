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
cross-language claims, retrieval hit@5, tokens and Apertus calls per claim, seconds) and writes it to
`runs/make-run/summary.md`, with one prediction file per model and mode next to it.

OST task format (input as on slide 24 of the OST session, output as on slide 25):

```bash
docker compose run --rm booklint predict --case data/case.json        # one object, a JSON list or JSONL
docker compose run --rm booklint predict --booklet <pdf> --claim "…" --vote "…" --id case-0042
docker compose run --rm booklint predict --reference "…" --claim "…" --id case-0043   # beginner task
```

```json
{"id": "case-0042", "label": 0, "label_name": "entailment",
 "evidence": [{"page": 7, "text": "…verbatim sentence…"}],
 "metrics": {"input_tokens": 1650, "output_tokens": 40, "inference_time_ms": 1820}}
```

`evidence` is required for entailment and contradiction and may be empty for neutral (we always return
`[]`). `metrics` holds the token counts reported by the API and the measured wall time of this call (with
a warm response cache the time is not inference time); OST measures tokens and time itself (mean and p95).
`run` and `bench` also accept files in this nested format.

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
- `evidence` keeps the whole passages (chunks) Apertus cited, with section and proposal.

The sentence is chosen after the decision without any Apertus call: the cited passages and the other top-5
BM25 passages are split into sentences, and the sentence that covers most of the (translated) claim wins
(idf-weighted word stems plus character 5-grams, so split words still match; cited passages get a 1.2 bonus).
On the test split the chosen sentence lies in OST's gold section for 79 % (8B) and 80 % (70B) of the
entailment/contradiction answers (`docs/EXPERIMENTS-v1.md`).

Default pipeline (`--mode retrieval`): find the proposal by its title (or, without a title, from the claim;
no LLM), let Apertus translate cross-lingual claims into the booklet language, retrieve 5 passages with BM25
(plus neighbours and the recommendation section for recommendation claims), and ask Apertus for evidence and
label under a strict JSON schema. With the 8B model the prompt carries 3 development examples and unsure
claims (p < 0.9) are split into atomic statements. Other modes: `baseline` (whole booklet, the comparison OST
uses), `easy` (gold section from `reference_string`), `ladder`, `pages`, `section`, `full`, `oracle`,
`claim-only`. Optional, off by default: `--crossling parallel` (search the other language version),
`--cascade apertus-v1.5-70b`, `--rerank yesno`, `--retriever hybrid` (needs `pip install .[dense]`),
`--calib`, `--numbers hint|rule`. Measurements: `docs/EXPERIMENTS-v1.md`.

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
