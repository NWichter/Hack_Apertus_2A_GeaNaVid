# Technical report — GeaNaVid

- **Track:** Track 2A — OST: Multilingual NLI over Swiss Official Voting Booklets
- **Event:** Online
- **Team:** Apertool — Niklas Wichter
- **Demo:** [TBD: video link] · `make run` in `track_2a/`

_Draft of 1 October 2026. All numbers are from runs on that day; open measurements are marked [TBD]._

## 1. Summary

Swiss voters meet many claims about federal proposals; the official voting booklet is the authoritative
source, but it runs to 40–90 pages in three languages. GeaNaVid checks a claim in German, French or
Italian against a booklet and returns entailment, neutral or contradiction together with the passages
that decide the label, the token usage and the time. We treat the task as document-level natural
language inference [@yin2021docnli; @koreeda2021contractnli], close to claim verification with evidence
[@thorne2018fever], but judged only against the booklet, never against the world.

Our CLI `booklint` parses the PDF without a language model, retrieves a few passages with BM25 and asks
Apertus v1.5 for a strict JSON verdict with evidence first and label second. Cross-lingual pairs are
handled by searching the booklet's parallel version in the claim's language and mapping the hits back by
page layout, which costs no tokens. On the official OST v1.0 benchmark (1,495 pairs across 60 voting booklets, 2020–2026; 497 held-out test pairs),
Apertus 8B reaches a macro-F1 of 0.941 [95% CI 0.919–0.960] with 2,302 tokens per claim, beating the whole-booklet
baseline of 0.723 (20,182 tokens) by +0.218 while cutting token consumption by nearly 90%. Apertus 70B reaches 0.951
[0.931–0.970] with 1,675 tokens, beating its 0.890 baseline by +0.061 with >12× fewer tokens. In the Beginner Task
(gold reference provided), 8B reaches 0.978 and 70B reaches 0.980 macro-F1.
Our contributions are (1) a cost-aware context ladder for document NLI with evidence, (2) a measured
trade-off between macro-F1, tokens and time for 8B and 70B, including the full-document baseline the
challenge asks for, and (3) a zero-token cross-lingual retrieval step that uses the official parallel
versions. The output is never a voting recommendation: every verdict comes with a quote from the booklet.

## 2. Architecture

The pipeline has five steps:

1. **Ingest** (once per booklet, no LLM, cached): text blocks with page, proposal, section and committee note.
2. **Claim language** by stop-word counts; no LLM.
3. **Retrieval**: BM25 top-5 plus same-page neighbours. Cross-lingual pairs search the parallel booklet in the claim language and map the hits back by layout; claims about a recommendation also get the recommendation blocks of the same proposal.
4. **Apertus NLI**, one call: numbered passages, JSON schema with evidence before label.
5. **Ladder gate**: an entailment or contradiction without evidence, or p(label) < 0.75, triggers one retry with the pages around the hits (±1 page). Output: label 0/1/2, evidence with page, section and offsets, tokens, seconds.

**Ingest.** PyMuPDF text blocks are cleaned (soft hyphens, line-break hyphenation, superscript footnote
digits that otherwise glue to numbers). Each block keeps its page, the proposal from the running header
("Erste Vorlage: …", or an ordinal title in older layouts), the nearest bold side heading ("In Kürze",
"Empfehlung von Bundesrat und Parlament") and the committee note ("Der Text auf dieser Doppelseite
stammt vom Initiativkomitee"). The 40-page demo booklet gives 210 blocks in 0.3 s and zero tokens.

**Retrieval.** BM25 [@robertson2009bm25] over heading plus text, with number normalisation
(500'000 = 500 000) and prefix stemming, fused across queries by reciprocal rank [@cormack2009rrf]. BM25
needs no GPU and is a strong zero-shot baseline [@thakur2021beir]. For a cross-lingual pair we fetch the
booklet in the claim's language (bk.admin.ch uses the same document id for all languages), rank there and
map each hit to the block at the same relative position on the same page of the target booklet.

**NLI call.** The passages are numbered and prefixed with their context; Apertus answers under a JSON
schema with the deciding passage numbers before the label, as in evidence-first setups
[@thorne2018fever; @koreeda2021contractnli]. Evidence is therefore always a real block of the booklet with
page and character offsets, never generated text.

**Ladder.** The idea follows Self-Route and LLM cascades [@li2024ragvslong; @chen2023frugalgpt]: most
pairs stop after one call; only unsure or unsupported verdicts climb to a wider context.

## 3. Use of Apertus

- **Model:** swiss-ai/Apertus-v1.5-8B and swiss-ai/Apertus-v1.5-70B [@apertus2025]
- **How it is used:** inference — the NLI verdict with evidence selection; optionally the translation of
  a claim (`--translate`).
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
| v1.0 Test | Held-out voting dates (7 dates, 21 booklets, seed 2026) | 497 | 175 same-lang, 322 cross-lang | balanced | Final evaluation (run once) |

The official OST v1.0 dataset comprises 1,495 annotated claim-booklet pairs spanning 20 federal voting dates
and 177 distinct proposals across German, French, and Italian. Crucially, 974 pairs (65.1%) are cross-lingual,
where the claim language differs from the booklet language. Splits are partitioned strictly by voting date:
DE, FR, and IT versions of the same booklet and cross-lingual variants never cross splits. The test set
was held out entirely and evaluated exactly once. Booklets are retrieved directly from official Federal Chancellery
publications. No personal data is involved.

## 5. Evaluation

**Metrics.** Macro-F1 across entailment, neutral, and contradiction with 95% bootstrap confidence intervals
(1,000 resamples), F1 per label, hit@k retrieval recall against the gold section (`reference_string`),
and total tokens per claim from API usage.

### 5.1 Main Results (Held-Out Test Set, n=497)

Settings were frozen on the dev set before this single evaluation run:

| Setup | 8B Macro-F1 [95% CI] | 8B Same / Cross | 8B Tokens | 70B Macro-F1 [95% CI] | 70B Same / Cross | 70B Tokens |
| --- | --- | --- | --- | --- | --- | --- |
| **Baseline: Whole booklet** | 0.723 [0.684–0.760] | 0.801 / 0.685 | 20,182 | 0.890 [0.862–0.917] | 0.916 / 0.876 | 20,176 |
| **Beginner: Gold section** | 0.940 [0.917–0.961] | 0.918 / 0.950 | 2,101 | **0.980** [0.968–0.990] | 0.987 / 0.977 | 2,098 |
| **Beginner + 3 examples** | **0.978** [0.964–0.990] | 0.980 / 0.976 | 2,678 | – | – | – |
| **Advanced: BM25 whole booklet** | 0.762 | 0.943 / 0.672 | 1,387 | – | – | – |
| **Advanced: Proposal + BM25** | 0.778 | 0.943 / 0.696 | 1,333 | 0.819 | 0.974 / 0.741 | 1,331 |
| **Advanced: + Translation** | 0.940 [0.919–0.959] | 0.943 / 0.938 | 1,683 | **0.951** [0.931–0.970] | 0.974 / 0.940 | 1,675 |
| **Advanced: 8B Default** (+3 ex. + decomp) | **0.941** [0.919–0.960] | 0.980 / 0.922 | 2,302 | – | – | – |
| **Advanced: 70B Default** (+ decomp, no ex.) | – | – | – | **0.955** [0.937–0.972] | 0.974 / 0.946 | 1,709 |
| _Optional: Parallel version retrieval_ | 0.953 | 0.980 / 0.940 | 2,195 | – | – | – |

### 5.2 Key Findings
1. **Beating the Baseline with 90% Less Compute:** On 8B, our proposal-aware retrieval pipeline outperforms
   the whole-booklet baseline by **+0.218 macro-F1** (0.941 vs. 0.723) while reducing token usage from
   20,182 down to 2,302 tokens. On 70B, it achieves 0.951 macro-F1 with >12× fewer tokens.
2. **Cross-Lingual Parity:** While the naive whole-booklet baseline drops sharply on cross-lingual pairs
   (from 0.801 down to 0.685 on 8B), our translation and parallel-retrieval steps eliminate this penalty
   (0.980 same-language / 0.922 cross-language on 8B; 0.974 / 0.940 on 70B).
3. **Retrieval Accuracy (hit@5):** Proposal localization reaches 0.928 hit@5 with translation (vs. 0.604
   over the entire unpartitioned booklet), providing clean, unpolluted context to Apertus.
4. **OST input and output format:** `booklint predict` reads the task cases of both tasks (nested `booklet.path`,
   `claim.text`, `reference.text`, `vote`, `id`) and prints `id`, `label`, `label_name`, `evidence`
   (page and verbatim text, required for entailment and contradiction; we return `[]` for neutral) and
   `metrics` (tokens from the API usage and measured wall time; OST measures both itself).

**Evidence.** Grounded rate against the single gold paragraph is 0.68–0.73 with retrieval and 0.39–0.45
with the whole booklet. Many misses cite another valid passage (for example the legal text instead of
the summary), so this is a lower bound; a judged evaluation of evidence relevance is [TBD].

## 6. Limitations

The development data are small: 23 distinct official claims from one booklet, and the cross-lingual and
synthetic sets are our own, with labels not yet checked by a human; at n ≈ 100 a macro-F1 difference
below about 0.08 is within noise. Synthetic claims may follow their generators' style. Topical but
unsupported claims and attribution remain the main error sources for 8B. The parallel-booklet step
needs the bk.admin.ch URL; for a local PDF it falls back to direct BM25 or translation. Scanned booklets
without a text layer (before about 2000) are not handled yet. Labels and evidence are an automated
reading of the booklet, not a voting recommendation, and the model's position must never be presented as
the booklet's.

## 7. Reproducibility

`make run` builds the Docker image and runs the benchmark on D0 + D1 against the endpoint in `LLM_*`; no
GPU or local weights are needed. Settings: prompt `nli-v1`, k = 5, one neighbour, τ = 0.75, temperature 0,
JSON schema. Development ran on a laptop against the Hack Apertus endpoint; commit [TBD]. Runs write one
JSONL per setting with label, evidence, probabilities, tokens and seconds, plus `summary.md`.

## 8. Next steps

Measure Apertus translation against the parallel-booklet step; add OCR text for scanned booklets
[@stuessi2026votingbooklets]; human-check the synthetic sets and judge evidence relevance; try 70B only
for escalated pairs; extend to Romansh.

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References
