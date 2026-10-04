# Hack Apertus — project template

Template repository for [Hack Apertus](https://hackapertus.ch/) submissions.
Every project keeps almost the same layout, so organizers and judges find the
same things in the same place.

## Select your track

This repository holds one example project per track:

- `track_1a/`
- `track_1b/`
- `track_2a/`
- `track_2b/`

Keep the directory for the track you are competing in **exactly as it is** —
don't rename it or move its files — and delete the other track directories.
That directory is your project root. Keep the files and directories as shown
below.

## The structure

| Path | What it is |
| --- | --- |
| `README.md` | The challenge description and submission requirements for your track |
| `technical_report.md` | The deeper write-up: architecture, evaluation, limitations |
| `Makefile` | `make run` must spin up your project |
| `src/` | Your code |
| `data/` | Datasets — `track_1a`, `track_2a` and `track_2b` only; max. 100 MB |
| `findings/` | Issue files — `track_1a` only |
| `docs/` | Diagrams, notes, longer write-ups |

## Run it

Judges run `make run` from the root of the project, on a clean checkout:

```bash
make run
```

`make run` is expected to run the project using Docker, since that
is how the judges will run it.
- If you used other local open-weight models, include instructions for running the project in your technical report.
- Use the following environment variables:
```
LLM_NAME — name and version of the model
LLM_BASE_URL — endpoint base URL
LLM_API_KEY — your API key
```

## Getting started

1. Click **Use this template** to create your own repository.
2. Delete the other track directories. Don't rename or restructure yours.
3. Read its `README.md` and fill in `technical_report.md`.
4. Make `make run` work from the root of the project, on a clean checkout.

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
