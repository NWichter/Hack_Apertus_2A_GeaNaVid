# holdout-synth: synthetic hold-out set

**Synthetic data. Not part of the OST benchmark.** 90 claim/booklet pairs written by
Claude for three federal voting dates that the OST benchmark v1.0 does not cover. The
labels were cross-checked blindly by two other models (Codex CLI, NVIDIA Nemotron); the
89 rows on which generator and both judges agree form `holdout.jsonl`. No human annotated
these rows. Report numbers on this set separately and never mix them with OST benchmark
numbers. It was built after the pipeline's defaults were fixed and evaluated once
(results below); nothing was tuned on it.

## Files

| File | Content |
| --- | --- |
| `holdout.jsonl` | **the hold-out**: 89 rows on which Claude, Codex and Nemotron agree |
| `holdout-dropped.jsonl` | 1 row where a judge disagreed (`ho-009`, neutral; Nemotron: contradiction) |
| `holdout-candidates.jsonl` | all 90 rows with gold label, reference text, evidence, provenance, `judge_codex`, `judge_nemotron` |
| `judge-cases.jsonl` | Blind input for more judges: `id`, `claim`, `claim_language`, `booklet_language`, `reference_string` only |
| `booklets/` | The 9 downloaded PDFs (git-ignored, see below for the URLs) |

Scripts are in `experiments/holdout/`:

| Script | Purpose |
| --- | --- |
| `spec.py` | Hand-written claims, labels, section anchors and evidence (the generator output) |
| `pdftext.py` | PyMuPDF text extraction, line joining and the loose normalisation used for checks |
| `build_candidates.py` | Builds `holdout-candidates.jsonl` from `spec.py` and the PDFs (keeps existing `judge_*` fields) |
| `verify.py` | Checks that every `reference_string` line and every evidence text occur in the PDF (evidence on the stated page) and prints the counts |
| (not in the repository) | the blind Codex judge (a CLI agent run); its answers are stored in `judge_codex` |
| `export_judge_cases.py` | Writes `judge-cases.jsonl` |
| `run_nemotron.py` | Blind Nemotron judge on OpenRouter, writes `judge_nemotron`, `holdout.jsonl`, `holdout-dropped.jsonl` |
| `evaluate.py` | The one-time evaluation with booklint (`runs/holdout-synth/<model>/<mode>.*`) |

Rebuild: download the PDFs (URLs below) to `booklets/<date>_<lang>.pdf`, then
`python build_candidates.py && python verify.py` in `experiments/holdout/`.

## Voting dates and proposals

All three dates are absent from OST v1.0 (which covers 2020-02-09 to 2026-06-14), and none is 2018-11-25.

| Date | Proposal (DE / FR / IT as printed) | Rows |
| --- | --- | --- |
| 2019-02-10 | Volksinitiative «Zersiedelung stoppen – für eine nachhaltige Siedlungsentwicklung (Zersiedelungsinitiative)» / Initiative populaire « Stopper le mitage – pour un développement durable du milieu bâti (initiative contre le mitage) » / Iniziativa popolare «Fermare la dispersione degli insediamenti – per uno sviluppo insediativo sostenibile (Iniziativa contro la dispersione degli insediamenti)» | 30 |
| 2019-05-19 | Bundesgesetz über die Steuerreform und die AHV-Finanzierung (STAF) / Loi fédérale relative à la réforme fiscale et au financement de l’AVS (RFFA) / Legge federale concernente la riforma fiscale e il finanziamento dell’AVS (RFFA) | 15 |
| 2019-05-19 | Umsetzung einer Änderung der EU-Waffenrichtlinie (Weiterentwicklung von Schengen) / Mise en œuvre d’une modification de la directive de l’UE sur les armes (Développement de l’acquis de Schengen) / Trasposizione nel diritto svizzero di una modifica della direttiva UE sulle armi (Sviluppo di Schengen) | 15 |
| 2018-06-10 | Volksinitiative «Für krisensicheres Geld: Geldschöpfung allein durch die Nationalbank! (Vollgeld-Initiative)» / Initiative populaire « Pour une monnaie à l’abri des crises : émission monétaire uniquement par la Banque nationale ! (Initiative Monnaie pleine) » / Iniziativa popolare «Per soldi a prova di crisi: emissione di moneta riservata alla Banca nazionale! (Iniziativa Moneta intera)» | 15 |
| 2018-06-10 | Bundesgesetz über Geldspiele (Geldspielgesetz) / Loi fédérale sur les jeux d’argent / Legge federale sui giochi in denaro | 15 |

## Counts

| | entailment | neutral | contradiction | total |
| --- | --- | --- | --- | --- |
| all rows | 30 | 30 | 30 | 90 |
| `holdout.jsonl` | 30 | 29 | 30 | 89 |

- Booklet language: DE 30, FR 30, IT 30. Each booklet (date × language) has 10 rows.
- Claim language: DE 30, FR 30, IT 30. No Romansh.
- Same language (claim = booklet): 30. Cross-lingual: 60, 10 for each of the six pairs
  (de→fr, de→it, fr→de, fr→it, it→de, it→fr; claim language → booklet language).

## Row format

| Field | Meaning |
| --- | --- |
| `id` | `ho-001` … `ho-090` |
| `claim`, `claim_language` | Claim and its language (`de`, `fr`, `it`) |
| `booklet_language`, `booklet_date` | Language and voting date of the booklet the claim is checked against |
| `booklet_path` | PDF path relative to `track_2a/` |
| `booklet_url` | Source URL of the PDF |
| `vote` | Proposal title as printed in that language version |
| `entailment_label`, `label_name` | 0 = entailment, 1 = neutral, 2 = contradiction (as in OST v1.0) |
| `reference_string` | Proposal title, a blank block, then the verbatim booklet section the claim was written from (summary, details, committee arguments, Federal Council arguments or legal text). One line per page part |
| `evidence` | List of `{page, text}`: 1-based PDF page and a verbatim sentence or clause. Required for entailment and contradiction, empty for neutral |
| `provenance` | `generator` = `claude`, `generator_model`, `generated_at`, `prompt_version` = `holdout-v1` |
| `judge_codex` | `{model, label, label_name, reason}` from the blind Codex pass |

Label rules follow OST v1.0: neutral claims are on topic but not answerable from the
reference (invented but plausible numbers, actors or facts); contradictions change a
number, actor, direction or recommendation, or negate the reference.

## Text checks

`verify.py` compares texts after a loose normalisation (Unicode NFKC, all whitespace,
hyphens and soft hyphens removed, typographic apostrophes unified), because the PDF text
layers split words at line ends. Every evidence text is checked on its stated page, and
every line of every `reference_string` against the full PDF text. Current result: 0 errors.

The reference strings are taken from the PyMuPDF text layer and keep some of its
artefacts, mainly in the 2018-06-10 German booklet (for example `abzu lehnen`,
`VollgeldInitiative`), where the soft hyphens are lost in the text layer.

## Judges

- **Codex** (`judge_codex`): `codex exec -s read-only` run from an empty temporary folder,
  10 cases per call. The prompt contains only claim and `reference_string`, no label and
  no evidence (an empty evidence list would reveal "neutral"; the evidence is part of
  `reference_string` anyway). Model `gpt-6.1-sol` (Codex CLI 0.160.0, reasoning effort medium), run 2026-10-04: raw agreement with the gold labels 90/90 (100 %). A perfect score from a strong model on self-written claims mostly shows that the labels are unambiguous to that model; it is not a measure of difficulty.
- **Nemotron** (`judge_nemotron`): `nvidia/nemotron-3.5-lightning:free` on OpenRouter (open weights), temperature 0,
  one case per call, same blind input (claim and `reference_string`). Agreement 89/90; the one disagreement
  (`ho-009`, gold neutral, Nemotron contradiction) was dropped, not fixed.

The model under test (Apertus) was not used for generation or judging.

## Sources

Collection page: <https://www.bk.admin.ch/de/sammlung-der-abstimmungsbuechlein-seit-1978>
(Federal Chancellery, "Erläuterungen des Bundesrates"). Downloaded on 2026-10-04.

| Date | Language | URL |
| --- | --- | --- |
| 2019-02-10 | de | https://www.bk.admin.ch/dam/de/sd-web/feT3z55YdiNa/2019-02-10_erlaeuterungen_des_bundesrates.pdf |
| 2019-02-10 | fr | https://www.bk.admin.ch/dam/fr/sd-web/feT3z55YdiNa/2019-02-10_explications_du_conseil_federal.pdf |
| 2019-02-10 | it | https://www.bk.admin.ch/dam/it/sd-web/feT3z55YdiNa/2019-02-10_spiegazioni_del_consiglio_federale.pdf |
| 2019-05-19 | de | https://www.bk.admin.ch/dam/de/sd-web/JidqjDWbXbrM/2019-05-19_erlaeuterungen_des_bundesrates.pdf |
| 2019-05-19 | fr | https://www.bk.admin.ch/dam/fr/sd-web/JidqjDWbXbrM/2019-05-19_explications_du_conseil_federal.pdf |
| 2019-05-19 | it | https://www.bk.admin.ch/dam/it/sd-web/JidqjDWbXbrM/2019-05-19_spiegazioni_del_consiglio_federale.pdf |
| 2018-06-10 | de | https://www.bk.admin.ch/dam/de/sd-web/WBiy0Vj6fgqY/2018-06-10_erlaeuterungen_des_bundesrates.pdf |
| 2018-06-10 | fr | https://www.bk.admin.ch/dam/fr/sd-web/WBiy0Vj6fgqY/2018-06-10_explications_du_conseil_federal.pdf |
| 2018-06-10 | it | https://www.bk.admin.ch/dam/it/sd-web/WBiy0Vj6fgqY/2018-06-10_spiegazioni_del_consiglio_federale.pdf |

The German links come from the collection page. The French and Italian links use the
same document id with the language path and file name pattern of the OST v1.0 URLs; all
nine returned `application/pdf`, and the first page of each PDF is in the expected
language. All nine PDFs have a text layer (PyMuPDF).

## Terms of use

What we found (2026-10-04), without legal assessment:

- The PDFs carry no licence statement. The back page only says "Herausgegeben von der
  Bundeskanzlei" (published by the Federal Chancellery).
- The collection page links to the federal legal notice
  <https://www.admin.ch/gov/de/start/rechtliches.html>. Its "Copyright" section says:
  copyright of the federal authorities; the information is made available to the public;
  downloading or copying transfers no rights; reproduction of any element requires prior
  written consent of the copyright holders.
- The Federal Chancellery imprint page (<https://www.bk.admin.ch/de/impressum>) is rendered
  by JavaScript and returned no terms text to a plain HTTP request.

Consequences here: the PDFs are not committed (`booklets/` is git-ignored); the data
files contain the URLs plus the verbatim excerpts in `reference_string` and `evidence`,
in the same way as OST v1.0. Decision (14 October): the excerpts are published as official texts in the sense of
Art. 5 URG (not protected by copyright); see `LICENSE`.

## Licence

The whole folder is licensed under CDLA-Permissive-2.0 (text and notes in [`LICENSE`](LICENSE)). The booklet
excerpts in `reference_string` and `evidence` are official texts in the sense of Art. 5 URG and are included as such.
The scripts in `experiments/holdout/` fall under the repository's Apache-2.0 licence.

## Results (evaluated once, 2026-10-04)

`python experiments/holdout/evaluate.py --model <m> --mode retrieval|baseline|easy`; the claim language is detected,
the booklet is the local PDF. Evidence: first evidence sentence inside the reference section; on a page of the
generator's evidence. Calls to Apertus: 679.

| model | task | macro-F1 [95 % CI] | same / cross | evidence in reference (page) | input tokens | time mean / p95 |
| --- | --- | --- | --- | --- | --- | --- |
| 8B | whole booklet (baseline) | 0.665 [0.561–0.753] | 0.662 / 0.666 | 0.826 (0.848) | 25,414 | 4,428 / 6,834 ms |
| 8B | Advanced (default) | **0.845** [0.764–0.919] | 0.928 / 0.807 | 0.782 (0.800) | 2,217 | 1,402 / 5,147 ms |
| 8B | Beginner (reference given) | 0.855 [0.781–0.923] | 0.887 / 0.840 | 1.000 | 1,427 | 778 / 3,545 ms |
| 70B | whole booklet (baseline) | 0.872 [0.800–0.939] | 0.930 / 0.844 | 0.754 (0.754) | 22,522 | 2,515 / 7,187 ms |
| 70B | Advanced (default) | **0.932** [0.872–0.978] | 0.965 / 0.917 | 0.807 (0.842) | 1,546 | 1,871 / 2,992 ms |
| 70B | Beginner (reference given) | 0.931 [0.876–0.978] | 0.928 / 0.932 | 1.000 | 845 | 799 / 899 ms |

Times are wall time per claim with 4 parallel requests and a warm endpoint, not a cold run. One 8B baseline answer
(`ho-033`) was not valid JSON and counted as neutral; the parser now falls back to the label word.
