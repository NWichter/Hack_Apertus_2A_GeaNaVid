# stress-synth: synthetic stress set on older booklets (1999–2018)

**Synthetic data. Not part of the OST benchmark. No human annotated these rows.** Report numbers on this set
separately and never mix them with OST benchmark numbers.

- **Booklets:** 10 federal voting dates (1999–2018) that OST v1.1 (2020–2026) and `holdout-synth/` (2018-06-10,
  2019) do not cover, DE/FR/IT each, from the Federal Chancellery's collection (URLs in `download.log`, SHA-256 in
  `MANIFEST.json`). The PDFs are git-ignored; download them to `booklets/<date>_<lang>.pdf`.
- **Claims:** written by `nvidia/nemotron-3-ultra-550b-a55b:free` (open weights, OpenRouter) from one booklet page
  each, three label slots per page, about two thirds cross-lingual; evidence quoted verbatim from that page and
  checked against the PDF text.
- **Labels:** kept only where the generator and two blind judges of other model families agree
  (`google/gemma-4-31b-it`, `qwen/qwen3-235b-a22b-2507`; they saw claim, title and the whole proposal, not the label):
  298 rows (`clean.jsonl`, E 103 / N 101 / C 94). 135 disputed rows are in `disputed.jsonl` (120 of them generated as
  neutral). Because the judges dropped more than half of the generated neutral claims, the hard neutral cases are
  under-represented: scores on this set are rather too high than too low.
- **Gold passage** is one PDF page (`reference_page`), not an OST section, so the evidence score is not comparable
  with OST's.
- `cases_A.jsonl` / `cases_B.jsonl`: the same rows in OST's input format (task A booklet, task B reference).
- **Split** (`split.json`, `experiments/stress/split.py`): fixed by voting date before any development on this set,
  stratified and seeded: `dev` 2005, 2008, 2010, 2016, 2018 (157 rows); `holdout` 1999, 2002, 2013, 2014, 2017
  (141 rows). Changes are developed on `dev` and on OST development data only; `holdout` is evaluated once.

Data license: to be decided (prepared for CDLA-Permissive-2.0, not yet declared). The booklets are official
publications of the Swiss Confederation; see `../holdout-synth/README.md` for their terms of use.

**Second set (pre-registered 14 October, before its data exists).** A second synthetic set on 12–16 further voting
dates (about 1995–2019) is being built by the same method with open-weight generator and judges. Its dates will be
split by a seeded draw (seed 20261015, dates sorted, shuffled, first half `dev2`, rest `holdout2`). Neither half is
used to develop anything in the round of 14 October; both are evaluated once with the defaults fixed below.
