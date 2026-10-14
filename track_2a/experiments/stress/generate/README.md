# Stress set generation

These scripts built the two synthetic stress sets in `data/stress-synth/`:

- `set1/` built the first set: `clean.jsonl`, `disputed.jsonl`, `cases_A.jsonl`, `cases_B.jsonl`, `MANIFEST.json`.
- `set2/` built the second set: the same files with the suffix `-b` (`clean-b.jsonl`, ..., `MANIFEST-b.json`).

The scripts write `MANIFEST.json` etc. without a suffix; the `-b` names were given when the second set was copied
to `data/stress-synth/`.

## Steps

Run the scripts from inside `set1/` or `set2/` (they import `common.py` from the same folder).

| Step | set1 | set2 |
| --- | --- | --- |
| 0 | | `python usage.py start` (logs the key usage as the budget baseline) |
| 1 | `python generate.py` | `python generate.py` |
| 2 | `python generate.py neutral` | `python generate.py neutral` |
| 3 | `python build_candidates.py` | `python build_candidates.py` |
| 4 | `python judge.py gemma` | `python judge.py gemma` |
| 5 | `python judge.py qwen` | `python judge.py qwen --all` |
| 6 | `python freeze.py` | `python freeze.py` |

- `generate.py`: writes claims with the generator (`data/generated.jsonl`; with `neutral`, extra neutral items in
  `data/generated_neutral.jsonl`). Resumable.
- `build_candidates.py`: checks that each evidence quote is verbatim in the PDF (`data/candidates.jsonl`).
- `judge.py`: blind labels from two judges (`data/judge_gemma.jsonl`, `data/judge_qwen.jsonl`). Without `--all`, Qwen
  only judges items where Gemma agrees with the generator (set1); in set2 Qwen judged every candidate.
- `freeze.py`: keeps an item as clean only if generator, Gemma and Qwen agree; writes the clean, disputed and OST-format
  files and the manifest with SHA-256 hashes. In set2 it also writes `MANIFEST.sha256`.
- `set2/common.py` has a budget guard: it stops new calls when key usage is 2.80 USD above the `start` entry in
  `data/usage.log`, and it logs the cost of each call to `data/costs.jsonl`.

## Working folder and inputs

- The scripts write into a working folder: `data/stress-synth/work-set1/` or `data/stress-synth/work-set2/`.
  Set the environment variable `STRESS_WORKDIR` to use another folder.
- Download the booklets to `<workdir>/booklets/<date>_<lang>.pdf`. The URLs are in `data/stress-synth/download.log`
  (set1) and `data/stress-synth/download-b.log` (set2).
- `build_candidates.py` reads the URLs from `<workdir>/data/download.log`. For set2, copy `download-b.log` to that name.
- `freeze.py` in set2 also hashes `download_unbenutzt.log`, `generate.log`, `generate_neutral.log` and `costs.jsonl`
  from `<workdir>/data/`; these files must exist.
- OpenRouter key: environment variable `OPENROUTER_API_KEY`, or `OPENROUTER_API_KEY=...` in `track_2a/.env`.

## Models and cost

- Generator: `nvidia/nemotron-3-ultra-550b-a55b:free` (temperature 0.7).
- Judges: `google/gemma-4-31b-it` (the `:free` variant first, then the paid one) and `qwen/qwen3-235b-a22b-2507`
  (temperature 0).
- OpenRouter cost: 0.53 USD (set1), 0.81 USD (set2).

## Reproducibility

Generation is stochastic (temperature 0.7). The seeds fix only the choice of pages, labels, languages and phenomena
(set1: `SEED = 20261014`, set2: `SEED = 202610142`; `SEED + 1` for the neutral step). A rerun gives a similar set,
but not the same one. The published files are the frozen ones: their SHA-256 hashes are in `MANIFEST*.json`, and
`experiments/check_hashes.py` checks them.
