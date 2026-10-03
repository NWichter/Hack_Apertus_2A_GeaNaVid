- #strong[Track:] Track 2A --- OST: Multilingual NLI over Swiss Official
  Voting Booklets
- #strong[Event:] Online
- #strong[Team:] Apertool --- Niklas Wichter
- #strong[Demo:] \[TBD: video link\] · `make run` in `track_2a/`

#emph[Draft of 1 October 2026. All numbers are from runs on that day;
open measurements are marked \[TBD\].]

= 1. Summary
<summary>
Swiss voters meet many claims about federal proposals; the official
voting booklet is the authoritative source, but it runs to 40--90 pages
in three languages. GeaNaVid checks a claim in German, French or Italian
against a booklet and returns entailment, neutral or contradiction
together with the passages that decide the label, the token usage and
the time. We treat the task as document-level natural language inference
@yin2021docnli@koreeda2021contractnli, close to claim verification with
evidence @thorne2018fever, but judged only against the booklet, never
against the world.

Our CLI `booklint` parses the PDF without a language model, retrieves a
few passages with BM25 and asks Apertus v1.5 for a strict JSON verdict
with evidence first and label second. Cross-lingual pairs are handled by
searching the booklet's parallel version in the claim's language and
mapping the hits back by page layout, which costs no tokens. On the
official demo and its cross-lingual variants (74 pairs), Apertus 8B
reaches a macro-F1 of 0.92 with about 2,200 input tokens per pair,
against 0.81 with the whole booklet (18,200 tokens); Apertus 70B reaches
0.96 with retrieval and 0.98 with the whole booklet. On held-out
synthetic claims for four longer booklets (40,000 tokens on average),
the whole-booklet baseline drops to 0.60 (8B) and 0.85 (70B), while the
ladder keeps 0.88 and 0.94 with 1,700--1,900 tokens. Our contributions
are (1) a cost-aware context ladder for document NLI with evidence, (2)
a measured trade-off between macro-F1, tokens and time for 8B and 70B,
including the full-document baseline the challenge asks for, and (3) a
zero-token cross-lingual retrieval step that uses the official parallel
versions. The output is never a voting recommendation: every verdict
comes with a quote from the booklet.

= 2. Architecture
<architecture>
The pipeline has five steps:

+ #strong[Ingest] (once per booklet, no LLM, cached): text blocks with
  page, proposal, section and committee note.
+ #strong[Claim language] by stop-word counts; no LLM.
+ #strong[Retrieval]: BM25 top-5 plus same-page neighbours.
  Cross-lingual pairs search the parallel booklet in the claim language
  and map the hits back by layout; claims about a recommendation also
  get the recommendation blocks of the same proposal.
+ #strong[Apertus NLI], one call: numbered passages, JSON schema with
  evidence before label.
+ #strong[Ladder gate]: an entailment or contradiction without evidence,
  or p(label) \< 0.75, triggers one retry with the pages around the hits
  (±1 page). Output: label 0/1/2, evidence with page, section and
  offsets, tokens, seconds.

#strong[Ingest.] PyMuPDF text blocks are cleaned (soft hyphens,
line-break hyphenation, superscript footnote digits that otherwise glue
to numbers). Each block keeps its page, the proposal from the running
header ("Erste Vorlage: …", or an ordinal title in older layouts), the
nearest bold side heading ("In Kürze", "Empfehlung von Bundesrat und
Parlament") and the committee note ("Der Text auf dieser Doppelseite
stammt vom Initiativkomitee"). The 40-page demo booklet gives 210 blocks
in 0.3 s and zero tokens.

#strong[Retrieval.] BM25 @robertson2009bm25 over heading plus text, with
number normalisation (500'000 = 500 000) and prefix stemming, fused
across queries by reciprocal rank @cormack2009rrf. BM25 needs no GPU and
is a strong zero-shot baseline @thakur2021beir. For a cross-lingual pair
we fetch the booklet in the claim's language (bk.admin.ch uses the same
document id for all languages), rank there and map each hit to the block
at the same relative position on the same page of the target booklet.

#strong[NLI call.] The passages are numbered and prefixed with their
context; Apertus answers under a JSON schema with the deciding passage
numbers before the label, as in evidence-first setups
@thorne2018fever@koreeda2021contractnli. Evidence is therefore always a
real block of the booklet with page and character offsets, never
generated text.

#strong[Ladder.] The idea follows Self-Route and LLM cascades
@li2024ragvslong@chen2023frugalgpt: most pairs stop after one call; only
unsure or unsupported verdicts climb to a wider context.

= 3. Use of Apertus
<use-of-apertus>
- #strong[Model:] swiss-ai/Apertus-v1.5-8B and swiss-ai/Apertus-v1.5-70B
  @apertus2025
- #strong[How it is used:] inference --- the NLI verdict with evidence
  selection; optionally the translation of a claim (`--translate`).
- #strong[Where it runs:] the Hack Apertus OpenAI-compatible endpoint,
  selected through `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY`\;
  temperature 0, JSON schema, `logprobs` with 10 alternatives.

Both models honour the JSON schema and return log-probabilities, so the
label probability is read from the first token of the label value. No
other model takes part in the default path: retrieval is BM25 and
parsing is deterministic. Prompts are versioned (`nli-v1` … `nli-v5`,
Section 5.3); the default is `nli-v1`. Every call is cached on disk by a
hash of model, messages and parameters, which makes reruns free and
reproducible.

= 4. Data
<data>
#figure(
  align(center)[#table(
    columns: (14.79%, 42.25%, 3.52%, 13.38%, 8.45%, 17.61%),
    align: (auto,auto,auto,auto,auto,auto,),
    table.header([Set], [Source], [Pairs], [Languages], [E / N /
      C], [Use],),
    table.hline(),
    [D0 demo], [`OSTswiss/MNLIoverSwissVotingBooklets`, commit 43f8aa3
    (MIT)], [28], [de-de, fr-fr, it-it], [17 / 4 / 7], [sanity,
    headline],
    [D1 demo cross-lingual], [D0 claims against the other two language
    versions], [46], [6 cross pairs], [26 / 8 / 12], [cross-lingual],
    [D2 syn\_dev], [synthetic, 5 vote dates], [132], [same
    language], [44 / 40 / 48], [prompt and setting choice],
    [D2 syn\_test], [synthetic, 4 other vote dates], [101], [same
    language], [36 / 33 / 32], [held out],
    [D2 syn\_x\_test], [syn\_test claims against other language
    versions], [120], [cross], [39 / 39 / 42], [held out],
  )]
  , kind: table
  )

The official demo has only 23 distinct claims from one booklet and no
cross-lingual pairs. D1 carries the labels over to the official parallel
versions and maps the gold evidence by page layout. D2 was generated for
nine other votes (2009--2026) by two other LLMs (Claude and GPT-5.5 via
the Codex CLI), each batch cross-reviewed by the other model; rows the
review flagged were dropped. Apertus never generated or reviewed data.
Generated claims cover hard cases on purpose: topical but unsupported,
numbers and dates, attribution, negation, modality, recommendations
@nie2020anli@schuster2021vitaminc. Every row carries generator, model,
date and prompt version; all rows still await a human check. The
booklets are official publications of the Federal Chancellery; they are
downloaded at run time and not stored in the repository. No personal
data is involved.

= 5. Evaluation
<evaluation>
#strong[Metrics.] Macro-F1 over E/N/C with a 95 % bootstrap interval
(1,000 resamples), F1 per class, retrieval recall (any retrieved block
fuzzily inside the gold paragraph), grounded rate (correct E/C label and
a cited block inside the gold paragraph), prompt tokens per pair from
the API `usage`, LLM calls and seconds per pair.

== 5.1 Context versus macro-F1 (D0 + D1, 74 pairs)
<context-versus-macro-f1-d0-d1-74-pairs>
#figure(
  align(center)[#table(
    columns: (36.17%, 21.28%, 21.28%, 21.28%),
    align: (auto,auto,auto,auto,),
    table.header([Setup], [8B macro-F1], [70B macro-F1], [Prompt tokens
      \/ pair],),
    table.hline(),
    [claim only (no booklet)], [0.09], [0.09], [331],
    [gold paragraph (oracle)], [0.94], [0.98], [991],
    [retrieval, top-5 + neighbours], [0.89], [0.96], [1,690],
    [retrieval + recommendation routing], [0.91], [0.96], [1,717],
    [ladder + routing (default)], [#strong[0.92] \[0.84--0.98\]], [0.94
    \[0.88--0.99\]], [2,052--2,159],
    [whole booklet], [0.81 \[0.70--0.91\]], [#strong[0.98]
    \[0.92--1.00\]], [18,229],
  )]
  , kind: table
  )

The claim-only run predicts almost always neutral, so the claims carry
no obvious label artefacts @gururangan2018annotation. For 8B, the whole
booklet is worse than 9 % of it: retrieval removes distractors that the
small model cannot ignore, in line with position effects in long
contexts @liu2024lost. For 70B the gap is 0.01--0.04 at a tenth of the
tokens. Median latency per pair with retrieval is 0.34 s (8B) and 1.07 s
(70B). Whole-booklet calls were not much slower (0.45 s and 0.86 s),
probably because the endpoint caches the shared booklet prefix; we
report this rather than claim a speed-up.

== 5.2 Cross-lingual retrieval (no LLM)
<cross-lingual-retrieval-no-llm>
#figure(
  align(center)[#table(
    columns: (62.96%, 13.58%, 23.46%),
    align: (auto,auto,auto,),
    table.header([Retrieval], [D1 recall\@5], [syn\_x\_test recall\@5],),
    table.hline(),
    [BM25 on the target booklet with the original
    claim], [0.74], [0.42],
    [BM25 in the parallel booklet, mapped back by
    layout], [#strong[0.95]], [#strong[0.88]],
    [same-language reference (D0 / syn\_dev)], [0.96], [0.97],
  )]
  , kind: table
  )

The gold evidence of D1 and syn\_x\_test was itself mapped by layout,
which favours the mapping; a comparison with Apertus translation of the
claim @artetxe2023revisiting is \[TBD\].

== 5.3 Harder synthetic cases and prompt variants (syn\_dev, 132 pairs, 8B)
<harder-synthetic-cases-and-prompt-variants-syn_dev-132-pairs-8b>
#figure(
  align(center)[#table(
    columns: (6.25%, 75%, 9.38%, 9.38%),
    align: (auto,auto,auto,auto,),
    table.header([Prompt], [Change], [Retrieval], [Ladder],),
    table.hline(),
    [nli-v1], [label definitions, attribution
    check], [#strong[0.873]], [#strong[0.896]],
    [nli-v2], ["a missing detail is neutral", stricter
    attribution], [0.840], [0.862],
    [nli-v4], [v1 + booklet conventions (Federal Council and Parliament,
    "voting text")], [0.858], [0.872],
    [nli-v5], [v4 + one-sentence check before the
    label], [0.845], [0.878],
  )]
  , kind: table
  )

With 70B and nli-v1 the same set gives 0.963 (oracle), 0.933 (retrieval)
and 0.948 (ladder). The ladder helps on hard cases (+0.02 for both
models). None of the prompt variants beats v1; v2 moved true
contradictions (numbers, negations) to neutral. Calibrating a neutral
bias on the label log-probabilities @zhao2021calibrate did not help
either: more than 90 % of the answers have p(label) \> 0.9, so the
probability gate fires for only about 2 % of pairs and the ladder mostly
escalates verdicts without evidence.

== 5.4 Held-out synthetic test
<held-out-synthetic-test>
Settings were frozen on syn\_dev before these runs; each held-out set
was run once.

#figure(
  align(center)[#table(
    columns: (20%, 20%, 20%, 20%, 20%),
    align: (auto,auto,auto,auto,auto,),
    table.header([Set], [Setup], [Prompt tokens / pair], [8B], [70B],),
    table.hline(),
    [syn\_test (101)], [gold paragraph (oracle)], [484], [0.940
    \[0.89--0.98\]], [0.930 \[0.87--0.97\]],
    [syn\_test (101)], [retrieval], [1,446], [0.881
    \[0.81--0.94\]], [0.931 \[0.88--0.97\]],
    [syn\_test (101)], [ladder], [1,715--1,856], [0.882
    \[0.81--0.94\]], [#strong[0.941] \[0.89--0.98\]],
    [syn\_test (101)], [whole booklet], [40,149 (p95 69,689)], [0.604
    \[0.50--0.70\]], [0.847 \[0.77--0.91\]],
    [syn\_x\_test (120)], [gold paragraph (oracle)], [488], [0.851
    \[0.79--0.91\]], [0.859 \[0.79--0.92\]],
    [syn\_x\_test (120)], [retrieval], [1,413], [#strong[0.857]
    \[0.79--0.92\]], [#strong[0.899] \[0.84--0.95\]],
    [syn\_x\_test (120)], [ladder], [1,807--1,832], [0.854
    \[0.78--0.91\]], [0.882 \[0.82--0.93\]],
  )]
  , kind: table
  )

The held-out booklets (2010, 2016, 2020, 2025) are longer than the demo,
with up to five proposals. Here the whole-booklet baseline breaks down:
8B falls to 0.60 and 70B to 0.85, while retrieval and the ladder keep
0.88 and 0.93--0.94 with 4 % of the tokens. Retrieval stays within 0.06
(8B) and 0.01 (70B) of the gold paragraph. Whole-booklet latency for 70B
rises to 2.8 s median and 16 s at p95, against 0.9 s for the ladder.
Cross-lingual pairs cost 0.02--0.06 macro-F1 against the same claims in
their own language. That the oracle is not better than retrieval there
points to the layout-mapped gold paragraphs of this set being noisy. The
ladder helps 8B on syn\_dev and 70B on syn\_test, but not on the
cross-lingual set; with 70B, escalation sometimes turns a correct
verdict into a wrong one.

#strong[Error analysis (8B, syn\_dev, retrieval).] Of 17 errors, 6 are
topical but unsupported claims judged as contradiction (a figure the
booklet never gives), 5 are attribution errors (the committee says X,
the Federal Council the opposite, and the model follows the committee
text), 3 are number contradictions judged as entailment. On the demo, 8B
misread a paraphrased legal threshold ("nine and a half million") as a
contradiction in three language versions of the same claim.

#strong[Evidence.] Grounded rate against the single gold paragraph is
0.68--0.73 with retrieval and 0.39--0.45 with the whole booklet. Many
misses cite another valid passage (for example the legal text instead of
the summary), so this is a lower bound; a judged evaluation of evidence
relevance is \[TBD\].

= 6. Limitations
<limitations>
The development data are small: 23 distinct official claims from one
booklet, and the cross-lingual and synthetic sets are our own, with
labels not yet checked by a human; at n ≈ 100 a macro-F1 difference
below about 0.08 is within noise. Synthetic claims may follow their
generators' style. Topical but unsupported claims and attribution remain
the main error sources for 8B. The parallel-booklet step needs the
bk.admin.ch URL; for a local PDF it falls back to direct BM25 or
translation. Scanned booklets without a text layer (before about 2000)
are not handled yet. Labels and evidence are an automated reading of the
booklet, not a voting recommendation, and the model's position must
never be presented as the booklet's.

= 7. Reproducibility
<reproducibility>
`make run` builds the Docker image and runs the benchmark on D0 + D1
against the endpoint in `LLM_*`\; no GPU or local weights are needed.
Settings: prompt `nli-v1`, k = 5, one neighbour, τ = 0.75, temperature
0, JSON schema. Development ran on a laptop against the Hack Apertus
endpoint; commit \[TBD\]. Runs write one JSONL per setting with label,
evidence, probabilities, tokens and seconds, plus `summary.md`.

= 8. Next steps
<next-steps>
Measure Apertus translation against the parallel-booklet step; add OCR
text for scanned booklets @stuessi2026votingbooklets\; human-check the
synthetic sets and judge evidence relevance; try 70B only for escalated
pairs; extend to Romansh.

= License
<license>
Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects
are open-sourced.

= References
<references>
