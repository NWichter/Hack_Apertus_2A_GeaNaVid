# Data

```
data/
├── v1/                      # OST v1.0 benchmark and our split (all reported numbers)
│   ├── v1.0.jsonl           # 1,495 pairs, OSTswiss/MNLIoverSwissVotingBooklets, HF commit adca9a5, MIT
│   ├── dev.jsonl            # 998 pairs: prompts, few-shot examples, thresholds
│   ├── dev_s.jsonl          # 450-pair subset of dev for ablations
│   ├── test.jsonl           # 497 pairs, used only for final numbers
│   └── split.json           # split definition (seed 2026)
├── edge_cases.jsonl         # 24 synthetic stress pairs, NOT part of the OST benchmark
├── manifest.json            # sha256, sizes, label and language counts
└── archive/demo-2026-10-01/ # the 28-row kickoff demo, superseded by v1.0
```

## OST v1.0 (`v1/`)

Claims in German, French and Italian against the official federal voting booklets (20 voting dates
2020–2026, each in de/fr/it). Fields: `claim`, `claim_language`, `reference_string`, `reference_language`,
`entailment_label` (0 entailment, 1 neutral, 2 contradiction), `booklet_url`, `booklet_publish_date`,
`vote`, `baseline_score`; `id` = `v1-NNNN` (line number in `v1.0.jsonl`).

Languages: German, French and Italian only (claims and booklets).

The split (`experiments/v1/split.py`) is by booklet, not chronological: the unit is the voting date, so the
de/fr/it versions of a booklet always stay on one side. The kickoff demo booklet (2026-06-14) is forced into
dev because it was used to build the first pipeline. From the other 19 dates the script draws 7 test dates,
5,000 times with seed 2026, and keeps the draw whose test part is closest to one third of the rows and to the
overall distribution of labels, claim language, booklet language and same/cross-language pairs. Result:
7 test dates (497 rows), 13 dev dates (998 rows); `split.json` lists them. `dev_s` is a 450-row sample of
dev, proportional per label × same/cross-language cell.

## Synthetic edge cases (`edge_cases.jsonl`)

24 stress pairs written by an LLM agent (Antigravity, 2026-10-02): Romansh claims, modal/negation traps,
attribution (committee vs. Federal Council), numbers, cross-lingual pairs. Each row carries a `provenance`
object (`synthetic: true`, `reviewed: false`, generator, date). Seven further pairs appended later with
invented references and placeholder metrics were removed on 2026-10-04.

- The references are paraphrases written by the generator, **not verbatim booklet text**; `evidence.page`
  is a placeholder (1).
- Labels are **not reviewed** by a person. A spot check (by Claude, 2026-10-04) relabelled `edge-rm-03`
  (a 50-franc fee against "free of charge" is a contradiction, not neutral) and noted two doubtful rows and
  one wrong category in `provenance.review_note` (`edge-modal-02`, `edge-rm-02`, `edge-xling-05`).
- Romansh text was not checked by a native speaker.
- Use them for demos and qualitative stress tests only; never mix their results with OST v1.0 numbers.
