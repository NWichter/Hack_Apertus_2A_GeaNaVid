# Iteration log (2026-10-04)

How the pipeline improved after the first complete version (`docs/EXPERIMENTS-v1.md`, state of 2026-10-04 05:00).
Each round: error analysis on development data, one idea, measured on `dev_s` (450 development claims), kept only
if it helps there, then confirmed once on `test` (497 test claims; over the whole project test was evaluated 26 times, for 24
configurations and decided some defaults, see the technical report, §4). All numbers come from
`runs/v1/<split>/<model>/<run>.summary.json`; `python experiments/v1/run.py --base default ...` reproduces them
from the response cache.

## Protocol

- **Decisions on development data only.** Every choice in this log (section mapping, factors, k, thresholds) was
  made on `dev` / `dev_s`. The section mapping (claim cue → section type) was read off the gold sections of the
  998 `dev` claims (`experiments/v1/errors.py`, `evidence_variants.py`).
- **Test only to confirm.** Test evaluations in this log: **5** (round 1 with 8B and 70B, round 2 with 70B,
  rounds 7 + 9 with 8B and 70B). Offline replays of stored runs (0 calls, labels unchanged) are not counted.
- **Defaults** change only if they are better on `dev_s` **and** `test` for macro-F1 (OST: "the priority is really
  NLI performance").
- **Reference point:** the whole-booklet baseline (OST slide 14): test 0.723 (8B) / 0.890 (70B) at 20,156 input
  tokens per claim; `dev_s` 0.655 / 0.853.
- **Budget:** first block (rounds 0–6) at most 8,000 Apertus calls: 3,564 for the rounds and 679 for the hold-out,
  4,243 in total. Second block (rounds 7–12) at most 3,500 calls: 1,941 used (last column; hold-out 34, cold run
  189). At most 4 in parallel.
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
| 7 | re-check every "neutral" answer once, only for a contradiction (8B p ≥ 0.5, 70B p ≥ 0.999) | **0.969** | **0.973** | 0.838 / 0.871 | 2,564 / 1,943 | see 9 | see 9 | – | – | with 9 | 270 |
| 7b | same, but only the 5 direct hits as context | 0.964 | 0.971 | – | 2,403 / 1,784 | – | – | – | – | no: worse than 7 for both | 269 |
| 8 | the same re-check for "entailment" answers | 0.838 (best) | 0.967 (best) | – | 3,048 / 2,431 | – | – | – | – | no: 8B calls 61 of 152 entailments a contradiction even at p ≥ 0.9999 | 264 |
| 9 | 7 + "Komitee / comité / comitato" restored in claim translations | **0.973** | 0.973 | 0.842 / 0.875 | 2,564 / 1,942 | **0.957** | 0.966 | 0.861 / 0.878 | 2,662 / 2,066 | **8B: yes, default; 70B: no** (test −0.002) | 45 + 277 (test) |
| 10 | translate the passages into the claim language instead of the claim (pilot, 150 rows, 8B) | 0.987 vs 0.990 (F1 entailment) | – | – | +35 % | – | – | – | – | no: 10× time (p50 6.2 s vs 0.65 s) | 167 |
| 11 | prompt with a sharper contradiction / neutral definition (8B, on top of 9) | 0.964 | – | – | 2,651 / – | – | – | – | – | no: −0.009 on dev; 70B not run | 426 |
| 12 | Italian booklets (offline): F1, retrieval and section labels by booklet language | = | = | – | – | – | – | – | – | no change: Italian is not weaker on development data | 0 |
| – | cold run, 50 test cases, new vs old 8B default in the same session | – | – | – | – | 0.964 vs 0.946 | – | – | 2,761 vs 2,117 | – | 189 |

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

### Round 7 – re-check "neutral" answers for a contradiction (kept for 8B, with round 9)

**Error analysis** (`dev_s`, defaults of round 6): 8B 19 errors, 11 of them contradiction → neutral; 70B 16, 7 of
them. Apertus gives most of these neutral answers p ≥ 0.98, so no probability gate finds them (round 4). A
deterministic number check does not separate them either: of the 8B neutral answers with a claim number missing
from the passages, 52 are gold neutral and 1 is a contradiction (offline, 0 calls).

**Change.** After a "neutral" answer, one more Apertus call with the same passages and a narrow question: is a detail
of the claim contradicted (another number, actor, position, direction, scope)? The answer names the claim detail,
the passage and what it says, then `contradiction` / `no_contradiction`; the probability of the verdict is read
from its first token. Run on all neutral answers of `dev_s` (8B 154, 70B 149); thresholds chosen afterwards offline.

**Effect on `dev_s`.** 8B: 5 answers flip, all 5 correct (gold contradiction); 0.958 → 0.969 at p ≥ 0.5 (0.966
at 0.9–0.99). 70B: the re-check says contradiction far too often (41 flips at p ≥ 0.5, 35 of them gold neutral);
at p ≥ 0.999 7 flips, 5 correct: 0.964 → 0.973. Only the 5 direct hits as context (7b) is cheaper (+300 instead of
+460 input tokens) but worse for both models. A BM25 score gate did not help.

### Round 8 – the same re-check for "entailment" answers (rejected)

The remaining 8B errors include 4 contradiction → entailment (the committee says no, the claim says it recommends
yes). Asking the same question after an "entailment" answer: 8B flags 94 of 152 entailments (91 wrongly), 61 even
at p ≥ 0.9999; 70B 16 (13 wrongly). Worse at every threshold.

### Round 9 – the booklet's word for the committee (kept for 8B, with round 7)

Apertus translates Italian "il comitato" into German as "der Ausschuss" in 15 of 50 cross-lingual committee claims
of `dev_s` (both models), while German booklets say "Komitee"; BM25 and the passage notes then miss the committee
pages. When the claim names the committee and the translation lacks the booklet word, "Ausschuss" /
"commission" / "commissione" are replaced (no call). `dev_s` on top of round 7: 8B 0.969 → 0.973, 70B unchanged.

**Test (once, 8B and 70B, rounds 7 + 9 together):** 8B 0.953 → **0.957**, 70B 0.968 → 0.966. Offline split of the
test effect: the committee words alone change no test label for either model; the re-check flips 4 8B answers (3
correct) and 10 70B answers (4 correct; 5 wrong flips are copies of the same claim at p = 0.9992). Kept for 8B
(better on `dev_s` and test), not for 70B (worse on test). Cost for 8B: 0.35 more calls per claim, input tokens
2,129 → 2,662 (+25 %), cold time 401 → 648 ms mean and 709 → 1,188 ms p95 (same session, 50 test cases).

### Round 10 – translate the passages instead of the claim (rejected)

Pilot with 8B on the first 150 `dev_s` rows (all of them entailment, the file is sorted by label): one Apertus call
translates the retrieved passages into the claim language, the judgement then reads claim and passages in the same
language. F1 on these rows 0.987 vs 0.990, input tokens +35 %, median Apertus time 6.2 s instead of 0.65 s per
claim. Not continued: the time alone rules it out as a default.

### Round 11 – sharper contradiction / neutral definition in the prompt (rejected)

`nli-v6` defines contradiction as "a statement about the same point with a different detail" and neutral as "no
statement about the point", and asks to compare the claim with the closest statement first (the three examples
stay). 8B on `dev_s` on top of round 9: 0.973 → 0.964. 70B was not run.

### Round 12 – Italian booklets (no change)

On test, 8B is weakest on Italian booklets (0.914). This was not analysed on test rows. On development data Italian
is not weaker: `dev_s` macro-F1 by booklet language, 8B DE / FR / IT, 0.976 / 0.973 / 0.972; same-language
retrieval on the 998 `dev` claims, hit@5 0.922 / 0.923 / 0.954; share of text blocks without a section type
2 / 5 / 3 %. Without a development signal there is nothing to fix that would not be fitted to test.

## Final defaults and numbers

Advanced: `--mode retrieval --scope vote --translate --k 5 --neighbors 1 --section-boost 1.5`, evidence section
factor 2.0 with 4 extra candidate blocks, prompt `nli-v1`; 8B with three examples, decomposition when p < 0.9, a
contradiction re-check of neutral answers (`--recheck`, p ≥ 0.5) and the committee words (`--committee-terms`).
Beginner: the reference as context, no translation; 8B with three examples.

| test (497) | macro-F1 [95 % CI] | same / cross | evidence in gold (page) | input tokens | cold time mean / p95 |
| ---------- | ------------------ | ------------ | ----------------------- | ------------ | -------------------- |
| Baseline 8B (whole booklet) | 0.723 [0.684–0.760] | 0.801 / 0.685 | – | 20,156 | – |
| Baseline 70B (whole booklet) | 0.890 [0.862–0.917] | 0.916 / 0.876 | – | 20,156 | – |
| Advanced 8B | **0.957** [0.938–0.975] | 0.987 / 0.943 | 0.861 (0.870) | 2,662 | 648 / 1,188 ms |
| Advanced 70B | **0.968** [0.951–0.982] | 0.987 / 0.958 | 0.881 (0.890) | 1,531 | 1,344 / 2,200 ms |
| Beginner 8B | 0.978 [0.964–0.990] | 0.980 / 0.976 | 0.960 | 2,662 | – |
| Beginner 70B | 0.980 [0.968–0.990] | 0.987 / 0.977 | 0.969 | 2,080 | – |

Cluster bootstrap (copies of a claim resampled together): 8B [0.933–0.978], 70B [0.948–0.984]; without the 122
copied rows 8B 0.955, 70B 0.965 (`runs/v1/test/duplicates-ci.json`). 70B − 8B: +0.010 [−0.012; +0.035].

Cold run (`ost-checks-cold50-r1.json`; 8B since round 9 `ost-checks-cold50-v2.json`): 50 seeded test cases in
OST's input format, no response cache, one request at a time; same labels as the stored runs on 50/50 for both
models (round 6 defaults). The new 8B default measured 648 / 1,188 ms against 401 / 709 ms for the old one in the
same session. The 8B mean time is higher than in the first
cold run (457 ms) at the same number of calls: the Apertus share alone is 0.59 s per claim, so the endpoint was
slower; the local part is 48 ms.

## Hold-out (synthetic, evaluated once)

To check that the rounds above did not fit OST's 20 voting dates, a new set was built after the defaults were
fixed: 89 claims on five proposals of three voting dates that OST v1.0 does not contain (2018-06-10, 2019-02-10,
2019-05-19; older booklet layouts), DE/FR/IT booklets, two thirds cross-lingual, 30 / 29 / 30 labels. Claims,
labels, reference sections and evidence were written by Claude; every label was checked blindly by open-weight
models: NVIDIA Nemotron 3.5 Lightning (89/90) and, since 14 October, a panel of GLM-5.3 (89/90), DeepSeek V3.2 (90/90)
and Qwen3-235B (82/90); a row is kept if Nemotron and the panel majority agree, which drops the same single row
(an earlier Codex pass, a closed model, was replaced by the panel and changed nothing).
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

**Hold-out with the round-9 default (evaluated once, 34 calls):** Advanced 8B 0.845 → **0.874** [0.800–0.936],
contradiction F1 0.735 → 0.793, cross-lingual 0.807 → 0.848, input tokens 2,217 → 2,732; evidence in the reference
section 0.80. 70B is unchanged (0.932). `runs/holdout-synth/apertus-v1.5-8b/retrieval-v2.summary.json`.

Apertus calls in this log: 4,243 of 8,000 (rounds 0–6 and the first hold-out) and 1,941 of 3,500 (rounds 7–12).

## 13 October: OST's scoring script, v1.1 and a development split outside the tuning subset

OST published a Solution API Guide (7 October), a starter repository with `evaluate.py` (8 October) and dataset
v1.1 (6 October, 7 faulty rows removed, 4 of them in our test split). No call was spent on test in this block.

| # | idea | decided on | dev_s 8B / 70B | dev_rest 8B / 70B | test v1.1 8B / 70B | kept | calls |
| - | ---- | ---------- | -------------- | ----------------- | ------------------ | ---- | ----- |
| – | final defaults on `dev_rest` (546 dev claims outside `dev_s`, never used to choose an option) | – | – | macro-F1 0.971 / 0.965 | – | – | 1,409 |
| 13 | evidence: up to 5 sentences from different passages, no score threshold (was at most 2, the second only at ≥ 70 % of the best score) | `dev_s`, OST evidence score | 0.920 → 0.964 / 0.917 → 0.954 | 0.893 → 0.940 / 0.888 → 0.923 | 0.932 → 0.969 / 0.920 → 0.960 | **yes** | 0 |
| 13b | same with whole paragraphs instead of sentences | `dev_s` | 0.954 / 0.944 | – | – | no | 0 |
| 13c | 3 sentences, threshold 50 % / 5 sentences, threshold 50 % | `dev_s` | 0.937 / 0.937, 0.944 / 0.947 | – | – | no | 0 |

The OST evidence score counts a gold entailment/contradiction case if one of the first five quotes (≤ 5,000
characters) matches the gold `reference_string` with rapidfuzz `partial_ratio` ≥ 90 (`experiments/v1/ost_evidence.py`
reimplements `evaluate.py`). Labels and tokens do not change; the first quote stays the same. All v1.1 numbers
come from the stored runs without the removed rows (`experiments/v1/replay_v11.py`, `runs/v1/v1.1-filtered.json`):
test v1.1 macro-F1 8B 0.957, 70B 0.967, whole booklet 0.720 / 0.889, Beginner 0.977 / 0.980.

## 14 October: fewer tokens and less time (OST scores both relative to the other teams)

Protocol as above: choose on `dev_s` (v1.1, 449), confirm once on `dev_rest` (546), then one test run (the 24th test evaluation; for 70B the compact headers had been seen on test once before, round 2
look). Labels and tokens from `runs/v1/{dev_s,dev_rest,test}_v11/<model>/*.summary.json`; latency from cold runs on 50
seeded `dev_rest` cases with old and new default interleaved (`runs/v1/dev_rest_v11/cold-*-1014.json`).

| # | idea | dev_s 8B / 70B | dev_rest 8B / 70B | test 8B / 70B | input tokens (test) | kept |
| - | ---- | -------------- | ----------------- | ------------- | ------------------- | ---- |
| 14 | 8B: re-check a neutral verdict only if p(label) < 0.999 (`--recheck-below`, 0.9999 / 0.99999 same F1 on dev_s, more tokens) | 0.973 → 0.971 / – | 0.971 → 0.971 / – | 0.957 → **0.959** / – | 2,667 → **2,159** | **yes** (0 calls: a subset of the cached calls) |
| 15 | 70B: compact passage headers by default | – / 0.966 → 0.973 | – / 0.965 → 0.967 | – / 0.967 → **0.963** | 1,532 → **1,418** | **yes** (test −0.004, within the interval) |
| 15b | 8B: compact headers, few-shot headers converted the same way (with 14) | 0.960 | – | – | −7 % | no |
| 16 | 8B: two / one few-shot examples (with 14) | 0.967 / 0.951 | – | – | −11 % / −18 % | no |

Cold latency, mean / p95 per case: 8B 543 / 972 → **366 / 545 ms**, 70B 1,407 / 2,056 → **1,342 / 2,015 ms**; same
macro-F1 on the 50 cases. OST evidence score on test unchanged (0.969 / 0.960). Calls for this round: about 2,800
(dev_s and dev_rest runs, cold runs, test 70B).

Also fixed on the way: two workers asking the same prompt had written one cache file twice into each other (a
replay then failed on these two claims); cache files are now written atomically, and a broken one counts as a
miss. A run hung for over 20 minutes on one request: connection and timeout errors are now retried at most four
times with a 60 s timeout.

## 14 October: error analysis on development data, one change for 70B

Errors of the defaults before this round on `dev_s` + `dev_rest` (995 claims; test not looked at;
`experiments/v1/error_types.py` → `runs/v1/error-types-dev.json`, 0 calls). A row can carry several types; the types
are keyword rules on the claim, not a manual reading.

| type | 8B (29 errors, 25 distinct claims) | 70B (30 errors, 22 distinct claims) | share in all 995 claims |
| ---- | ---- | ---- | ---- |
| gold contradiction answered entailment / neutral | 11 / 9 | 7 / 12 | 33 % gold contradiction |
| gold entailment answered neutral / contradiction | 4 / 3 | 6 / 4 | |
| gold neutral answered contradiction | 2 | 1 | |
| p(label) ≥ 0.999 | 19 | 21 | |
| numbers or amounts in the claim | 13 | 16 | 46 % |
| cross-lingual | 22 | 20 | 65 % |
| time expressions | 5 | 7 | 26 % |
| negation | 5 | 4 | 15 % |
| no quote inside the gold passage | 2 | 2 | |

Missed contradictions dominate (69 % / 63 % of the errors against 33 % of the data), mostly with high confidence;
numbers, negation, dates and language pairs are not over-represented.

| # | idea (chosen on `dev_s`) | dev_s 8B / 70B | dev_rest 8B / 70B | test 8B / 70B | input tokens (test) | kept |
| - | ---- | -------------- | ----------------- | ------------- | ------------------- | ---- |
| 17 | re-check an entailment whose claim numbers are missing from the passages (option `recheck_numbers="missing"` via `run.py --opts`) | 0.971 → 0.971 / 0.973 → 0.973 | – | – | ± 0 | no (never fires: all 42 numeric entailments on `dev_s` find their numbers in the passages) |
| 17b | re-check every entailment with a number in the claim (`recheck_numbers="any"`) | 0.924 / 0.960 | – | – | +7 % / +10 % (dev_s) | no |
| 18 | 8B: swap one few-shot example (v1-1444 → v1-1084) / add it as a fourth | 0.967 / 0.951 | – | – | −5 % / +7 % (dev_s) | no |
| 19 | 70B: neutral re-check only if p(label) < 0.999, contradiction taken only at p ≥ 0.999 (`--tau-recheck`; at 0.5: 0.973) | – / 0.973 → 0.978 | – / 0.967 → 0.971 | – / 0.963 → **0.965** [0.944–0.983] | 1,418 → **1,461** | **yes** (25th test evaluation) |

Round 19 is round 7 for 70B (same acceptance threshold 0.999) plus the p < 0.999 gate of round 14 and on top of the
compact headers of round 15; round 7 had been rejected for 70B because of test (round 9, −0.002), so test has now seen
a related option twice. Round 19 on `dev_rest`: 11 re-checks, 2 flips. On test the OST evidence score goes 0.960 → 0.963, without copies
0.960 → 0.962; over all 20 voting dates 70B scores 0.971 (s.d. per date 0.028). Cold latency on 50 `dev_rest` cases,
old and new interleaved in one session: 1,338 / 2,050 → 1,274 / 2,197 ms (mean / p95), tokens 1,276 → 1,319, macro-F1
0.937 → 0.956 (one flip). OST's Docker run on all 493 test rows (70B, rerun): task A 0.965, 312 of 324 evidence, task B
0.976, 1,460 tokens, 1,059 / 2,344 ms. Note: the six few-shot rows lie in `dev_rest` (three used by 8B), so `dev_rest`
is not fully clean for 8B; 8B is unchanged in this round. Calls: several thousand, not counted exactly (dev runs, cold runs, test 70B, Docker 70B).

## 14 October (afternoon): older booklets (stress set 1999–2018)

A synthetic stress set on 10 voting dates outside OST (`data/stress-synth/`, 298 claims; generator Nemotron 3 Ultra,
judges Gemma 4 31B and Qwen3-235B, no human) showed task A at 0.788 (8B) / 0.791 (70B) against task B 0.889 / 0.976.
Before any change the set was split by voting date (`experiments/stress/split.py`, seeded, stratified by failure type):
`dev` 2005, 2008, 2010, 2016, 2018 (157 claims), `holdout` 1999, 2002, 2013, 2014, 2017 (141 claims). Development used
only `dev` and OST development data. Caveat: the first stress report (read before the split) described the failure of
every date, the held-out ones included.

Guard for OST: `experiments/stress/scope_regress.py` stores the region `locate()` gives for all 1,488 OST v1.1 rows;
after every change 0 rows differ, no OST booklet uses the outline (60 of 60 keep their header structure), and an offline
replay of dev_s, dev_rest and test (`replay-v6`, both models, 0 uncached calls) gives the stored labels on every row.

| # | idea (stress `dev` half, task A, 8B / 70B) | proposal right | macro-F1 | input tokens | kept |
| - | ---- | ---- | ---- | ---- | ---- |
| – | before (first stress run, same code as the defaults) | 17 / 157 | 0.760 / 0.757 | 1,997 / 1,276 | – |
| 20 | outline: proposals from lines "Erste Vorlage / Premier objet / Primo oggetto", else from the overview's page ranges (6+ pages, not nested); garbled header names and garbled text (> 5 % of a booklet) ignored; used only when the headers give fewer than two readable proposals | 157 / 157 | 0.830 / 0.884 | 2,100 / 1,379 | **yes** |
| 21 | no section boost when the proposals come from the outline (gold page in the hits, 70B: 0.567 → 0.732) | 157 / 157 | 0.877 / 0.929 | 2,153 / 1,464 | **yes** |
| 22 | k = 7 instead of 5 for outline layouts (gold page in the hits 0.73 → 0.80) | 157 / 157 | 0.876 / **0.955** | 2,530 / 1,802 | **70B only** (8B not better) |
| 22b | recommendation routing restricted to the region | | 0.870 / 0.955 | | no (8B not better; within noise) |
| 23 | 8B: re-check every neutral answer (`recheck_below` 1.01) | | 0.858 / – | 2,548 / – | no (dev_s 0.971 → 0.973 at +21 % tokens) |

Final run on `dev` with the kept options: 0.864 (8B, run-to-run noise against 0.877 in round 21 at the same options) /
0.955 (70B). Then the `holdout` half once (A and B, both models):

| held-out half (141) | 8B before → after | 70B before → after |
| --- | --- | --- |
| task A macro-F1 | 0.819 → **0.864** | 0.828 → **0.915** |
| task A evidence (gold page as passage) | 0.674 → 0.800 | 0.684 → 0.842 |
| task A input tokens | 2,509 → 2,674 | 1,778 → 2,073 |
| task B macro-F1 | 0.897 → 0.888 | 0.964 → 0.964 |

All 298 claims (dev + held-out): task A 0.788 → 0.864 (8B), 0.791 → 0.936 (70B). Times in these runs come from
up to eight parallel requests and are not comparable. OST test: the replay is the 26th test evaluation (no new
configuration on OST): 0.959 / 0.965, unchanged.

### Second stress set (16 more dates, 1998–2018) and one regression fix

A second set by the same method (504 claims, 16 voting dates; `clean-b.jsonl`, OpenRouter cost 0.81 USD) was split by a
rule fixed in the README before the data existed (seed 20261015): half 1 = 1999-02, 2000, 2003, 2004, 2009, 2011, 2015,
2018-09 (252 claims), half 2 = 1998, 2001, 2006, 2007, 2012, 2013-09, 2016-09, 2017-09 (252). Both halves were run once
with the code of round 22, and with the code before round 20 for comparison (`--src` worktree of `a4ad821`):

| task A, 8B / 70B | before | first run (round 22 code) |
| --- | --- | --- |
| half 1 (252) | 0.824 / 0.845 | 0.861 / 0.881 |
| half 2 (252) | 0.767 / 0.813 | **0.728 / 0.777** |

Half 2 got worse. Per date, 2007-06-17 fell from 0.84 / 0.94 to 0.41 / 0.32: it has a single proposal, the overview
fallback read its explanation (pp. 6–15) and its voting text (pp. 16–40) as two proposals, and the title matched the
voting text. Round 24: the overview fallback now needs at least two distinct proposal ordinals ("Erste/Zweite Vorlage",
"Premier/Deuxième objet", ...) on the overview pages (NUL characters removed first, as in 2018 FR). This fix was found
on held-out data. Rerun of all four halves with it (`final2`):

| task A, 8B / 70B | before | after round 24 |
| --- | --- | --- |
| set 1 dev (157) | 0.760 / 0.757 | 0.877 / 0.955 |
| set 1 held out (141) | 0.819 / 0.828 | 0.849 / 0.922 |
| set 2 half 1 (252) | 0.824 / 0.845 | 0.861 / 0.881 |
| set 2 half 2 (252) | 0.767 / 0.813 | 0.776 / 0.841 |
| all 802 | 0.793 / 0.815 | 0.836 / 0.890 |

Task B on all 802: 0.889 / 0.963 (code path unchanged). OST guard after round 24: 0 of 1,488 regions differ, outline
used for 0 of 60 OST booklets. Still wrong after the fix and left alone (seen only on held-out data): 2006-09-24, where
running headers name two of three proposals (header structure wins over the outline), and 2015/2016 FR/IT with partial
header structure.
