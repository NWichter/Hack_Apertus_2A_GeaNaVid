# GeaNaVid

Hack Apertus 2026 · Track 2A · OST challenge "Multilingual Natural Language Inference over Swiss Official
Voting Booklets" · Team Apertool.

GeaNaVid checks a claim in German, French or Italian against a Swiss federal voting booklet and returns
0 entailment, 1 neutral or 2 contradiction (Romansh *Gea*, *Vid*, *Na*: yes, blank, no), together with the
booklet sentence and PDF page that decide it, the input/output tokens and the time. Apertus v1.5 (8B or 70B)
makes every decision; the booklet is narrowed to the proposal named by `vote`, cross-lingual claims are
translated by Apertus, and BM25 picks a few passages, preferring the section the claim names (summary,
committee, voting text, Federal Council), so a claim costs about 1.4–2.2 k instead of 20 k input tokens. On the
test split of OST v1.1 (493 pairs) the macro-F1 is 0.959 (8B) and 0.963 (70B), against 0.720 and 0.889 for the
whole booklet. The test split was looked at for 22 configurations; 546 development claims outside the tuning
subset give a second check (0.971 / 0.967). By the rule of OST's evaluation script, one of our five quoted
sentences lies in the gold passage for 97 % (8B) and 96 % (70B) of the entailment and contradiction cases.

The project lives in [`track_2a/`](track_2a/) (template layout). Details: [`track_2a/README.md`](track_2a/README.md).

## Judges start here

Requirements: Docker, an OpenAI-compatible Apertus v1.5 endpoint, no GPU, no local weights.

**As OST runs it** (Solution API Guide, 7 October): the image takes `--input` / `--output`, reads `BASE_URL` and
`API_KEY` at run time, and finds `booklet.path` below `/data`.

```bash
cd track_2a
docker build --platform linux/amd64 -t geanavid .
docker run --rm --platform linux/amd64 -e BASE_URL -e API_KEY \
  -v /abs/path/data:/data:ro -v /abs/path/output:/output \
  geanavid --input /data/cases.jsonl --output /output/predictions.jsonl
```

Input: one JSON object per line, task A `{"id", "vote", "claim": {"text", "language"}, "booklet": {"path",
"language"}}` and task B with `"reference": {"text", "language"}` instead of `booklet`, mixed in one file (flat
variants are read too). Output: one line per case with `id`, `label`, `label_name`, `evidence[{page, text}]`
(up to five quotes, 1-based PDF page; `null` page in task B; `[]` for neutral) and `metrics{input_tokens,
output_tokens, inference_time_ms}`. A failed case is answered neutral with an `error` field; the run never stops
and exits with 0. Checked on 14 October from a fresh clone with 80 OST-format cases and OST's `evaluate.py`
(`track_2a/README.md`, section "OST task format").

**Our benchmark run:**

```bash
cd track_2a
cp .env.example .env      # LLM_NAME, LLM_BASE_URL, LLM_API_KEY
make run                  # Docker: default pipeline on the test split data/v1/test_v11.jsonl (493), table in runs/make-run/
make run LIMIT=30         # quick check
```

`make run` also works from the repository root (the root `Makefile` forwards to `track_2a/`).

**More.**

- Technical report (5 pages, tokens and time included): [`track_2a/Apertool_Report.pdf`](track_2a/Apertool_Report.pdf),
  source [`track_2a/technical_report.md`](track_2a/technical_report.md)
- Experiments and all measurements: [`track_2a/docs/EXPERIMENTS-v1.md`](track_2a/docs/EXPERIMENTS-v1.md)
- How the numbers improved, round by round: [`track_2a/docs/ITERATIONS.md`](track_2a/docs/ITERATIONS.md)
- Data, splits and provenance: [`track_2a/data/README.md`](track_2a/data/README.md)
- Web demo (preview behind a password): https://geanavid.apertool.ch/demo/, code in [`track_2a/demo/`](track_2a/demo/)
- Project page and pitch: https://geanavid.apertool.ch
- Demo video: embedded on the project page (`website/media/video.mp4`, subtitles `website/media/video.vtt`)

GeaNaVid reads the booklet; it never tells anyone how to vote.

## License

Licences follow the Hack Apertus Terms & Conditions (6. What you build is open source): https://hackapertus.ch/terms-and-conditions

| Part | License | File |
| --- | --- | --- |
| Code: `track_2a/` (package `booklint`, `data_prep`, experiments, tests, demo), `website/` | Apache-2.0 | [`LICENSE`](LICENSE) |
| Documentation and technical report: README files, `track_2a/docs/`, `track_2a/technical_report.md`, `track_2a/report/`, `track_2a/Apertool_Report.pdf`, pitch slides | CC-BY-4.0 | [`LICENSE-docs`](LICENSE-docs) |
| Submitted dataset: 24 synthetic edge cases, `track_2a/data/edge_cases.jsonl` | CDLA-Permissive-2.0 | [`track_2a/data/LICENSE-edge_cases`](track_2a/data/LICENSE-edge_cases) |

Third-party material keeps its own licence and is not relicensed:

- OST benchmark `OSTswiss/MNLIoverSwissVotingBooklets` v1.0 (`track_2a/data/v1/`), our splits derived from it and the archived kickoff demo (`track_2a/data/archive/demo-2026-10-01/`): MIT, as published by OST.
- Federal voting booklets (bk.admin.ch): downloaded and cached at run time, not shipped.
- VotingBooklets-v1 (Stüssi & Vamvas, SwissText 2026): CC BY 4.0; one quoted Romansh sentence on a pitch slide, with attribution; the corpus is not shipped.
- `intfloat/multilingual-e5-small` (optional dense retrieval): MIT, downloaded on demand, not shipped.
- Fonts in `website/assets/fonts/`: SIL Open Font License 1.1, see `LICENSE-fonts.txt`.
