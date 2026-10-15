# GeaNaVid

Hack Apertus 2026 · Track 2A · OST challenge "Multilingual Natural Language Inference over Swiss Official
Voting Booklets" · Team Apertool.

GeaNaVid checks a claim in German, French or Italian against a Swiss federal voting booklet and returns
0 entailment, 1 neutral or 2 contradiction (Romansh *Gea*, *Vid*, *Na*: yes, blank, no), together with the
booklet sentence and PDF page that decide it, the input/output tokens and the time. Apertus v1.5 (8B or 70B)
makes every decision; the booklet is narrowed to the proposal named by `vote`, cross-lingual claims are
translated by Apertus, and BM25 picks a few passages, preferring the section the claim names (summary,
committee, voting text, Federal Council), so a claim costs about 1.5–2.2 k instead of 20 k input tokens. On the
test split of OST v1.1 (493 pairs) the macro-F1 is 0.959 (8B) and 0.965 (70B), against 0.720 and 0.889 for the
whole booklet. The test split was evaluated 26 times (24 configurations); 546 development claims outside the tuning
subset give a second check (0.971 / 0.971). By the rule of OST's evaluation script, one of our five quoted
sentences lies in the gold passage for 97 % (8B) and 96 % (70B) of the 324 gold entailment and contradiction cases.
Run as OST runs it (Docker, all 493 test rows as task A and as task B, OST's `evaluate.py`): task A 0.961 / 0.965,
task B 0.977 / 0.976 (8B / 70B; 0.974 in a second 70B run).
Older booklets (1998–2018), which OST v1.1 does not cover, are checked on two synthetic stress sets (26 voting dates,
802 claims by an open model, labels agreed by two other open models, no human;
[`track_2a/data/stress-synth/`](track_2a/data/stress-synth/)): reading the proposal structure of older layouts raised
task A from 0.793 / 0.815 to 0.836 / 0.890 (8B / 70B); OST results are unchanged. Details and the held-out protocol
are in the technical report, §4.

The project lives in [`track_2a/`](track_2a/) (template layout). Details: [`track_2a/README.md`](track_2a/README.md).

Demo video: https://geanavid.apertool.ch/#video · submitted commit: `9a75cb22edf1`

## Judges start here

Requirements: Docker and an OpenAI-compatible Apertus v1.5 endpoint; no GPU, no local weights. Every target runs in
Docker and works from the repository root (the root `Makefile` forwards to `track_2a/`).

```bash
cp track_2a/.env.example track_2a/.env   # LLM_NAME, LLM_BASE_URL, LLM_API_KEY
make test                                 # unit tests, no model calls
make run LIMIT=30                         # benchmark on 30 test claims; make run = all 493; table in track_2a/runs/make-run/
make ost ROWS=20                          # OST's contract: 20 test rows as task A and B through the image, scored like evaluate.py
```

**As OST runs it** (Solution API Guide, 7 October): the image takes `--input` / `--output`, reads `BASE_URL` and
`API_KEY` at run time and finds `booklet.path` below a read-only `/data`.

```bash
cd track_2a
docker build --platform linux/amd64 -t geanavid .
docker run --rm --platform linux/amd64 -e BASE_URL -e API_KEY \
  -v /abs/path/data:/data:ro -v /abs/path/output:/output \
  geanavid --input /data/cases.jsonl --output /output/predictions.jsonl
```

Checked on 14 October from fresh clones: all 986 OST-format cases of the test split (every row as task A and as
task B) with OST's `evaluate.py`, exit code 0, and `make test`, `make run`, `make ost` on Linux.

**Model.** The image runs **Apertus v1.5 70B** (`LLM_NAME=swiss-ai/Apertus-v1.5-70B`, the name format of OST's Solution
API Guide; other spellings are resolved from the endpoint's `/models`, with a `WARNING` on stderr). Why 70B: macro-F1
0.965 on the test split, fewer input tokens (1,461 vs 2,159) and more robust on older booklets. 8B stays available
with `-e LLM_NAME=apertus-v1.5-8b` and is faster: 8B 0.959, 366 / 545 ms (mean / p95); 70B 1,274 / 2,197 ms
(cold runs, see the technical report).

Input: one JSON object per line, task A `{"id", "vote", "claim": {"text", "language"}, "booklet": {"path",
"language"}}` and task B with `"reference": {"text", "language"}` instead of `booklet`, mixed in one file (flat
variants are read too). Output: one line per case with `id`, `label`, `label_name`, `evidence[{page, text}]`
(up to five quotes, 1-based PDF page; `null` page in task B; `[]` for neutral) and `metrics{input_tokens,
output_tokens, inference_time_ms}`. A failed case is answered neutral with an `error` field; the run never stops
and exits with 0. Details: [`track_2a/README.md`](track_2a/README.md), section "OST task format".

**Read next.**

1. Technical report (6 pages, tokens and time included): [`track_2a/Apertool_Report.pdf`](track_2a/Apertool_Report.pdf),
   source [`track_2a/technical_report.md`](track_2a/technical_report.md)
2. How the numbers improved, round by round, with every rejected idea: [`track_2a/docs/ITERATIONS.md`](track_2a/docs/ITERATIONS.md)
3. Data, splits, synthetic sets and provenance: [`track_2a/data/README.md`](track_2a/data/README.md)
4. Early ablations on OST v1.0 (2–4 October, superseded numbers): [`track_2a/docs/EXPERIMENTS-v1.md`](track_2a/docs/EXPERIMENTS-v1.md)
5. Project page with pitch, demo video and web demo: https://geanavid.apertool.ch (demo code in [`track_2a/demo/`](track_2a/demo/))
   The public web demo shares one Apertus key and is capped at 20 requests per minute per visitor and 300 requests
   per hour overall (`/api/info` shows both limits); that is enough for judging, and the CLI has no such cap.

GeaNaVid reads the booklet; it never tells anyone how to vote.

## License

Licences follow the Hack Apertus Terms & Conditions (6. What you build is open source): https://hackapertus.ch/terms-and-conditions

| Part | License | File |
| --- | --- | --- |
| Code: `track_2a/` (package `booklint`, experiments, tests, demo), `website/` | Apache-2.0 | [`LICENSE`](LICENSE) |
| Documentation and technical report: README files, `track_2a/docs/`, `track_2a/technical_report.md`, `track_2a/report/`, `track_2a/Apertool_Report.pdf`, pitch slides | CC-BY-4.0 | [`LICENSE-docs`](LICENSE-docs) |
| Submitted dataset: 24 synthetic edge cases, `track_2a/data/edge_cases.jsonl` | CDLA-Permissive-2.0 | [`track_2a/data/LICENSE-edge_cases`](track_2a/data/LICENSE-edge_cases) |
| Synthetic hold-out `track_2a/data/holdout-synth/` and stress sets `track_2a/data/stress-synth/` (claims, labels, judge outputs; quoted booklet passages are official texts under Art. 5 URG) | CDLA-Permissive-2.0 | [`holdout-synth/LICENSE`](track_2a/data/holdout-synth/LICENSE), [`stress-synth/LICENSE`](track_2a/data/stress-synth/LICENSE) |
| OST benchmark `OSTswiss/MNLIoverSwissVotingBooklets` v1.0/v1.1 and our splits (`track_2a/data/v1/`), archived OST demo (`track_2a/data/archive/demo-2026-10-01/`); not ours, not relicensed | MIT (OST – Ostschweizer Fachhochschule, dataset authors; [dataset card](https://huggingface.co/datasets/OSTswiss/MNLIoverSwissVotingBooklets)) | [`track_2a/data/v1/LICENSE`](track_2a/data/v1/LICENSE) |

Third-party material keeps its own licence and is not relicensed:

- OST benchmark `OSTswiss/MNLIoverSwissVotingBooklets` v1.0 (`track_2a/data/v1/`), our splits derived from it and the archived kickoff demo (`track_2a/data/archive/demo-2026-10-01/`): MIT, as published by OST (licence text in `track_2a/data/v1/LICENSE`).
- Federal voting booklets (bk.admin.ch): not shipped; our benchmark scripts and the web demo download and cache them, OST's evaluation reads them from `/data`.
- VotingBooklets-v1 (Stüssi & Vamvas, SwissText 2026): CC BY 4.0; one quoted Romansh sentence on a pitch slide, with attribution; the corpus is not shipped.
- `intfloat/multilingual-e5-small` (optional dense retrieval): MIT, downloaded on demand, not shipped.
- Fonts in `website/assets/fonts/`: SIL Open Font License 1.1, see `LICENSE-fonts.txt`.
