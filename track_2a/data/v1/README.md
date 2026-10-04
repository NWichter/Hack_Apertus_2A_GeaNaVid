---
license: mit
---

# OST v1.0 and our split

- `v1.0.jsonl`: downloaded on 2026-10-02 from `OSTswiss/MNLIoverSwissVotingBooklets` (HF commit `adca9a5`), MIT.
  Unchanged: its sha256 `f13c5039…4fb88c` equals the LFS object id of `v1.0.jsonl` at commit
  `adca9a5ee87e9813cef80b305c3b12e3e8a05959`. OST does not document how claims and labels were made.
- `dev.jsonl`, `dev_s.jsonl`, `test.jsonl`, `split.json`: made by `experiments/v1/split.py` (seed 2026),
  split by `booklet_publish_date`; ids `v1-NNNN` = 0-based line index in `v1.0.jsonl`. Rerunning the script
  reproduces the four files byte for byte. `test` is used only for final numbers.
- Why: v1.0 is the official benchmark of the OST challenge, and OST's hidden test set follows its format.
  Sources and known properties (duplicate rows): `../README.md`.
