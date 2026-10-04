# Technical report — GeaNaVid

- **Track:** Track 2A — OST: Multilingual NLI over Swiss Official Voting Booklets
- **Event:** Online
- **Team:** Apertool — Niklas Wichter
- **Demo:** [TBD: video link] · `make run` in `track_2a/`

_Draft of 4 October 2026. All numbers are from runs on OST v1.0 stored in `runs/v1/`; open measurements are
marked [TBD]. Ablations, retrieval recall, calibration, error analysis and the full tables are in
`docs/EXPERIMENTS-v1.md`._

## 1. Summary

Swiss voters meet many claims about federal proposals; the official voting booklet is the authoritative
source, but it runs to 40–90 pages in three languages. GeaNaVid checks a claim in German, French or
Italian against a booklet and returns entailment, neutral or contradiction together with the passages
that decide the label, the token usage and the time. We treat the task as document-level natural
language inference [@yin2021docnli; @koreeda2021contractnli], close to claim verification with evidence
[@thorne2018fever], but judged only against the booklet, never against the world.

Our CLI `booklint` parses the PDF without a language model, narrows the booklet to the proposal named in
the case's `vote` field, retrieves a few passages with BM25 and asks Apertus v1.5 for a strict JSON verdict
with evidence first and label second. Cross-lingual claims are translated into the booklet language by
Apertus before retrieval. On the official OST v1.0 benchmark (497 held-out test pairs), Apertus 8B reaches
a macro-F1 of 0.941 [95% CI 0.919–0.960] with 2,258 input tokens per claim, against 0.723 for the
whole-booklet baseline (20,156 input tokens). Apertus 70B reaches 0.951 [0.931–0.970] with 1,631 input
tokens, against 0.890. In the Beginner task (gold reference given), 8B reaches 0.978 and 70B 0.980.
The output is never a voting recommendation: every verdict comes with a quote from the booklet.

## 2. System design and architecture

The CLI reads OST's case format (`id`, `booklet.path` or `reference.text`, `vote`, `claim.text`) and prints
OST's output format (`id`, `label`, `label_name`, `evidence[{page, text}]`,
`metrics{input_tokens, output_tokens, inference_time_ms}`). The default pipeline for the Advanced task:

1. **Ingest** (once per booklet, no LLM, cached): text blocks with page, proposal, section and committee note.
2. **Languages** of claim and booklet from function words and letters; no language field needed.
3. **Proposal**: the booklet is narrowed to the proposal named by `vote` (BM25 over proposal titles and
   texts). A `vote` title in another language than the booklet is first translated by Apertus.
4. **Translation**: a cross-lingual claim is translated into the booklet language by Apertus.
5. **Retrieval**: BM25 top-5 over claim and translation inside the proposal, plus same-page neighbours.
6. **Apertus NLI**, one call: numbered passages, JSON schema with evidence before label. With 8B the prompt
   carries three development examples, and a verdict with p(label) < 0.9 is re-checked by splitting the
   claim into atomic statements (two more calls).
7. **Evidence sentence** (no LLM): the sentence of the cited or retrieved passages that covers most of the
   claim, with its page.

For the Beginner task (claim + reference text) steps 3 and 5 are skipped: the reference is the context.
A failed case (missing or scanned PDF, endpoint error) is answered neutral with an `error` field, so a
batch never stops.

### 2.1 Document parsing and context preparation

**Parsing.** PyMuPDF text blocks are cleaned (soft hyphens, line-break hyphenation, footnote digits that
otherwise glue to numbers). Each block keeps its page (1-based PDF index), the proposal from the running
header, the nearest bold side heading ("In Kürze", "Empfehlung von Bundesrat und Parlament") and the
committee note. Parsing is deterministic and costs no tokens. Booklets without a text layer are reported as
failed cases (no OCR yet).

**Context preparation.** (a) Locating the proposal by the `vote` title keeps 93.7 % of the gold section
inside about a quarter of the booklet (median 19 k of 82 k characters). (b) BM25 [@robertson2009bm25] over
heading plus text, with number normalisation and prefix stemming, fused across claim and translation by
reciprocal rank [@cormack2009rrf]; BM25 needs no GPU and is a strong zero-shot baseline
[@thakur2021beir]. hit@5 of the gold section is 0.928 on test with translation, 0.718 without and 0.604
over the whole booklet. (c) The five hits and their same-page neighbours, each prefixed with page, proposal
and section, give about 1.2 k tokens of context instead of 20 k for the whole booklet (p95 30 k).

**NLI call and evidence.** Apertus names the deciding passage numbers before the label, as in
evidence-first setups [@thorne2018fever; @koreeda2021contractnli]. The returned evidence is a verbatim
booklet sentence chosen after the decision without an LLM call (idf-weighted word stems and character
5-grams against claim and translation); `--evidence-unit paragraph` returns the whole text block.

**Not in the default.** A page-window ladder [@li2024ragvslong], an 8B → 70B cascade
[@chen2023frugalgpt], the parallel language version instead of translation, dense or hybrid retrieval,
Apertus reranking, label calibration and number rules are flags; on the development subset none paid for
its cost (`docs/EXPERIMENTS-v1.md`).

## 3. Use of Apertus

- **Model:** swiss-ai/Apertus-v1.5-8B and swiss-ai/Apertus-v1.5-70B [@apertus2025]
- **How it is used:** inference only: the NLI verdict with evidence selection, the translation of
  cross-lingual claims and of foreign `vote` titles, and (8B) the split of unsure claims into atomic statements.
- **Where it runs:** the Hack Apertus OpenAI-compatible endpoint, selected through `LLM_NAME`,
  `LLM_BASE_URL`, `LLM_API_KEY`; temperature 0, JSON schema, `logprobs` with 10 alternatives.

The label probability is read from the first token of the label value. No other model takes part in the
default path. Every call is cached on disk by a hash of model, messages and parameters, which makes reruns
free and reproducible.

## 4. Evaluation

**Data.** OST v1.0 (MIT) has 1,495 claim-booklet pairs, 60 booklets from 20 voting dates (2020–2026),
177 proposals, balanced labels and 974 pairs (65 %) cross-lingual
(`OSTswiss/MNLIoverSwissVotingBooklets`). Split by
voting date (seed 2026), so the DE/FR/IT versions of a booklet never cross splits: 998 development pairs
(13 dates), of which a stratified subset of 450 was used for all ablations, and 497 test pairs (7 dates,
21 booklets); each configuration ran once on test with settings frozen on development data. v1.0
contains 335 rows that are exact copies of another row (same claim, booklet and label), 122 of them in
test (375 distinct pairs). We keep them as published; a plain bootstrap then counts copies as independent
evidence and its intervals are too narrow. Recomputed from the stored predictions (no new calls), the
defaults score 0.931 (8B) and 0.944 (70B) without copies; resampling each group of copies as one unit
widens the intervals to [0.915–0.963] and [0.928–0.971] (by proposal: about the same). All reported numbers
use OST v1.0 only. Two auxiliary sets written by closed LLMs are used for no reported number: 24 unreviewed
edge cases (Gemini 3.8 Flash via the Antigravity CLI), demo presets only, and never evaluated because 16 of
them concern proposals of the test dates; and archived synthetic development sets from before v1.0 (Claude
Opus 5.5, GPT-5.5). A unit test checks that no stored run contains an edge case; sources and per-row
provenance are in `data/README.md`.

**Metrics** as on OST's slide 28: macro-F1 over the three labels with 95 % bootstrap intervals (1,000
resamples), separately for Beginner and Advanced and by language; evidence against the gold section
(`reference_string`) and its page; input tokens per claim (what OST sums); mean and p95 of
`inference_time_ms`.

**Main results** (test, macro-F1; input tokens per claim, 8B / 70B where they differ):

| Setup | 8B | 70B | Input tok. |
| --- | --- | --- | --- |
| Baseline: whole booklet | 0.723 | 0.890 | 20,156 |
| Beginner: gold section | 0.940 | **0.980** | 2,080 |
| Beginner + 3 examples (8B) | **0.978** | – | 2,662 |
| Adv.: BM25, whole booklet | 0.762 | – | 1,367 |
| Adv.: proposal + BM25 | 0.778 | 0.819 | 1,312 |
| Adv.: + translation | 0.940 | **0.951** | 1,636 / 1,631 |
| Adv.: + 3 ex. + decomp. | **0.941** | – | 2,258 |

Defaults: 8B = last row, 70B = translation row. The 8B pipeline beats the 8B baseline by +0.218 and even
the 70B baseline; 70B gains +0.061. Both need 1.6–2.3 k instead of 20 k input tokens per claim. With 70B, adding the
decomposition gives 0.955 (within noise); the optional parallel version instead of translation gives
0.953 for 8B.

**By language** (test, macro-F1; claim or booklet language, n in brackets):

| Group (n) | Adv. 8B | Adv. 70B | Beg. 8B | Beg. 70B |
| --- | --- | --- | --- | --- |
| All (497) | 0.941 | 0.951 | 0.978 | 0.980 |
| Claim DE (166) | 0.937 | 0.951 | 0.956 | 0.963 |
| Claim FR (165) | 0.939 | 0.951 | 0.982 | 0.989 |
| Claim IT (166) | 0.944 | 0.950 | 0.994 | 0.988 |
| Booklet DE (156) | 0.923 | 0.936 | 0.974 | 0.987 |
| Booklet FR (186) | 0.967 | 0.973 | 0.983 | 0.989 |
| Booklet IT (155) | 0.927 | 0.942 | 0.974 | 0.965 |
| Same lang. (166) | 0.980 | 0.974 | 0.980 | 0.987 |
| Cross-ling. (331) | 0.922 | 0.940 | 0.976 | 0.977 |

The whole-booklet baseline drops on cross-lingual pairs (8B 0.801 same vs. 0.685 cross); translation closes
most of the gap. With the claim language detected instead of read from the data, the Advanced results are
identical (detection right on 497 of 497 test claims).

**Evidence (Advanced).** The first evidence sentence lies inside the gold section for 0.786 (8B) and 0.804
(70B) of entailment/contradiction answers, and on a gold page for 0.802 / 0.823 (median 238 / 219
characters). The whole paragraph scores 0.777 / 0.798 at about 2.5× the length. This proxy is strict: the
booklet often says the same thing twice and only one place is gold. In a read sample of 30 sentences (8B),
22 decide the claim, 7 partly, 1 does not. How OST matches evidence is not yet known, so OST's evidence
score is [TBD].

**Efficiency as OST measures it.** Cold run on 50 seeded test cases in OST's input format, no response
cache, one request at a time; `inference_time_ms` is the wall time of one case (booklet parsed beforehand):

| Model | Input tok. | Calls | Mean ms | p95 ms |
| --- | --- | --- | --- | --- |
| 8B | 2,205 | 1.72 | 457 | 819 |
| 70B | 1,630 | 1.68 | 1,366 | 2,119 |

The endpoint's prefix cache cannot be switched off; tokens counted by OST's proxy are [TBD].

## 5. Reproducibility

`make run` builds the Docker image and runs the default pipeline on the test split against the endpoint in
`LLM_*`; no GPU or local weights are needed. For OST's own cases: `booklint predict --case <cases.jsonl>`
(mounts and `BOOKLET_ROOT` in `track_2a/README.md`). Settings: prompt `nli-v1`, k = 5, one neighbour,
temperature 0, JSON schema. Replaying the stored test runs from the response cache with the current code
gives the same 497 labels for both models; each run in `runs/v1/` stores its options, split seed and
command. At temperature 0 the endpoint is not fully deterministic: a cold rerun of 50 cases gave the same
label on 50/50 (8B) and 49/50 (70B). Commit of the submission: [TBD].

## 6. Limitations

497 test claims (375 distinct) from 7 voting dates: differences below about 0.02–0.03 macro-F1 are within
the cluster-bootstrap interval (70B − 8B: +0.011 [−0.011; +0.033]), and the model-aware defaults (examples and decomposition only for 8B) were chosen on 450
development claims. Main error sources are topical but unsupported claims, attribution (committee vs.
Federal Council) and claims about the front-page summary. Booklets without a text layer are not handled
(no OCR). Labels and evidence are an automated reading of the booklet, not a voting recommendation.

Open questions to OST (Q&A on 2026-10-08): whether `page` is the PDF index or the printed page number;
which page the Beginner task expects (we return `page: 1`); how evidence is matched; and whether the
token-counting proxy passes `response_format` and `logprobs` through. Without them the client retries
without schema and log-probabilities and the 8B decomposition is skipped (about −0.004 macro-F1 on
development data).

## 7. Lessons learned

- **Narrow first, then read.** Locating the proposal by its title costs nothing; with translation it beats
  the whole booklet by +0.22 (8B) and +0.06 (70B) with 1.6–2.3 k instead of 20 k input tokens. 8B with this context
  (0.941) beats 70B with the whole booklet (0.890).
- **Translation is the largest single step** for cross-lingual claims (8B cross-lingual 0.696 → 0.938).
- **Prompt rules move the boundary instead of sharpening it.** Rules for "neutral" made 8B call real
  contradictions neutral; three worked examples helped on development data but not on test for the
  Advanced task. Apertus is very confident (p > 0.9 for 94–98 % of answers), so probability gates rarely
  fire and calibration offsets were unstable.
- **Cheap evidence.** Choosing the evidence sentence after the decision costs no tokens and lands in the
  gold section more often than the whole cited passage (0.79 vs. 0.62 for 8B).
- **Measure what the judges measure.** OST sums input tokens and takes mean and p95 of time per claim; our
  first numbers (total tokens, warm cache) had to be re-measured cold.
- **Check the input format, not only the dataset.** OST's cases have no language field and may carry a
  `vote` in another language; translating the title raises the right proposal from 70 % to 95–98 %.

Next steps: settle evidence unit and page numbering with OST, OCR for scanned booklets
[@stuessi2026votingbooklets], extend to Romansh.

## License

This report and the documentation: Creative Commons Attribution 4.0 (CC-BY-4.0). Code: Apache-2.0. Our edge-case set
(`data/edge_cases.jsonl`): CDLA-Permissive-2.0. The OST benchmark and the splits derived from it keep their MIT licence.
All HackApertus projects are open-sourced.

## References
