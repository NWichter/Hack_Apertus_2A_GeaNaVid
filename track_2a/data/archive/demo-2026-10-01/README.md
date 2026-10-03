# Archived: official demo (2026-10-01)

Archived on 2026-10-02 when OST released the full dataset v1.0 (`data/v1/`).

- `demo.jsonl`: the 28-row demo of `OSTswiss/MNLIoverSwissVotingBooklets` (commit 43f8aa3), ids added. MIT.
- `demo_crossling.jsonl`: the same claims against the other two language versions of the booklet,
  labels carried over, evidence mapped by page layout. MIT (derived).

Why archived: 28 rows from one booklet (2026-06-14) are too few to tune or evaluate on; the demo booklet
was used to tune the first pipeline, so it is kept in the v1.0 dev split and never in test.
All numbers measured on these files (runs `r1`, `r1-8b`, `r5-d01-route`) are in
`runs/archive/demo-synthetic-2026-10-01/` (not tracked) and are superseded by `docs/EXPERIMENTS-v1.md`.
