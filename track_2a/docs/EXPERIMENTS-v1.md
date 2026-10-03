# Experiments on OST v1.0 (2026-10-02)

All numbers on this page come from `runs/v1/<split>/<model>/<run>.{jsonl,config.json,summary.json}`.
Each run stores its full option set, the split seed and the command. Tables are produced with
`python experiments/v1/table.py <split>`. Earlier numbers (28-row demo, synthetic sets) are archived in
`data/archive/` and `runs/archive/` and are superseded by this page.

## Data and protocol

- **Dataset:** `OSTswiss/MNLIoverSwissVotingBooklets` `v1.0.jsonl` (HF commit `adca9a5`, MIT), 1,495 rows,
  20 voting dates × 3 language versions = 60 booklets (2020–2026), 177 proposals, labels balanced,
  974 rows cross-lingual (claim language ≠ booklet language). Stored in `data/v1/v1.0.jsonl`.
- **Split** (`experiments/v1/split.py`, seed 2026): by voting date, so the DE/FR/IT versions of a booklet and
  translated copies of a claim never cross splits. 7 test dates (21 booklets, **497 rows**) chosen among 5,000
  seeded draws for the best balance of size, labels and languages; 13 dev dates (39 booklets, 998 rows).
  The demo booklet (2026-06-14), used to tune the first prototype, is forced into dev.
  `dev_s` = 450 dev rows, stratified by label × same/cross language; all ablations ran on `dev_s`.
  **`test` was used once, for the final table below; nothing was tuned on it.**
- **Two tasks** (our assumption until OST's slides are out):
  _easy_ = the gold section `reference_string` is the context;
  _hard_ = only the booklet is given, the system finds the passage itself.
- **Metrics:** macro-F1 with 95 % bootstrap interval, F1 per label, macro-F1 for same-language and
  cross-language rows; tokens per claim = prompt + completion tokens of all Apertus calls (translation,
  judgement, decomposition) from the API `usage` field; calls per claim; Apertus time per claim (sum of call
  latencies, 4 parallel requests). For the hard task, _hit@k_ = at least one of the k retrieved chunks lies
  inside the gold section (normalised substring match of the chunk against `reference_string`; 95 % of the
  gold section text maps to our chunks).
- **Models:** `apertus-v1.5-8b`, `apertus-v1.5-70b` on the Hack Apertus endpoint, temperature 0, strict
  `json_schema`, `top_logprobs` 10. ~14,900 uncached Apertus calls in total.

## Baseline: whole booklet

OST's `baseline_score` is described as "Apertus gets the whole booklet". We rebuilt that: the plain text of
every page (PyMuPDF, `(p. N)` prefix) plus the claim, same NLI prompt as our pipeline. Booklets are
20 k tokens on average on test (p95 30 k, max 118 k with our chunk prefixes; the endpoint accepts it).

| model | split | macro-F1                | F1 same | F1 cross | tokens/claim |
| ----- | ----- | ----------------------- | ------- | -------- | ------------ |
| 8B    | dev_s | 0.655                   | 0.759   | 0.597    | 28,305       |
| 70B   | dev_s | 0.853                   | 0.857   | 0.852    | 28,302       |
| 8B    | test  | **0.723** [0.684–0.760] | 0.801   | 0.685    | 20,182       |
| 70B   | test  | **0.890** [0.862–0.917] | 0.916   | 0.876    | 20,176       |

Apertus time per claim looks small (8B 0.6 s, 70B 1.3 s mean on test) because rows of one booklet run in a
row and the server reuses the cached booklet prefix; a cold call on a 30 k-token booklet takes 3–8 s.

**What `baseline_score` is:** a float per row, 0.606–0.999, mean 0.877, identical for duplicated rows, the
same mean for same- and cross-language rows. It is not a label and it does not tell which label the baseline
predicted, so OST's baseline macro-F1 cannot be computed from it. It does not track our baseline: Pearson
r with our p(predicted label) = −0.03 (8B) / −0.13 (70B), with our p(gold label) −0.12 / −0.14, with our
correctness −0.12 / −0.11; it is not an e5 cosine between claim and gold section (r = 0.07) or its best
sentence (r = 0.02). It is slightly higher for contradiction rows (0.897) than for entailment rows (0.862).
Most likely the confidence of OST's own baseline run for its (unpublished) predicted label; to be confirmed
by OST.

## Steps (dev_s, 450 rows)

Each row adds one step to the row above it unless stated otherwise. Same/cross = macro-F1 on the 160
same-language and 290 cross-language rows.

| step                                                 | 8B F1     | 8B same / cross | 8B tokens | 70B F1                                      | 70B same / cross | 70B tokens |
| ---------------------------------------------------- | --------- | --------------- | --------- | ------------------------------------------- | ---------------- | ---------- |
| Baseline: whole booklet                              | 0.655     | 0.759 / 0.597   | 28,305    | 0.853                                       | 0.857 / 0.852    | 28,302     |
| Easy task: gold section                              | 0.924     | 0.918 / 0.928   | 2,068     | **0.971**                                   | 0.962 / 0.976    | 2,065      |
| Easy + 3 examples                                    | **0.959** | 0.962 / 0.958   | 2,644     | 0.948                                       | 0.942 / 0.951    | 2,644      |
| Hard 1: BM25 top-5 over the whole booklet            | 0.758     | 0.900 / 0.677   | 1,450     | 0.798                                       | 0.956 / 0.709    | 1,448      |
| Hard 2: proposal first (vote title), then BM25 top-5 | 0.826     | 0.937 / 0.765   | 1,354     | 0.847                                       | 0.962 / 0.782    | 1,353      |
| Hard 3: + Apertus translates the claim               | 0.909     | 0.937 / 0.893   | 1,650     | **0.949**                                   | 0.962 / 0.941    | 1,656      |
| Hard 4: + 3 dev examples in the prompt               | 0.942     | 0.968 / 0.927   | 2,228     | 0.930                                       | 0.930 / 0.930    | 2,234      |
| Hard 5: + decomposition when p < 0.9                 | **0.946** | 0.968 / 0.934   | 2,261     | 0.944 (Hard 3 + decomposition, no examples) | 0.969 / 0.930    | 1,684      |

Variants of step 3 (8B), each against Hard 3 = 0.909:

| variant                                                              | F1                        | tokens                | verdict                                             |
| -------------------------------------------------------------------- | ------------------------- | --------------------- | --------------------------------------------------- |
| k = 3 / k = 8                                                        | 0.891 / 0.904             | 1,220 / 2,220         | k = 5 stays                                         |
| ladder (escalate to page window when p < 0.75 or no evidence)        | 0.906                     | 2,222                 | no gain                                             |
| whole proposal as context                                            | 0.816                     | 12,510                | worse and 7× tokens                                 |
| number hint in the prompt                                            | 0.902                     | 1,652                 | no gain                                             |
| 3 / 4 / 6 examples                                                   | **0.942** / 0.932 / 0.930 | 2,228 / 2,522 / 2,816 | 3 is best                                           |
| decomposition alone (p < 0.9, 25 of 450 claims; 9 with examples)     | 0.915                     | 1,749                 | +0.006, noise level                                 |
| proposal found from the claim instead of the vote title              | 0.831                     | 1,669                 | vote title matters                                  |
| _optional:_ parallel language version instead of translation         | 0.922                     | 1,490                 | as good, fewer tokens                               |
| _optional:_ cascade 8B → 70B when p < 0.9 (on Hard 5)                | 0.944                     | 2,268                 | 6 escalations, no gain                              |
| Apertus yes/no rerank of the top 12 (first 150 rows, all entailment) | acc. 0.953 vs 0.920       | 4,794 vs 1,754        | hit@5 0.927 → 0.987, but 2.7× tokens, 14 calls, 6 s |

### Retrieval recall (offline, 0 tokens)

hit@k against the gold section, `experiments/v1/recall.py`; dev (998 rows) without translation,
dev_s (450) with the 8B translation.

| retrieval                            | region                 | query                       | hit@1 | hit@3 | hit@5     | hit@10 | context tokens @5 |
| ------------------------------------ | ---------------------- | --------------------------- | ----- | ----- | --------- | ------ | ----------------- |
| BM25                                 | booklet                | claim                       | 0.318 | 0.483 | 0.565     | 0.678  | 1,081             |
| BM25                                 | claim-located proposal | claim                       | 0.318 | 0.442 | 0.487     | 0.543  | 1,058             |
| BM25                                 | vote proposal          | claim                       | 0.462 | 0.654 | 0.724     | 0.797  | 1,011             |
| e5-small dense                       | vote proposal          | claim                       | 0.383 | 0.543 | 0.640     | 0.767  | 935               |
| hybrid BM25 + e5 (RRF)               | vote proposal          | claim                       | 0.458 | 0.673 | 0.775     | 0.873  | 1,070             |
| BM25                                 | vote proposal          | claim + translation (dev_s) | 0.593 | 0.836 | **0.907** | 0.964  | 1,228             |
| hybrid BM25 + e5                     | vote proposal          | claim + translation (dev_s) | 0.584 | 0.807 | 0.898     | 0.958  | 1,138             |
| _optional:_ BM25 on parallel version | vote proposal          | claim (dev_s)               | 0.602 | 0.844 | 0.911     | 0.942  | 1,185             |

Locating the proposal by its title (`vote`) keeps 93.7 % of the gold section inside a region of about a quarter
of the booklet (median 19 k of 82 k characters); located from the claim alone it keeps 58 %.
The embedding model (`intfloat/multilingual-e5-small`, MIT, 118 M parameters, ONNX on CPU) helps only without
translation; with translation BM25 alone is as good, so dense retrieval stays an optional extra (`[dense]`).

### Calibration and number rules (offline, 0 tokens)

- **Calibration:** label log-offsets for neutral and contradiction, grid −4…4, fitted on dev_s, checked by
  2-fold cross-fitting over voting dates. Apertus is confident (p > 0.9 for 94–98 % of answers). Cross-fitted
  gains: hard 8B +0.009, hard 70B +0.005, easy 8B +0.024, easy 70B −0.002; the fitted offsets are large and
  change sign between runs (neutral −3.5 … +1.25). Applied to test with dev_s offsets: hard 8B 0.941 → 0.945,
  hard 70B 0.951 → 0.952, easy 8B 0.940 → 0.958, easy-with-examples 8B 0.978 → 0.976. Not in the default
  (unstable, small); available as `--calib '{"neutral": …, "contradiction": …}'`.
- **Numbers:** amounts, percentages, years and durations of the claim (digits, scale words such as
  Millionen/millions/milioni, a few number words) are matched against the text. Against the gold section,
  a claim number that is missing means "not entailment" in 128 of 128 dev rows (neutral 114, contradiction 14).
  But Apertus already gets these cases right: the rule "missing number → neutral instead of entailment"
  changes nothing on dev_s and test (±0.002), and the number hint in the prompt costs 0.007. Kept as an option
  (`--numbers hint|rule`).

### Error analysis (dev_s, 8B)

| run                   | errors | retrieval miss | E/C without cited passage | wrong judgement on the right passage | main confusions                               |
| --------------------- | ------ | -------------- | ------------------------- | ------------------------------------ | --------------------------------------------- |
| Hard 3 (translation)  | 41     | 9              | 8                         | 24                                   | C→N 13, N→C 8, C→E 8, E→C 7                   |
| Hard 4 (+ 3 examples) | 26     | 6              | 1                         | 19                                   | C→N 12, C→E 8                                 |
| Easy (gold section)   | 34     | –              | –                         | 34                                   | N→C 19 (unrelated claim called contradiction) |

Error rates by claim type (Hard 3): claims about "the summary" (Zusammenfassung / résumé / riassunto)
19 %, negations 15 %, "the voting text" 12 %, committee claims 10 %, Federal Council claims 0.6 %.
Typical failures: the committee's argument is judged against the Federal Council's opposite view
(gold: entailment), invented facts that sound like the booklet are called contradiction (gold: neutral),
claims about the front-page summary miss the summary passage. The three prompt examples
(`src/booklint/fewshot.json`, dev rows outside dev_s: committee claim → entailment, unrelated claim → neutral,
"summary says the opposite" → contradiction) target exactly these and almost remove the "no passage cited" errors (8 → 1).

## Final numbers (test, 497 rows, run once)

| run                                                 | 8B F1 [95 % CI]         | 8B same / cross | 8B tokens | 70B F1 [95 % CI]        | 70B same / cross | 70B tokens |
| --------------------------------------------------- | ----------------------- | --------------- | --------- | ----------------------- | ---------------- | ---------- |
| Baseline: whole booklet                             | 0.723 [0.684–0.760]     | 0.801 / 0.685   | 20,182    | 0.890 [0.862–0.917]     | 0.916 / 0.876    | 20,176     |
| Easy: gold section                                  | 0.940 [0.917–0.961]     | 0.918 / 0.950   | 2,101     | **0.980** [0.968–0.990] | 0.987 / 0.977    | 2,098      |
| Easy + 3 examples                                   | **0.978** [0.964–0.990] | 0.980 / 0.976   | 2,678     | –                       | –                | –          |
| Hard: BM25 whole booklet                            | 0.762                   | 0.943 / 0.672   | 1,387     | –                       | –                | –          |
| Hard: vote proposal + BM25                          | 0.778                   | 0.943 / 0.696   | 1,333     | 0.819                   | 0.974 / 0.741    | 1,331      |
| Hard: + translation                                 | 0.940 [0.919–0.959]     | 0.943 / 0.938   | 1,683     | **0.951** [0.931–0.970] | 0.974 / 0.940    | 1,675      |
| Hard: + 3 examples                                  | 0.940                   | 0.980 / 0.922   | 2,260     | –                       | –                | –          |
| Hard: + 3 examples + decomposition (**8B default**) | **0.941** [0.919–0.960] | 0.980 / 0.922   | 2,302     | –                       | –                | –          |
| Hard: + decomposition, no examples                  | –                       | –               | –         | 0.955 [0.937–0.972]     | 0.974 / 0.946    | 1,709      |
| Hard, no vote title (proposal from claim)           | 0.918                   | 0.949 / 0.903   | 2,321     | –                       | –                | –          |
| _optional:_ parallel version instead of translation | 0.953                   | 0.980 / 0.940   | 2,195     | –                       | –                | –          |

hit@5 on test: 0.928 with translation, 0.718 without, 0.604 over the whole booklet.
Apertus time per claim on test (mean): 8B default 0.76 s, 70B default 1.69 s (1.67 calls per claim).

**Reading:**

- The hard-task pipeline beats the whole-booklet baseline by **+0.22 (8B)** and **+0.06 (70B)** macro-F1
  with **8–9 % of the tokens** (1.7–2.3 k instead of 20 k per claim).
- 8B with our pipeline (0.941) is better than 70B with the whole booklet (0.890).
- Translation by Apertus is the largest single step on cross-lingual rows (8B cross 0.696 → 0.938).
- The gain from the three examples on dev_s (+0.033) **did not carry over to test** for the hard task
  (0.940 → 0.940; same-language +0.04, cross-language −0.02). For the easy task it did (+0.038).
  The examples stay in the 8B default because they never hurt 8B on either split and fix the
  "no passage cited" errors, but the honest effect on the hard task is about zero at +600 tokens.
- The 70B choice "no examples, no decomposition" was made on dev_s (0.949 vs 0.944 with decomposition);
  on test the decomposition variant scored 0.955 vs 0.951. Both differences are within 2–3 rows.

## Sentence-level evidence (offline, 0 tokens)

Every answer now carries `decision` (= `entailment_label`), `answer` (yes / blank / no), `page` and
`evidence_sentence`: the sentence of the booklet that supports or contradicts the claim, verbatim, with
`char_start`/`char_end` (`src/booklint/sentences.py`). Neutral answers carry no page, sentence or passages.
The sentence is picked after the decision, without an Apertus call: the passages Apertus cited and the other
top-5 BM25 passages are split into sentences (DE/FR/IT abbreviations, ordinals and article numbers do not end a
sentence); each sentence is scored by the share of the claim and of its translation it covers (idf-weighted
word stems and character 5-grams, so split words such as "Bundes steuer" still match), divided by a mild
length penalty; sentences of cited passages get a bonus of 1.2. The best sentence is extended by an adjacent
sentence of the same passage if that one scores at least 70 % of it, and a second span from another passage
is added under the same rule. In `easy` mode the candidates are the chunks of the gold section, in `baseline`
mode the chunks of the pages Apertus cited.

Choices on dev_s (8B default run, 288 E/C answers; 70B Hard 3, 290): 8B cited passages only 0.70 → plus the other
top-5 passages with bonus 1.0 / **1.2** / 1.5 / 2.0: 0.780 / **0.780** / 0.753 / 0.722 (70B 0.797 / **0.814** /
0.803 / 0.783); a bonus for matching claim numbers cost 0.014 (contradictions have different numbers) and was
dropped; the length penalty matters little (±0.01).

**Test** (stored runs re-run from the response cache, 0 Apertus calls; `runs/v1/test/<model>/{default,ret-vote-tr}-sentences.*`,
`python experiments/v1/sentences.py test <model> <run>`): share of E/C answers whose first evidence sentence
lies inside the gold section `reference_string` (normalised substring match).

| sentence choice                                    | 8B default (323 E/C answers) | 70B default (316) |
| -------------------------------------------------- | ---------------------------- | ----------------- |
| first cited passage (whole chunk, before)          | 0.616                        | 0.652             |
| first sentence of the first cited passage          | 0.625                        | 0.652             |
| best sentence of the cited passages only           | 0.700                        | 0.782             |
| **best sentence, cited + top-5 (default)**         | **0.786**                    | **0.804**         |
| upper bound: any cited passage in the gold section | 0.752                        | 0.810             |

Given a cited passage inside the gold section, the chosen sentence is inside it in 91 % (8B) and 92 % (70B)
of cases. By answer type (8B): entailment same-language 0.87, cross-language 0.79; contradiction 0.78 / 0.73.
Median sentence length 147 characters (p90 269), against 300–600 for a whole passage. Macro-F1 is unchanged
(8B 0.9406, 70B 0.9512, identical labels on all 497 rows), and so are the tokens.

"Inside the gold section" is a strict proxy: the booklet often says the same thing twice (summary and
detailed section, or legal text), and only one place is gold. We therefore read a sample of 30 answers of the
8B run (seeded, stratified by predicted label × booklet language: 15 entailment, 15 contradiction, 10 per
language; `runs/v1/test/sentences-sample-8b.jsonl`) and judged whether the first sentence decides the claim:
**22 fit, 7 fit partly, 1 does not fit**. "Partly": the sentence covers only part of a multi-part claim
(e.g. "by 2030" but not "6 billion" and "60 %"; "750 million euros" but not "15 %"), the best sentence is the
second span, or the sentence is related but not decisive (one of them on a wrongly labelled claim). "Does not
fit": a neutral claim wrongly labelled contradiction, where no sentence can fit. 3 of the 30 labels are wrong;
for one of them the sentence is still the deciding one. 5 of the 30 count as misses by the gold-section proxy;
3 of those were judged fit (the same statement on another page, e.g. summary vs. detailed section). An Apertus variant
that picks the sentence number itself was planned as a fallback but not built, since the deterministic choice
is good enough at 0 tokens.

## Default of the CLI (`booklint`, `make run`)

`--mode retrieval --scope vote --translate --k 5 --neighbors 1`, BM25, recommendation routing on,
prompt `nli-v1`, and model-aware extras (`--fewshot -1`, decomposition auto): **8B** → 3 dev examples +
decomposition when p < 0.9; **70B** → neither. Without a `vote` field the proposal is located from the claim.
Not in the default (flags, off): parallel language version (`--crossling parallel`), cascade
(`--cascade apertus-v1.5-70b`), rerank (`--rerank yesno`), dense/hybrid retrieval (`--retriever hybrid`,
extra `[dense]`), calibration (`--calib`), number hint/rule (`--numbers`), ladder (`--mode ladder`).
Only Apertus and the given booklet are used in the default pipeline.

`make run` (Docker, test split) reproduces the test rows above from the response cache: 8B 0.9406, 70B 0.9512;
a live run without cache on 12 rows took 5 s.

## Reproduce

```bash
cd track_2a
export PYTHONPATH=src CACHE_DIR=.cache BOOKLINT_ENV_FILE=.env      # LLM_BASE_URL, LLM_API_KEY
python experiments/v1/split.py                                     # data/v1/{dev,dev_s,test}.jsonl + split.json
python experiments/v1/recall.py --split dev                        # retrieval recall, no LLM
bash experiments/v1/queue1.sh; bash experiments/v1/queue2.sh       # dev_s ablations (see queue3/4 for the rest)
bash experiments/v1/queue3.sh; bash experiments/v1/queue4.sh       # 70B steps, then test
python experiments/v1/analyze.py calib|numbers|errors dev_s apertus-v1.5-8b <run>
python experiments/v1/baseline_score.py dev_s apertus-v1.5-70b baseline
python experiments/v1/table.py test
```

## Draft for the technical report (section "Results on OST v1.0")

> We evaluate on OST's v1.0 benchmark (1,495 claims, 60 booklets, two thirds cross-lingual), split by voting
> date into 998 development and 497 held-out test claims; all design decisions were taken on a 450-claim
> development subset and the test set was evaluated once. Following OST, the baseline gives Apertus the whole
> booklet (20 k tokens per claim on average). It reaches a macro-F1 of 0.723 with Apertus-8B and 0.890 with
> Apertus-70B. GeaNaVid first restricts the search to the proposal named in the claim's `vote` field
> (0 tokens; 94 % of the gold section stays inside a quarter of the booklet), lets Apertus translate
> cross-lingual claims into the booklet language, retrieves five passages with BM25 and asks Apertus for
> evidence and label under a strict JSON schema. This reaches 0.941 (8B) and 0.951 (70B) with 1.7–2.3 k tokens
> per claim, i.e. +0.22 and +0.06 macro-F1 at 8–9 % of the baseline's tokens; the 8B pipeline outperforms
> the 70B baseline. Translation is the decisive step for cross-lingual claims (8B: 0.70 → 0.94).
> Given the gold section (easy setting), Apertus reaches 0.940 (8B) and 0.980 (70B); three in-context
> examples raise 8B to 0.978. Dense retrieval, LLM reranking, a page-window ladder, calibration of the label
> log-probabilities and deterministic number checks did not pay for their cost; we report them as negative
> results. Retrieval recall@5 of the gold section is 0.93, so the remaining gap to the easy setting
> (0.94 vs 0.98 for 8B) comes mostly from judgement errors on the right passage; about a quarter of the
> remaining errors are retrieval misses.

## Open points and risks

- **Easy/hard definitions** are our assumption until OST publishes the slides and recording. If the hard task
  does not provide `vote`, the claim-located variant applies (8B test 0.918 instead of 0.941).
- **`baseline_score`** meaning unconfirmed; we compare against our own re-run of the whole-booklet baseline.
- **Model-aware defaults** (examples/decomposition only for 8B) were chosen on 450 dev rows; differences
  for 70B are within noise.
- **Rate limit:** with 4–5 parallel requests about 10–17 % of 8B calls got HTTP 429 and were retried after
  1–3 s; with 3 parallel requests none. Wall time did not improve beyond 3–4 parallel requests.
- `dev_s` duplicates: v1.0 contains repeated (claim, booklet) rows; they are answered from the cache and
  counted as normal rows.
