# Data

```
data/
├── v1/                      # OST v1.0 benchmark and our split (all reported numbers)
│   ├── v1.0.jsonl           # 1,495 pairs, OSTswiss/MNLIoverSwissVotingBooklets, HF commit adca9a5, MIT
│   ├── dev.jsonl            # 998 pairs: prompts, few-shot examples, thresholds
│   ├── dev_s.jsonl          # 450-pair subset of dev for ablations
│   ├── test.jsonl           # 497 pairs (test_v11.jsonl: 493, OST v1.1); evaluated 25 times (24 configurations)
│   └── split.json           # split definition (seed 2026)
├── holdout-synth/           # 89 synthetic hold-out pairs from 2018/2019 booklets, NOT OST, evaluated after the defaults were fixed (README there)
├── edge_cases.jsonl         # 24 synthetic stress pairs, NOT part of the OST benchmark, CDLA-Permissive-2.0
├── LICENSE-edge_cases       # CDLA-Permissive-2.0 text for edge_cases.jsonl
├── manifest.json            # sha256, sizes, label and language counts
└── archive/demo-2026-10-01/ # the 28-row kickoff demo, superseded by v1.0
```

## OST v1.0 (`v1/`)

Claims in German, French and Italian against the official federal voting booklets (20 voting dates
2020–2026, each in de/fr/it). Fields: `claim`, `claim_language`, `reference_string`, `reference_language`,
`entailment_label` (0 entailment, 1 neutral, 2 contradiction), `booklet_url`, `booklet_publish_date`,
`vote`, `baseline_score`; `id` = `v1-NNNN` (0-based line index in `v1.0.jsonl`, added by `split.py`; v1.0 itself has no id).

Languages: German, French and Italian only (claims and booklets).

The split (`experiments/v1/split.py`) is by booklet, not chronological: the unit is the voting date, so the
de/fr/it versions of a booklet always stay on one side. The kickoff demo booklet (2026-06-14) is forced into
dev because it was used to build the first pipeline. From the other 19 dates the script draws 7 test dates,
5,000 times with seed 2026, and keeps the draw whose test part is closest to one third of the rows and to the
overall distribution of labels, claim language, booklet language and same/cross-language pairs. Result:
7 test dates (497 rows), 13 dev dates (998 rows); `split.json` lists them. `dev_s` is a 450-row sample of
dev, proportional per label × same/cross-language cell.

## Synthetic edge cases (`edge_cases.jsonl`)

24 stress pairs written by an LLM agent: an Antigravity CLI subagent running Gemini 3.8 Flash
(`gemini-3.8-flash`, a closed model) wrote them as a Python literal in `data/generate_edge_cases.py` on
2026-10-03 (04:55 UTC); the script was deleted on 2026-10-04. Topics: Romansh claims, modal/negation traps,
attribution (committee vs. Federal Council), numbers, cross-lingual pairs. Each row carries a `provenance`
object (`synthetic: true`, `reviewed: false`, `generator`, `generator_model`, `generated_at`, `prompt_version`,
`generation_trace`, `post_edits`). There was no versioned prompt, only a free-form agent task. Seven further
pairs appended later with invented references and placeholder metrics were removed on 2026-10-04, as were the
invented `metrics` values of the 24 pairs.

- The references are paraphrases written by the generator, **not verbatim booklet text**; `evidence.page`
  is a placeholder (1).
- Labels are **not reviewed** by a person. A spot check (by Claude, 2026-10-04) relabelled `edge-rm-03`
  (a 50-franc fee against "free of charge" is a contradiction, not neutral) and noted two doubtful rows and
  one wrong category in `provenance.review_note` (`edge-modal-02`, `edge-rm-02`, `edge-xling-05`).
- Romansh text was not checked by a native speaker.
- **Overlap with the test split.** 16 of the 24 rows are about proposals of test-split voting dates (rent law /
  personal need, imputed rental value, biodiversity: `edge-modal-02`–`05`, `edge-attrib-03`, `-04`,
  `edge-num-01`–`04`, `edge-xling-01`–`06`), and 11 of the 20 evidence texts share passages of 40 or more
  characters with OST test references (6 start with a verbatim copy). They were written after the test runs
  (2026-10-02) and were never used to choose prompts, examples or thresholds.
- Use them for demos and qualitative stress tests only; they are never evaluated and no reported number uses
  them. `tests/test_edge_cases.py` checks that no stored run under `runs/v1/` contains an edge-case id or claim,
  that every stored test/dev_s run holds only ids of its split, and that no run config refers to them.
- Evidence for model and date: the Antigravity conversation log of that subagent (every generation step names
  `gemini-3.8-flash`) and its transcript with the original rows; `post_edits` lists every later change per row.

## Sources and provenance

| Dataset | Source, version | Made by | Per-row provenance fields | Why we use it | Shipped? |
| --- | --- | --- | --- | --- | --- |
| `v1/v1.0.jsonl` | [`OSTswiss/MNLIoverSwissVotingBooklets`](https://huggingface.co/datasets/OSTswiss/MNLIoverSwissVotingBooklets) `v1.0.jsonl`, commit `adca9a5ee87e9813cef80b305c3b12e3e8a05959` (2026-10-02), downloaded 2026-10-02; sha256 equals the HF LFS object id | OST (challenge owner); how claims and labels were made is not documented by OST | `booklet_url`, `booklet_publish_date`, `booklet_download_date`; no creator, label source or review fields | the official benchmark of the challenge; the hidden test set follows its format | yes, unchanged copy |
| `v1/{dev,dev_s,test}.jsonl`, `split.json` | derived from `v1.0.jsonl` by `experiments/v1/split.py` (seed 2026); rerunning the script reproduces all four files byte for byte | us (script) | as v1.0, plus `id` | tuning on dev, final numbers on test | yes |
| `edge_cases.jsonl` | this repository | Gemini 3.8 Flash via Antigravity CLI (2026-10-03), edited 2026-10-04 | `provenance.*` on all 24 rows | demo presets and qualitative stress tests (Romansh, traps) | yes |
| `archive/demo-2026-10-01/demo.jsonl` | OST demo `demo_2026_09_28_1130.jsonl`, commit `43f8aa356dc16f5d1c434781749d1118f9503f04` (2026-09-28); rows identical to the HF file apart from the added `id` | OST | `booklet_url`, dates | first prototype before v1.0 existed | yes (archived) |
| `archive/demo-2026-10-01/demo_crossling.jsonl` | derived from the demo by `src/data_prep/crosslingual.py` (no LLM) | us (script) | `author: ost_demo`, `generator_model` | first cross-lingual tests | yes (archived) |
| `archive/synthetic-2026-10-01/` | `synthetic-v0` built by `src/data_prep/` | Claude Opus 5.5 and GPT-5.5 (Codex CLI), 2026-10-01, prompt `gen-v1`; cross-lingual copies by script | `author`, `generator_model` (full provenance only in the local `merged.v0.jsonl`) | development before v1.0; superseded | no (gitignored, local only) |

No reported number uses the edge cases or the archived sets. The OST dataset card gives no citation; cite it
as: OST Ostschweizer Fachhochschule, *MNLIoverSwissVotingBooklets* v1.0, Hugging Face, commit `adca9a5`, 2026.

**Known properties of OST v1.0.** 335 rows are exact copies of another row (236 groups of identical
claim, booklet and label; no conflicting labels): 122 of the 497 test rows and 53 of the 450 dev_s rows.
We keep the rows as published. A plain bootstrap then treats copies as independent and its intervals are too
narrow; `experiments/v1/duplicates_ci.py` recomputes them from the stored predictions (no Apertus calls,
`runs/v1/test/duplicates-ci.json`): on v1.0 (497 rows, 375 distinct pairs) the defaults of 2026-10-04 scored
0.952 / 0.965 without copies. The current defaults (14 October, OST v1.1, 493 rows, 371 distinct pairs) score 0.957 (8B)
and 0.962 (70B) without copies, with cluster intervals [0.933–0.980] and [0.944–0.983]
(`runs/v1/test_v11/final-v5-ci.json`). 4 claim texts occur in
both dev and test (against different booklets).

## Licences

- `edge_cases.jsonl` is our submitted dataset: CDLA-Permissive-2.0, see [`LICENSE-edge_cases`](LICENSE-edge_cases).
- `v1/` and `archive/demo-2026-10-01/` are OST data and splits derived from it: MIT, as published by OST.
  They are not relicensed.
