---
license: mit
---

# OST v1.0 and our split

- `v1.0.jsonl`: downloaded on 2026-10-02 from `OSTswiss/MNLIoverSwissVotingBooklets` (HF commit `adca9a5`), MIT.
- `dev.jsonl`, `dev_s.jsonl`, `test.jsonl`, `split.json`: made by `experiments/v1/split.py` (seed 2026),
  split by `booklet_publish_date`; ids `v1-NNNN` = line number in `v1.0.jsonl`. `test` is used only for final numbers.
