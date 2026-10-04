# GeaNaVid

Hack Apertus 2026 · Track 2A · OST challenge "Multilingual Natural Language Inference over Swiss Official
Voting Booklets" · Team Apertool.

GeaNaVid checks a claim in German, French or Italian against a Swiss federal voting booklet and returns
0 entailment, 1 neutral or 2 contradiction (Romansh *Gea*, *Vid*, *Na*: yes, blank, no), together with the
booklet sentence and PDF page that decide it, the input/output tokens and the time. Apertus v1.5 (8B or 70B)
makes every decision; the booklet is narrowed to the proposal named by `vote`, cross-lingual claims are
translated by Apertus, and BM25 picks a few passages, preferring the section the claim names (summary,
committee, voting text, Federal Council), so a claim costs about 1.5–2.1 k instead of 20 k input tokens. On the
held-out test split of OST v1.0 (497 pairs) the macro-F1 is 0.953 (8B) and 0.968 (70B), against 0.723 and 0.890
for the whole booklet; the evidence sentence lies in OST's gold section for 86–88 % of the answers.

The project lives in [`track_2a/`](track_2a/) (template layout). Details: [`track_2a/README.md`](track_2a/README.md).

## Judges start here

Requirements: Docker, an OpenAI-compatible Apertus v1.5 endpoint, no GPU, no local weights.

```bash
cd track_2a
cp .env.example .env      # LLM_NAME, LLM_BASE_URL, LLM_API_KEY
make run                  # Docker: default pipeline on the test split data/v1/test.jsonl, table in runs/make-run/
make run LIMIT=30         # quick check
```

`make run` also works from the repository root (the root `Makefile` forwards to `track_2a/`).

**OST task format.** `booklint predict --case <file>` reads the cases of slide 24 (Advanced:
`{"id", "booklet": {"path"}, "vote", "claim": {"text"}}`; Beginner: `{"id", "reference": {"text"},
"claim": {"text"}}`) as one JSON object, a JSON list or JSONL, and prints exactly the output of slide 25
(`id`, `label`, `label_name`, `evidence[{page, text}]`, `metrics{input_tokens, output_tokens,
inference_time_ms}`), one line per case. A failed case is answered neutral with an `error` field; the batch
never stops.

```bash
cd track_2a
docker compose build
docker compose run --rm -T   -v /abs/path/booklets:/work/booklets:ro -v /abs/path/cases:/work/cases:ro   -e BOOKLET_ROOT=/work   booklint predict --case /work/cases/cases.jsonl -o /work/runs/predictions.jsonl
```

**Mounts and `BOOKLET_ROOT`.** Booklet paths in the cases are paths inside the container. A relative path
(`booklets/2024_11_24_de.pdf`) is read below `BOOKLET_ROOT` when it is set, otherwise relative to the working
directory `/work`. If the file is not there, `booklint` also looks below `/work`, `/work/booklets`, `/data`,
`/booklets` and next to the case file, and finally by file name inside those folders; the path it takes is
printed on stderr. Output lands in `track_2a/runs/` (mounted at `/work/runs`). Use `-T` when the command runs
without a terminal.

**More.**

- Technical report (4 pages, tokens and time included): [`track_2a/Apertool_Report.pdf`](track_2a/Apertool_Report.pdf),
  source [`track_2a/technical_report.md`](track_2a/technical_report.md)
- Experiments and all measurements: [`track_2a/docs/EXPERIMENTS-v1.md`](track_2a/docs/EXPERIMENTS-v1.md)
- How the numbers improved, round by round: [`track_2a/docs/ITERATIONS.md`](track_2a/docs/ITERATIONS.md)
- Data, splits and provenance: [`track_2a/data/README.md`](track_2a/data/README.md)
- Web demo (preview behind a password): https://geanavid.apertool.ch/demo/, code in [`track_2a/demo/`](track_2a/demo/)
- Project page and pitch: https://geanavid.apertool.ch

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
