# Technical report — GeaNaVid

- **Track:** Track 2A — OST: Multilingual NLI over Swiss Official Voting Booklets
- **Event:** Online
- **Team:** Apertool — Niklas Wichter
- **Demo:** [TBD: video link] · `make run` in `track_2a/`

_Draft of 4 October 2026. All numbers are from runs on OST v1.0 stored in `runs/v1/`; open measurements are marked [TBD]._

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
Apertus before retrieval. On the official OST v1.0 benchmark (1,495 pairs across 60 voting booklets, 2020–2026; 497 held-out test pairs),
Apertus 8B reaches a macro-F1 of 0.941 [95% CI 0.919–0.960] with 2,302 tokens per claim, beating the whole-booklet
baseline of 0.723 (20,182 tokens) by +0.218 while cutting token consumption by nearly 90%. Apertus 70B reaches 0.951
[0.931–0.970] with 1,675 tokens, beating its 0.890 baseline by +0.061 with >12× fewer tokens. In the Beginner Task
(gold reference provided), 8B reaches 0.978 and 70B reaches 0.980 macro-F1.
Our contributions are (1) a small-context pipeline for document NLI with sentence-level evidence,
(2) a measured trade-off between macro-F1, input tokens and time for 8B and 70B, including the full-document
baseline OST recommends, and (3) proposal-first retrieval with Apertus translation for cross-lingual claims,
with a zero-token alternative that uses the official parallel versions. The output is never a voting
recommendation: every verdict comes with a quote from the booklet.

## 2. System design and architecture

The CLI reads OST's case format (slide 24 of the OST session: `id`, `booklet.path` or `reference.text`,
`vote`, `claim.text`) and prints OST's output format (slide 25: `id`, `label`, `label_name`,
`evidence[{page, text}]`, `metrics{input_tokens, output_tokens, inference_time_ms}`). The default pipeline
for the Advanced task:

1. **Ingest** (once per booklet, no LLM, cached): text blocks with page, proposal, section and committee note.
2. **Languages** of claim and booklet from function words and letters; no LLM, no language field needed.
3. **Proposal**: the booklet is narrowed to the proposal named by `vote` (BM25 over the proposal titles and
   texts). A `vote` title in another language than the booklet is first translated by Apertus.
4. **Translation**: a cross-lingual claim is translated into the booklet language by Apertus.
5. **Retrieval**: BM25 top-5 over claim and translation inside the proposal, plus same-page neighbours;
   claims about a recommendation also get the recommendation blocks of the same proposal.
6. **Apertus NLI**, one call: numbered passages, JSON schema with evidence before label. With 8B the prompt
   carries three development examples, and a verdict with p(label) < 0.9 is re-checked by splitting the claim
   into atomic statements (two more calls).
7. **Evidence sentence** (no LLM): the sentence of the cited or retrieved passages that covers most of the
   claim, with its page.

For the Beginner task (claim + reference text) steps 3 and 5 are skipped: the reference is the context.
Failures of single cases (missing or scanned PDF, endpoint error) are answered neutral with an `error` field,
so a batch never stops.

### 2.1 Document parsing and context preparation

**Parsing.** PyMuPDF text blocks are cleaned (soft hyphens, line-break hyphenation, superscript footnote
digits that otherwise glue to numbers). Each block keeps its page (1-based PDF index), the proposal from the
running header ("Erste Vorlage: …", or an ordinal title in older layouts), the nearest bold side heading
("In Kürze", "Empfehlung von Bundesrat und Parlament") and the committee note ("Der Text auf dieser
Doppelseite stammt vom Initiativkomitee"). Parsing is deterministic and costs no tokens; a 40-page booklet
gives about 200 blocks in 0.3 s. Booklets without a text layer are reported as failed cases (no OCR yet).

**Context preparation.** The context is cut in three steps, none of which calls a language model except
the translation. (a) Proposal: locating the proposal by the `vote` title keeps 93.7 % of the gold section
inside a region of about a quarter of the booklet (median 19 k of 82 k characters). (b) Retrieval: BM25
[@robertson2009bm25] over heading plus text, with number normalisation (500'000 = 500 000) and prefix
stemming, fused across claim and translation by reciprocal rank [@cormack2009rrf]; BM25 needs no GPU and is
a strong zero-shot baseline [@thakur2021beir]. With the translation, hit@5 of the gold section is 0.93 on
test. (c) Passages: the five hits and their same-page neighbours, each prefixed with page, proposal and
section, about 1.2 k tokens of context. The whole booklet would be 20 k tokens on average (p95 30 k).

**NLI call.** The passages are numbered; Apertus answers under a JSON schema with the deciding passage
numbers before the label, as in evidence-first setups [@thorne2018fever; @koreeda2021contractnli]. The
evidence returned is a verbatim sentence of the booklet, chosen after the decision without an LLM call
(idf-weighted word stems and character 5-grams against claim and translation); `--evidence-unit paragraph`
returns the whole text block instead.

**Options not in the default.** A page-window ladder for unsure verdicts (Self-Route and LLM cascades
[@li2024ragvslong; @chen2023frugalgpt]), the booklet's parallel language version instead of translation,
dense or hybrid retrieval, Apertus reranking, an 8B → 70B cascade, label calibration and number rules are
available as flags; on the development subset none of them paid for its cost (`docs/EXPERIMENTS-v1.md`).

## 3. Use of Apertus

- **Model:** swiss-ai/Apertus-v1.5-8B and swiss-ai/Apertus-v1.5-70B [@apertus2025]
- **How it is used:** inference only: the NLI verdict with evidence selection, the translation of
  cross-lingual claims and of foreign `vote` titles, and (8B) the split of unsure claims into atomic statements.
- **Where it runs:** the Hack Apertus OpenAI-compatible endpoint, selected through `LLM_NAME`,
  `LLM_BASE_URL`, `LLM_API_KEY`; temperature 0, JSON schema, `logprobs` with 10 alternatives.

Both models honour the JSON schema and return log-probabilities, so the label probability is read from
the first token of the label value. No other model takes part in the default path: retrieval is BM25 and
parsing is deterministic. Prompts are versioned (`nli-v1` … `nli-v5`, Section 5.3); the default is
`nli-v1`. Every call is cached on disk by a hash of model, messages and parameters, which makes reruns
free and reproducible.

## 4. Data

| Set | Source | Pairs | Languages | E / N / C | Use |
| --- | --- | --- | --- | --- | --- |
| v1.0 Total | `OSTswiss/MNLIoverSwissVotingBooklets` (`v1.0.jsonl`, MIT) | 1,495 | 60 booklets, 20 dates (2020–2026) | balanced | Official OST Benchmark |
| v1.0 Dev (`dev_s`) | Stratified split by voting date (13 dates, 39 booklets) | 450 (of 998) | 160 same-lang, 290 cross-lang | balanced | Ablations & prompt tuning |
| v1.0 Test | Held-out voting dates (7 dates, 21 booklets, seed 2026) | 497 | 166 same-lang, 331 cross-lang | balanced | Final evaluation (run once) |

The official OST v1.0 dataset comprises 1,495 annotated claim-booklet pairs spanning 20 federal voting dates
and 177 distinct proposals across German, French, and Italian. Crucially, 974 pairs (65.1%) are cross-lingual,
where the claim language differs from the booklet language. Splits are partitioned strictly by voting date:
DE, FR, and IT versions of the same booklet and cross-lingual variants never cross splits. The test set
was held out entirely and evaluated exactly once. Booklets are retrieved directly from official Federal Chancellery
publications. No personal data is involved.

## 5. Evaluation

**Metrics.** As on OST's slide 28: macro-F1 across entailment, neutral and contradiction with 95% bootstrap
confidence intervals (1,000 resamples), separately for the Beginner and the Advanced task and broken down by
language and by same-language vs. cross-lingual pairs; evidence against the gold section (`reference_string`)
and its page; input tokens per claim (OST sums `input_tokens`, counted by its proxy); mean and p95 of
`inference_time_ms`. We also report hit@k retrieval recall and total tokens (input + output) from API usage.

### 5.1 Main Results (Held-Out Test Set, n=497)

Settings were frozen on the dev set before this single evaluation run:

Tokens = input + output per claim; Input = input tokens only.

| Setup | 8B Macro-F1 [95% CI] | 8B Same / Cross | 8B Tokens | 8B Input | 70B Macro-F1 [95% CI] | 70B Same / Cross | 70B Tokens | 70B Input |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Baseline: Whole booklet** | 0.723 [0.684–0.760] | 0.801 / 0.685 | 20,182 | 20,156 | 0.890 [0.862–0.917] | 0.916 / 0.876 | 20,176 | 20,156 |
| **Beginner: Gold section** | 0.940 [0.917–0.961] | 0.918 / 0.950 | 2,101 | 2,080 | **0.980** [0.968–0.990] | 0.987 / 0.977 | 2,098 | 2,080 |
| **Beginner + 3 examples** | **0.978** [0.964–0.990] | 0.980 / 0.976 | 2,678 | 2,662 | – | – | – | – |
| **Advanced: BM25 whole booklet** | 0.762 | 0.943 / 0.672 | 1,387 | 1,367 | – | – | – | – |
| **Advanced: Proposal + BM25** | 0.778 | 0.943 / 0.696 | 1,333 | 1,312 | 0.819 | 0.974 / 0.741 | 1,331 | 1,312 |
| **Advanced: + Translation** (**70B default**) | 0.940 [0.919–0.959] | 0.943 / 0.938 | 1,683 | 1,636 | **0.951** [0.931–0.970] | 0.974 / 0.940 | 1,675 | 1,631 |
| **Advanced: + 3 ex. + decomp.** (**8B default**) | **0.941** [0.919–0.960] | 0.980 / 0.922 | 2,302 | 2,258 | – | – | – | – |
| Advanced: + decomp., no examples | – | – | – | – | 0.955 [0.937–0.972] | 0.974 / 0.946 | 1,709 | 1,663 |
| _Optional: Parallel version retrieval_ | 0.953 | 0.980 / 0.940 | 2,195 | 2,173 | – | – | – | – |

### 5.2 Key Findings
1. **Beating the Baseline with 90% Less Compute:** On 8B, our proposal-aware retrieval pipeline outperforms
   the whole-booklet baseline by **+0.218 macro-F1** (0.941 vs. 0.723) while reducing token usage from
   20,182 down to 2,302 tokens. On 70B, it achieves 0.951 macro-F1 with >12× fewer tokens.
2. **Cross-lingual pairs:** While the whole-booklet baseline drops sharply on cross-lingual pairs
   (from 0.801 down to 0.685 on 8B), translation by Apertus closes most of the gap
   (0.980 same-language / 0.922 cross-language on 8B; 0.974 / 0.940 on 70B).
3. **Retrieval Accuracy (hit@5):** Proposal localization reaches 0.928 hit@5 with translation (vs. 0.604
   over the entire unpartitioned booklet), providing clean, unpolluted context to Apertus.
4. **OST input and output format:** `booklint predict` reads the task cases of both tasks (nested `booklet.path`,
   `claim.text`, `reference.text`, `vote`, `id`) and prints `id`, `label`, `label_name`, `evidence`
   (page and verbatim text, required for entailment and contradiction; we return `[]` for neutral) and
   `metrics` (tokens from the API usage and measured wall time; OST measures both itself).

### 5.3 Breakdown as on OST's slide 28 (test, macro-F1)

Language = language of the claim or of the booklet (reference); n per group in the header.

| Task / model | All (497) | Claim DE (166) | Claim FR (165) | Claim IT (166) | Booklet DE (156) | Booklet FR (186) | Booklet IT (155) | Same (166) | Cross (331) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Advanced 8B | 0.941 | 0.937 | 0.939 | 0.944 | 0.923 | 0.967 | 0.927 | 0.980 | 0.922 |
| Advanced 70B | 0.951 | 0.951 | 0.951 | 0.950 | 0.936 | 0.973 | 0.942 | 0.974 | 0.940 |
| Beginner 8B (3 examples) | 0.978 | 0.956 | 0.982 | 0.994 | 0.974 | 0.983 | 0.974 | 0.980 | 0.976 |
| Beginner 70B | 0.980 | 0.963 | 0.989 | 0.988 | 0.987 | 0.989 | 0.965 | 0.987 | 0.977 |

OST's input has no language field. With the claim language detected instead of taken from the data, the
Advanced results are identical (8B 0.9406, 70B 0.9512; the detection is right on 497 of 497 test claims).

**Evidence (Advanced).** Share of entailment/contradiction answers whose first evidence item lies inside the
gold section, and whose page is a page of the gold section:

| Evidence unit | 8B in gold | 8B gold page | 8B chars (median) | 70B in gold | 70B gold page | 70B chars (median) |
| --- | --- | --- | --- | --- | --- | --- |
| Sentence (default) | 0.786 | 0.802 | 238 | 0.804 | 0.823 | 219 |
| Paragraph (text block) | 0.777 | 0.802 | 629 | 0.798 | 0.823 | 555 |

"Inside the gold section" is a strict proxy: the booklet often says the same thing twice (summary and detailed
section), and only one place is gold. In a read sample of 30 sentences (8B) 22 decide the claim, 7 partly and
1 does not. How OST matches evidence (substring, overlap, same paragraph) is not yet known, so OST's evidence
score is [TBD].

**Efficiency as OST measures it.** Cold run on 50 seeded test cases in OST's input format, without response
cache, one request at a time; `inference_time_ms` is the wall time of one case (the booklet is parsed
beforehand and cached):

| Model | Input tokens / claim | Calls / claim | `inference_time_ms` mean | p95 |
| --- | --- | --- | --- | --- |
| 8B | 2,205 | 1.72 | 457 | 819 |
| 70B | 1,630 | 1.68 | 1,366 | 2,119 |

The endpoint's own prefix cache cannot be switched off; tokens counted by OST's proxy are [TBD].

## 6. Limitations

The test split has 497 claims from 7 voting dates; at this size a macro-F1 difference below about 0.02 is
within the bootstrap interval, and the model-aware defaults (examples and decomposition only for 8B) were
chosen on 450 development claims. Topical but unsupported claims, attribution (committee vs. Federal
Council) and claims about the front-page summary remain the main error sources. The claim language is
detected (wrong on 1 of 1,495 v1.0 claims, an Italian claim quoting a German law title). Booklets without a
text layer are not handled (no OCR). Labels and evidence are an automated reading of the booklet, not a
voting recommendation, and the model's position must never be presented as the booklet's.

Open questions to OST (Q&A on 2026-10-08): whether `page` is the 1-based PDF index or the printed page
number (for federal booklets they mostly agree; not checked systematically); which page the Beginner task
expects (the reference has no pages, we return `page: 1`); how evidence is matched, which decides between
sentence and paragraph; and whether the token-counting proxy passes `response_format` and `logprobs`
through. Without them the endpoint client retries without schema and log-probabilities, the 8B decomposition
is skipped (about −0.004 macro-F1 on development data).

## 7. Reproducibility

`make run` builds the Docker image and runs the default pipeline on the test split against the endpoint in
`LLM_*`; no GPU or local weights are needed. For OST's own cases the command is
`booklint predict --case <cases.jsonl>` (Docker mounts and `BOOKLET_ROOT` in `track_2a/README.md`).
Settings: prompt `nli-v1`, k = 5, one neighbour, temperature 0, JSON schema. Every Apertus call is cached on
disk by a hash of model, messages and parameters; replaying the stored test runs from this cache with the
current code gives the same 497 labels for both models. Each run in `runs/v1/` stores its options, split seed
and command. The endpoint is not fully deterministic at temperature 0: a cold rerun of 50 cases gave the
same label on 50/50 (8B) and 49/50 (70B). Commit of the submission: [TBD].

## 8. Lessons learned

- **Narrow first, then read.** Locating the proposal by its title costs nothing and keeps 94 % of the gold
  section in a quarter of the booklet; together with translation it beats the whole booklet by +0.22 (8B)
  and +0.06 (70B) macro-F1 at 8–9 % of the input tokens. 8B with this context (0.941) beats 70B with the
  whole booklet (0.890).
- **Translation is the largest single step** for cross-lingual claims (8B cross-lingual 0.696 → 0.938);
  retrieval on the untranslated claim misses the passage.
- **Prompt rules move the boundary instead of sharpening it.** Rules for "neutral" made 8B call real
  contradictions neutral; three worked examples helped on development data but not on test for the
  Advanced task. Apertus is very confident (p > 0.9 for 94–98 % of answers), so gates on the label
  probability rarely fire, and calibration offsets were unstable.
- **Cheap evidence.** Choosing the evidence sentence deterministically after the decision costs no tokens
  and lands in the gold section more often than the whole cited passage (0.79 vs. 0.62 for 8B).
- **Measure what the judges measure.** OST sums input tokens and takes mean and p95 of time per claim on its
  own runs; our first numbers (total tokens, Apertus seconds with a warm cache) did not match that and had to
  be re-measured cold.
- **Check the input format, not the dataset.** The dataset has `claim_language` and `vote` in the booklet
  language; OST's case format has no language field and may carry a `vote` in another language. Without
  translation the proposal is then found for only 70 % of foreign titles; translating the title brings it
  to 95–98 %.

## 9. Next steps

Settle evidence unit and page numbering with OST; add OCR text for scanned booklets
[@stuessi2026votingbooklets]; judge evidence relevance on a larger sample; extend to Romansh.

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References
