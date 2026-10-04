# Iteration log (2026-10-04)

How the pipeline improved after the first complete version (`docs/EXPERIMENTS-v1.md`, state of 2026-10-04 05:00).
Each round: error analysis on development data, one idea, measured on `dev_s` (450 development claims), kept only
if it helps there, then confirmed once on `test` (497 held-out claims). All numbers come from
`runs/v1/<split>/<model>/<run>.summary.json`; `python experiments/v1/run.py --base default ...` reproduces them
from the response cache.

## Protocol

- **Decisions on development data only.** Every choice in this log (section mapping, factors, k, thresholds) was
  made on `dev` / `dev_s`. The section mapping (claim cue → section type) was read off the gold sections of the
  998 `dev` claims (`experiments/v1/errors.py`, `evidence_variants.py`).
- **Test only to confirm.** Test evaluations in this log: **3** (round 1 with 8B and 70B, round 2 with 70B).
  Offline replays of stored runs (0 calls, labels unchanged) are not counted.
- **Defaults** change only if they are better on `dev_s` **and** `test` for macro-F1 (OST: "the priority is really
  NLI performance").
- **Reference point:** the whole-booklet baseline (OST slide 14): test 0.723 (8B) / 0.890 (70B) at 20,156 input
  tokens per claim; `dev_s` 0.655 / 0.853.
- **Budget:** at most 8,000 Apertus calls, at most 4 in parallel. Used: 3,564 for the rounds (last column) and 679
  for the hold-out, 4,243 in total.
- An independent synthetic hold-out (other booklets, not in OST v1.0) is evaluated once at the very end,
  reported separately and never mixed with OST numbers.

## Rounds

Macro-F1; evidence = share of entailment/contradiction answers whose first evidence sentence lies inside the
gold section (and on a gold page); input = prompt tokens per claim (what OST sums).

| # | idea | dev_s 8B | dev_s 70B | dev_s evidence 8B / 70B | dev_s input 8B / 70B | test 8B | test 70B | test evidence 8B / 70B | test input 8B / 70B | kept | calls |
| - | ---- | -------- | --------- | ----------------------- | -------------------- | ------- | -------- | ---------------------- | ------------------- | ---- | ----- |
| 0 | start (state of 05:00) | 0.946 | 0.949 | 0.780 / 0.814 (page 0.801 / 0.838) | 2,216 / 1,611 | 0.941 | 0.951 | 0.786 / 0.804 (page 0.802 / 0.823) | 2,258 / 1,631 | – | 0 |
| 1a | evidence sentence from the section the claim names (offline) | 0.946 | 0.949 | 0.842 / 0.869 | unchanged | – | – | – | – | yes (with 1b) | 0 |
| 1b | + section-aware ranking: passages of that section ×1.5 in the BM25 fusion | **0.958** | **0.964** | 0.842 / 0.875 (page 0.863 / 0.892) | 2,098 / 1,491 | **0.953** | **0.968** | **0.863 / 0.881** (page 0.872 / 0.890) | 2,129 / 1,531 | **yes, default** | 1,328 |
| 2 | compact passage headers (proposal once, section type instead of page note) | 0.951 | 0.973 | 0.852 / 0.868 | 1,965 / 1,375 | – | 0.964 | – / 0.867 | – / 1,418 | no (option `--render compact`): 8B worse on dev, 70B worse on test | 1,194 |
| 3 | k = 6 passages without same-page neighbours | 0.953 | 0.953 | 0.866 / 0.894 | 1,761 / 1,149 | – | – | – | – | no: −0.004 / −0.011 on dev for −16 % / −23 % tokens | 812 |
| 4 | split unsure claims also when p < 0.99 / 0.999 (70B too) | 0.955 / 0.956 | 0.964 / 0.967 | – | +27…+80 | – | – | – | – | no: 8B worse, 70B +1 row | 62 |
| 5 | faster parsing path (proposal index cached, accent folding cached) | = | = | = | = | = | = | = | = | yes | 0 |
| 6 | Beginner CLI default aligned with the measured runs | 0.959 | 0.969 | – | 2,629 / 2,047 | 0.978 | 0.980 | – | 2,662 / 2,080 | yes (fix) | 0 |
| – | cold run as OST measures (50 test cases, no cache) | – | – | – | – | 0.946 | 0.964 | – | 2,116 / 1,564 | – | 168 |

### Round 1 – sections the claim names (kept)

**Error analysis** (`experiments/v1/errors.py`, `dev_s`, round 0): 8B 24 errors (C→N 10, C→E 7, E→C 4), 70B 23
(C→N 12, C→E 6). By cause: wrong judgement with the gold passage retrieved 14 / 12, retrieval miss 6 / 10, judged
on another passage 4 / 1. Cross-lingual claims err 2.5× more often than same-language ones (6.6 % vs 3.1 %, 8B).
Number claims 4.7 %, actor claims 2.6 %, negations 6.7 %. No gold section looks like a table. Most retrieval misses
and many evidence misses concern claims that name a source: "Laut der Zusammenfassung …", "Selon le texte soumis au
vote …", "Il comitato ritiene …".

**Finding.** The gold section of a claim depends on the source it names. On all 998 `dev` claims, the gold section
contains the explanation part (Ausgangslage / Contexte / Contesto) for 99 % of "summary" claims and 95 % of claims
without a source, the committee pages for 93 % of committee claims, and the recommendation or Federal Council
arguments for 98 % of Federal Council claims; voting-text claims point to the legal text in 56 %. The booklet often
says the same thing in several places, so the evidence sentence was often right in content but in another section.

**Change.** `sections.py` labels every text block with a section type from its headings and page notes (legal text,
committee, Federal Council arguments, recommendation, explanation, overview, debate; DE/FR/IT keywords, 0 tokens),
and reads the source a claim names from its wording. Blocks of that section get a factor 1.5 in the reciprocal-rank
fusion (retrieval) and 2.0 in the evidence-sentence score, and the 4 best blocks of that section join the
candidates for the evidence sentence. Factors chosen on `dev_s` (evidence: 1.3 / 1.5 / 2.0 and 0 / 2 / 4 extra
blocks; ranking: 1.5 / 2 / 3 gave the same hit@5 offline, 1.5 is the mildest).

**Effect.** Retrieval hit@5 0.920 → 0.947 (`dev_s`, 8B) and 0.928 → 0.980 (test); the context also got shorter. Test: 8B +0.013, 70B +0.017 macro-F1, evidence +7.6 / +7.7 points, input tokens
−6 %. Same-language 8B 0.980 → 0.993, cross-lingual 0.922 → 0.934.

### Round 2 – compact passage headers (option only)

Every passage repeated the proposal title and, on committee pages, a whole sentence ("Der Text auf dieser
Doppelseite stammt vom Initiativkomitee"): 30 % of the context characters. Compact headers print the proposal once
and the section type ("text of the committee", "voting text (legal text)") instead. `dev_s`: 70B +0.009 at −8 %
tokens, 8B −0.007 (its three examples keep the old header format). Test 70B: 0.964 vs 0.968 at −7 % tokens → not
better on test, so not a default; available as `--render compact`.

### Round 3 – fewer passages (rejected)

Offline, k = 6 without neighbours keeps hit@5 (0.956 vs 0.951) at 29 % fewer context tokens. With Apertus it loses
0.004 (8B) and 0.011 (70B) on `dev_s`: the neighbouring blocks carry context (a "Nein" next to its question, the
sentence before a number). Not run on test.

### Round 4 – re-check unsure answers (rejected)

Apertus is confident: 419 of 450 8B answers have p ≥ 0.999, and 9 of the 19 remaining errors are among them, so a
probability gate cannot find most errors. Splitting the claim into atomic statements when p < 0.99 or < 0.999:
8B 0.955 / 0.956 (worse than 0.958), 70B 0.964 / 0.967 (+0.000 / +0.002, one row). Self-consistency by sampling
was not tried for the same reason (no uncertainty signal on the wrong answers).

### Round 5 – speed (kept)

Profile of the non-LLM part (cache replay of 120 test claims): 135 ms per claim, 60 % of it rebuilding the BM25
index over proposals for every claim. The index is now built once per booklet, and accent folding caches
per character: 48 ms per claim, same 497 labels, evidence sentences and retrieved passages on test for both models.

### Round 6 – Beginner default (fix)

The reported Beginner numbers (8B 0.978 with three examples, 70B 0.980) came from runs without claim translation and
without decomposition, while the CLI default for Beginner translated cross-lingual claims and split unsure 8B
claims; that combination was never measured. On `dev_s`, translation did not change the Beginner score (0.924 with
and without, 8B) and costs one call. The CLI default now matches the measured runs (no translation, no
decomposition for Beginner; `translate_reference` and `--decompose` turn them on). Replay from the cache: 8B 0.978,
70B 0.980 on test, identical to the stored runs, 0 new calls.

## Final defaults and numbers

Advanced: `--mode retrieval --scope vote --translate --k 5 --neighbors 1 --section-boost 1.5`, evidence section
factor 2.0 with 4 extra candidate blocks, prompt `nli-v1`; 8B with three examples and decomposition when p < 0.9.
Beginner: the reference as context, no translation; 8B with three examples.

| test (497) | macro-F1 [95 % CI] | same / cross | evidence in gold (page) | input tokens | cold time mean / p95 |
| ---------- | ------------------ | ------------ | ----------------------- | ------------ | -------------------- |
| Baseline 8B (whole booklet) | 0.723 [0.684–0.760] | 0.801 / 0.685 | – | 20,156 | – |
| Baseline 70B (whole booklet) | 0.890 [0.862–0.917] | 0.916 / 0.876 | – | 20,156 | – |
| Advanced 8B | **0.953** [0.934–0.970] | 0.993 / 0.934 | 0.863 (0.872) | 2,129 | 671 / 871 ms |
| Advanced 70B | **0.968** [0.951–0.982] | 0.987 / 0.958 | 0.881 (0.890) | 1,531 | 1,344 / 2,200 ms |
| Beginner 8B | 0.978 [0.964–0.990] | 0.980 / 0.976 | 0.960 | 2,662 | – |
| Beginner 70B | 0.980 [0.968–0.990] | 0.987 / 0.977 | 0.969 | 2,080 | – |

Cluster bootstrap (copies of a claim resampled together): 8B [0.926–0.975], 70B [0.948–0.984]; without the 122
copied rows 8B 0.952, 70B 0.965 (`runs/v1/test/duplicates-ci.json`). 70B − 8B: +0.015 [−0.010; +0.042].

Cold run (`ost-checks-cold50-r1.json`): 50 seeded test cases in OST's input format, no response cache, one request
at a time; same labels as the stored runs on 50/50 for both models. The 8B mean time is higher than in the first
cold run (457 ms) at the same number of calls: the Apertus share alone is 0.59 s per claim, so the endpoint was
slower; the local part is 48 ms.

## Hold-out (synthetic, evaluated once)

To check that the rounds above did not fit OST's 20 voting dates, a new set was built after the defaults were
fixed: 89 claims on five proposals of three voting dates that OST v1.0 does not contain (2018-06-10, 2019-02-10,
2019-05-19; older booklet layouts), DE/FR/IT booklets, two thirds cross-lingual, 30 / 29 / 30 labels. Claims,
labels, reference sections and evidence were written by Claude; every label was checked blindly by Codex
(GPT-6.1-sol, 90/90 agreement) and NVIDIA Nemotron 3.5 Lightning (89/90); the one disagreement was dropped.
It is synthetic, not human-annotated, and its numbers are never mixed with OST numbers
(`data/holdout-synth/README.md`). Evaluated once, 679 Apertus calls:

| hold-out (89) | 8B | 70B | input tokens 8B / 70B |
| ------------- | -- | --- | --------------------- |
| whole booklet (baseline) | 0.665 [0.561–0.753] | 0.872 [0.800–0.939] | 25,414 / 22,522 |
| Advanced (default) | **0.845** [0.764–0.919] | **0.932** [0.872–0.978] | 2,217 / 1,546 |
| Beginner (reference given) | 0.855 [0.781–0.923] | 0.931 [0.876–0.978] | 1,427 / 845 |

Reading: the gap to the whole-booklet baseline carries over to unseen booklets (+0.18 for 8B, +0.06 for 70B at
9 % / 7 % of the tokens), and the Advanced pipeline is as good as the Beginner task with the reference given, so
retrieval and section routing lose almost nothing there. Absolute scores are lower than on OST test (8B 0.845
vs 0.953); the synthetic claims are harder for 8B, mainly contradictions (F1 0.73), and 89 claims give wide
intervals. Evidence: the first sentence lies in the reference section for 78 % (8B) / 81 % (70B), on a page of the
generator's evidence for 80 % / 84 %.

Apertus calls in this log including the hold-out: 4,243 of 8,000.
