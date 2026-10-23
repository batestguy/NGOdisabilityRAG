---
paths:
  - "src/retrieve.py"
  - "src/rag.py"
  - "src/chunk.py"
  - "src/load.py"
  - "src/chat.py"
  - "data/processed/**"
  - "data/eval/**"
  - "scripts/**/*.py"
---

# Retrieval, corpus and eval — the silent-damage rules

Moved from root `CLAUDE.md` by H8c (2026-10-22). The dated history behind each rule is in
`docs/history/claude_md_2026-10-22.md`, `docs/phases/12_corpus_v2.md`, `13_retrieval_quality.md`,
`14_generation_eval.md`, `15_phase_f_reexamined.md` and `16_post_launch_roadmap.md`.

## Corpus

- `doc_id ∈ {act2018, constitution1999, factsheet2020}` on v1/v2; corpus v3 (H8a.2, not shipping) appends `accessregs2023`
  (`[Regs reg. N]`, `[Regs general]`); every `Chunk`/`Hit` carries `(doc_id, ref)`
  and `cite_tag()` (`src/retrieve.py`) is the only place tags are built. The doc list is hard-coded in
  more places than that (`retrieve.DOC_IDS`, `scripts/evalset.py` `DOC_IDS`, `rag.CITE_TAG_RE`,
  `verify_citations`' `doc_of`, the prompt's rule 1, `test_phase05.tag_re`): see
  `docs/phases/17_h8_corpus_expansion.md` F1–F10 before adding a document.
- Chunk sizes are pinned by Phase 01 measurement: Act section-aware 800, Constitution chapter-aware
  400, Factsheet recursive 500/50.
- **`CORPUS_VERSION = "v2"`** (`src/rag.py`). v1 is retired as the default but **not deleted**: every
  harness takes `--corpus=v1` and reproduces its published numbers from the same commit. Keep it that
  way for any future version.
- **"Act section-aware 800" is misleading.** `chunk.SECTION_RE` matches only 4 times in the cleaned
  Act, all at 89.8%+ of the document, so v1's Act split is effectively `recursive_split(text, 800)`.
  Not a bug: it is the byte-identical v1 path every v1 baseline depends on. v2's Act is
  manifest-anchored (clause-aligned), a total replacement.
- **Citation checks are ref-based.** `verify_citations` matches a cited number against the retrieved
  chunk's own `ref`, never pooled text; `verify_ground_truth` asserts every EXPECTED number appears in
  some chunk's `ref`. So demoting a ref to `general` (or changing ref logic) can hard-crash the eval
  before it prints anything — measure the blast radius in isolation first.
- `parse_act_v2.py` defaults to `--body-from=5`, which is what the shipped artifact was built with.
- `scripts/audit_corpus.py` pins `V1_CORPUS_SHA256` and `V2_CORPUS_SHA256`. Never edit a pin to make
  a run pass; a new corpus gets a new pin.

## Retrieval budget

- **Shipping: `k=4/doc, top_n=12`** (Phase E1b, 2026-09-20; `ask()` in `src/rag.py`,
  `app.offline_legal_hits()`). It was `k=3/doc, top_n=6` before, so **any baseline or comment
  predating 2026-09-20 was measured at 3/6.**
- **`top_n == 3 × k` is load-bearing**: `select_top` then returns every candidate, so the cross-doc
  cosine cut — the comparison `PerDocRetriever`'s own docstring calls invalid — never discards
  anything. Widening `k` without holding `top_n == 3k` measured **worse on all three sets** (the spare
  slots go to the global top, which the Constitution owns). `k=20/doc` measured `+0.000` on test.
  A `max_per_doc` ceiling proved bit-identical to plain `k=4/doc` and was not added. Neither `k` nor
  `top_n` can move a refusal: the top-score vector is byte-identical from k=3 to k=20.
- **`top_n` is a ceiling, not a count.** `MIN_SCORE` trims below it; six realistic queries showed
  7 · 12 · 9 · 7 · 7 · 6 (mean 8). `INLINE_EXCERPTS` stays 3, so the fold holds *the rest*, often 4,
  not 9. Do not write a test or doc that assumes 12.
- `PerDocRetriever` merges top-k from each doc rather than one joint index, because the Constitution
  is ~95% of the joint index. Consequence: **context precision is low by design** (0.217 at the E1
  budget; it read 0.333 at 3/6 — same relevant chunks over more shown chunks). Never gate or "fix" it.
- **Its `docs` dict is iterated in insertion order and hits are sorted by score alone, so insertion
  order breaks ties** — reordering `build_corpus()` silently moves published numbers. A new doc is
  appended last.
- The corpus contains a byte-identical duplicate chunk pair (`[Constitution s. 4]`). The display
  dedupes it since H1b (`app.dedupe_excerpts`, keyed on doc_id+ref+text); the corpus is unchanged.

## Query expansion (edit only with a fresh calibration)

- `expand_query()` = `expand_query_hand()` (the hand-written `SYNONYMS`) **followed by the OOV bridge**
  (`oov_bridge_terms()`, a dict built from GloVe at build time, Phase E4a).
- **The bridge code is the measured function verbatim — do not "tidy" its loose hand-key skip or its
  cap-before-dedupe;** `scripts/ablate_oov_bridge.py`'s PORT CHECK asserts it.
- **`SYNONYMS` must not be edited casually**: `calibrate_refusal.py` builds 34 of its 106 probes from
  that map's keys, so touching it moves that suite off **212 runs** and requires a fresh calibration.
  The hand map earned its place on `test2` (E5.3: 0.629 vs bridge-only 0.577 vs none 0.554).
- Expansion is **two-side gated**: expand only if the user's own words already clear `MIN_SCORE`;
  keep the expansion only if it still clears it. Guaranteed property: expansion never turns a refusal
  into an answer or an answer into a refusal; it only re-ranks within the answered set.
- Expansion is not symmetric: only user→corpus direction entries survive (an `education` key once
  cost Q7 recall 1.000 → 0.500).

## Declined arms — code is deliberately NOT on `main`

| Arm | Result | Archive |
|---|---|---|
| E2a BM25/RRF re-rank | inert as ordering (`top_n == 3k` + set-scored metrics); as selection, test 0.529 → 0.471. BM25 is the same lexical family as TF-IDF cosine, so the pool headroom is not lexically reachable. | `phase10/retrieval-quality` `a6016e4` |
| E3a corpus-derived synonym map | loses on every set, gains no question, halves `vocab-mismatch`. 6 of the 34 hand keys (`fined`, `fired`, `jail`, `job`, `lawyer`, `sack`) never occur in the corpus. | `phase10/retrieval-quality` `a6016e4` |
| E5 surface-form `beg`→`begging` | dev tie | harness `ablate_surface.py` on main; arm not shipped |
| M2 dense (Gemini embeddings) | declined for launch, not rejected; revisit with real query logs (H7). Free tier: 100 strings/min, counted per string. | — |
| F0 offline static embedding | frozen-10 −2 q, dev net 0 | `phase10/f0-static` `27ed13d` |
| H4 off-topic guard | dev 2/5 (needs 3) | `phase11/h4-offtopic` `e884f85` |
| H5a Pidgin-routed static arm | dev net +1 (needs +2) | `phase11/h5a-pidgin` `5b28c07` |
| H8a v3 corpus (+ Accessibility Regs) | dev stage: v3-12 regresses existing law (G1); v3-16 holds it but new-doc reach 0.583 < 0.60 (G3) and 3/6 status probes miss evidence (G5). test2/test3 unread. | `phase11/h8a-accessregs` |

**Do not re-implement any of these here, and do not re-run them without a new reason.** Never re-rank
by replacing the cosine scorer: BM25 scores are unbounded and would invalidate the `MIN_SCORE`
calibration. Superseded and never to be executed: M3 of `10_corpus_rebuild_and_dense.md`, and steps
4/5 of `08_retrieval_upgrades.md` (both need a model at query time, which `requirements.txt` forbids).

## Measurement lessons that bind future arms

- **A budget that shows more chunks inflates any recall-shaped metric by construction.** E1b's
  load-bearing evidence was the single-turn held-out column, not the chat deltas.
- `recall_strict` corrects *scoring*, not *retrieval*: it cannot see a chunk retrieved because of
  another clause's words (the packed-ref subsidy in the `ctx` arm).
- `CT4.t3`'s correct chunk sits outside the 60-candidate pool entirely (rank 104 at k=200); no
  widening reaches it.
- Term-level lexical and static-semantic levers: E2, E3 and F0 declined; E4a's win was narrow.
  A new arm in that family needs a strict a-priori gate and should expect to be declined.
- `eval_heldout.py` exits nonzero **only** on a ground-truth failure or a frozen-10 regression, never
  on a held-out number, by design.
- Frozen questions are frozen: add new ones, never edit them, never merge held-out into frozen-10.
  `bench_phase01.load_questions()` is kept so a reworded frozen question fails loudly.
- Current figures: `scripts/baseline_phaseE_2026-09-24.txt` (strict 0.734 / 0.613 / test 0.647 /
  test2 0.629, calibrate 0/212).

## Harnesses (measure-only; none gates CI)

`ablate_phase08.py` · `ablate_phase10.py` (width ladder, never gates) · `ablate_oov_bridge.py` (E4a +
PORT CHECK; `--read-test` spends `test`) · `ablate_handmap.py` (E5.3; `--read-test2`) ·
`ablate_surface.py` (E5, declined) · `e4_reach.py` (dev only) · `build_oov_bridge.py` (needs
`runs\e4_vectors\`) · `probe_embed_quota.py`, `transcript_chat.py` and `probe_gen_refusal.py` (spend
quota only with `--i-understand-this-spends-quota`) · `judge_phase06.py` (quota) ·
`build_h6_review.py` (deterministic review pack).
