---
license: mit
---

# OST v1.0 / v1.1 and our split

- `v1.0.jsonl`: downloaded on 2026-10-02 from `OSTswiss/MNLIoverSwissVotingBooklets` (HF commit `adca9a5`), MIT.
  Unchanged: its sha256 `f13c5039…4fb88c` equals the LFS object id of `v1.0.jsonl` at commit
  `adca9a5ee87e9813cef80b305c3b12e3e8a05959`. OST does not document how claims and labels were made.
- `dev.jsonl`, `dev_s.jsonl`, `test.jsonl`, `split.json`: made by `experiments/v1/split.py` (seed 2026),
  split by `booklet_publish_date`; ids `v1-NNNN` = 0-based line index in `v1.0.jsonl`. Rerunning the script
  reproduces the four files byte for byte. Variants were chosen on `dev_s`; `test` was evaluated 25 times (24 configurations) (see `docs/ITERATIONS.md`), so `test` is not untouched.
- Why: v1.0 is the official benchmark of the OST challenge, and OST's hidden test set follows its format.
  Sources and known properties (duplicate rows): `../README.md`.
- `v1.1` (OST, 2026-10-06) is v1.0 without 7 faulty rows (`v1.1-removed.json`: ids, sha256 of OST's file, HF revision).
  `test_v11.jsonl` (493 rows) is `test.jsonl` without the 4 of them in our test split; `make run` uses it.
