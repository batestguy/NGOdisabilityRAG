# Phase 10 — Corpus rebuild + dense retrieval (planned 2026-09-13)

## Goal

A genuinely top-tier legal-aid chatbot at **$0.00**, with heavy offline work on free
Colab/Kaggle GPU allowed. This phase replaces Phase 09 step 3, which was **measured and
falsified** on 2026-09-13 (see Background). Free tier only: `drlca-rag` env, Gemini free,
Render free, local CPU, Colab/Kaggle.

## Background — what was measured on 2026-09-13, and what it killed

Phase 09 step 3 set out to fix retrieval with a better cross-doc merge and a BM25 re-rank.
**Both were built, both were measured, both are dead.** Everything below is zero-quota, on the
60-question set, with every "→6" arm returning exactly 6 chunks.

### What shipped and stays (M1 of the old plan, PR #11)

A clean 20-question `test` set (`T1`..`T20`), authored blind from the corpus before any
retrieval change and reviewed row by row against `data/processed/*.txt` with zero blocking
findings. `heldout` is relabelled **dev** — it was spent when its per-question misses were read
to design a fix. `eval_phase06.py` output stayed byte-identical to `scripts/eval_p09pre.json`,
proving M1 changed no retrieval behaviour.

| set | n | recall |
|---|---|---|
| frozen-10 (fitted on) | 10 | 0.925 |
| dev (ex-held-out) | 25 | 0.420 |
| **test (clean)** | 17 | **0.338** |

Test lands *below* dev, so dev was not unusually hard. Weakest class on test: vocab-mismatch
**0.125**. False refusal **0/17** — the floor is not denying help to PWDs.

### What was falsified — do not retry these

| arm | frozen10 | dev | test | shown |
|---|---|---|---|---|
| current `[:6]` slice | 0.925 | 0.420 | 0.338 | 6 |
| doc-quota merge `min_per_doc=1` | 0.925 | **0.420** | **0.338** | 6 |
| doc-quota merge `min_per_doc=2` | 0.846 | 0.420 | 0.353 | 6 |
| k=10 pool, `[:6]` slice | 0.867 | 0.400 | 0.338 | 6 |
| k=10 pool, quota →6 | 0.879 | 0.420 | 0.338 | 6 |
| k=10 pool, **no cut** | 0.950 | 0.700 | 0.559 | 30 |
| k=20 pool, **no cut** | 0.950 | 0.773 | 0.765 | 60 |

1. **The doc-quota merge is recall-neutral.** `min_per_doc=1` reproduces baseline to three
   decimals on all three sets while changing *which* six chunks are shown on 7/60 questions.
   Refusal invariance held bit-identically across 106 probes (60 questions + 12 off-corpus + 34
   bare synonym keys), so the proof is sound — it just buys nothing.
2. **The old diagnostic's gains were a `top_n` effect, not an ordering effect.** 0.460 / 0.627 /
   0.700 / 0.773 were all measured with *no cut* — showing 9, 18, 30, 60 chunks. Under the
   decision "users keep seeing 6 excerpts" there is nothing for a merge to recover.
3. **Widening the pool at a fixed cut of 6 is neutral-to-harmful** — k=10 with the current slice
   drops frozen-10 to 0.867, *below* the 0.925 guard.
4. **BM25 is a coin flip.** Over 91 (doc, expected-ref) pairs it ranks the expected chunk higher
   on 15 and lower on 16; rank buckets barely move (1-3: 50→52, 21+: 12→14).

**Lexical retrieval is exhausted.** No reordering of TF-IDF candidates reaches the tail.

### The bigger finding: the corpus is the real ceiling

Measured via `rag.build_corpus()` — previously unmeasured anywhere in the repo, and reproduced
independently on 2026-09-13:

| doc | chunks | `ref=="general"` (uncitable) | packed refs (`cl. 16,17`) |
|---|---|---|---|
| `act2018` | 62 | **25 (40%)** | 16/62 |
| `factsheet2020` | 48 | 9 (19%) | 19/48 |
| `constitution1999` | 2104 | 99 (5%) | 0 |

Act clause numbers **19, 35, 38, 40** produce no `ref` anywhere. Each was traced:

- **19, 35, 37, 54 bodies are all present in the text** — `"35. (1) A person ceases to hold
  office as a member of the Council if he-"`, `"37. The Council shall have power to-"`. They are
  invisible only because `act_ref()` infers refs from heading *shape*, and the gazette's
  marginal-note column is spliced into the body: `"37.The Council shall have power
  to-\nPower of the\nCouncil.\n(a) manage and superintend..."`. **Recoverable by parsing, free.**
- **38 and 40 are not in the source at all.** `data/raw/disability_act_2018_full.pdf` is a pure
  scan (27 pages, **0** embedded text chars — the Constitution and factsheet PDFs both *have*
  text layers). Raw OCR pages 5 and 6 are the same physical page scanned twice (0.819
  similarity, both PART II cl.3–4), so 27 raw pages cover 26 distinct pages of a 27-page
  instrument. The missing page carries cl.38's opening and cl.40. **No OCR can recover it.**

This matters more than ranking. The project's central invariant is *every legal claim carries a
citation tag copied verbatim from the chunk header*. With 40% of Act chunks uncitable, that
invariant is structurally broken on the app's most important document. **A better ranking over
uncitable chunks is a better-ranked list of things you are not allowed to cite.**

Also user-facing: excerpts are displayed verbatim and the text contains
`"Apersonwith disabilityhas theright to access"`. Screen readers read that aloud.

## Design decisions (owner, 2026-09-13)

1. **Cheap measurable wins first**, then the corpus rebuild, then fine-tuning.
2. **Gemini embeddings at query time** for the dense arm.
3. **Parser fix now**; VLM re-OCR is a separate later milestone.
4. **Owner hunts for a born-digital Act** to fix cl.38/40 and cross-verify the OCR.

### The one decision argued against, and how this plan de-risks it

Static (model2vec-class) embeddings were recommended; the owner chose Gemini embeddings at
query time. It is the highest-quality option. Two consequences are engineered around here
rather than discovered later.

**Availability.** `CLAUDE.md` states the default user path makes zero network calls. Putting
embeddings in that path means retrieval can fail — exactly when quota runs out. Handled by a
**degradation ladder** that is never allowed to break retrieval:

```
tier 1  Gemini gemini-embedding-001  (best; cached; needs key + quota + network)
tier 2  static distilled encoder     (numpy only, offline — built in M4)
tier 3  TF-IDF lexical only          (today's behaviour; always works)
```

M2 ships tiers 1 and 3. Until M4, "offline" means today's quality — a degradation, never an
outage. The `CLAUDE.md` invariant gets **explicitly amended with its reasoning recorded**, not
quietly broken.

**Privacy — new, and needs an owner call in M2.** Today Gemini is opt-in behind an expander
defaulting OFF, so a user who never opts in has their question stay on the device. Embedding at
query time sends **every** question to Google, including from users who never wanted AI. These
questions describe disability, abuse and begging coercion. M2 therefore ships a visible notice
and a hard-offline toggle. Non-negotiable for this user population.

**Quota is unknown and must be measured, not assumed.** Google no longer publishes free-tier
embedding limits (`ai.google.dev/gemini-api/docs/rate-limits` defers to AI Studio). The 20/day
figure in `CLAUDE.md` is the *generation* cap; embeddings are a different model family and
probably far higher. M2 opens with an empirical probe, following this project's own precedent
("20 calls/day confirmed by 429").

## Steps

### M0 — Seal v1, and build metrics that can tell ranking from width

Branch `phase10/seal-v1`. Zero quota. **Do this first** — everything after invalidates
baselines.

- **Commit `select_top`** (already written, uncommitted on `phase09/merge-fix`) with an honest
  claim: it fixes a real defect — `src/rag.py:537` and `app.py:243` sort candidates from three
  separate TF-IDF spaces by raw cosine, which `PerDocRetriever`'s own docstring calls invalid —
  and it is provably refusal-invariant. **Recall unchanged.** It is needed as the cross-doc
  merge once a dense arm exists. Do not claim a recall win.
- **`recall_strict`** in `scripts/eval_heldout.py`: credit at most **one** expected number per
  retrieved chunk. This is the load-bearing migration metric. Today a chunk tagged `cl. 16,17`
  satisfies two expected refs at once and 16/62 Act chunks carry packed refs, so clause-aligned
  chunking will *mechanically lower* `recall` at identical retrieval quality. **Publish v1's
  `recall_strict` before v2 exists** or every v2 number looks like a regression.
- **`recall@{3,6,10,20,60}` curve + `rank_of_first_expected` + MRR**, per set, for every arm
  from now on. This is what makes "ranking or width?" unanswerable by accident — the mistake
  that produced the falsified plan.
- **`scripts/audit_corpus.py`** (new): makes the corpus table above reproducible and, in M3, a
  gate. Per doc: chunk count, length histogram vs the size cap, `ref=="general"` count/%,
  packed-ref count/%, and which clause numbers in the Arrangement manifest have no ref.
- **`scripts/baseline_v1_2026-09-13.txt`** (new): archived stdout of `eval_heldout.py` and
  `eval_phase06.py` at this commit, so v1 is reproducible from an artifact, not from prose.
- Rename the guard to `FROZEN10_RECALL_BASELINE_V1`; add `CORPUS_VERSION` to every artifact
  header. Keep `eval_phase06.py`'s existing writer intact — its byte-identity claim against
  `scripts/eval_p09pre.json` is a real asset; new columns go to a new `--out=` path.

**M0 green:** v1 `recall` *and* `recall_strict` and the recall@k curve published for all three
sets · `audit_corpus.py` reproduces the corpus table · all suites green · `eval_p09pre.json`
still byte-identical.

### M1 — Widen the prompt, not the screen

Branch `phase10/prompt-width`. Zero quota. The free, immediate win.

Three budgets are conflated under one `top_n` today. Separate them:

| budget | now | target | real constraint |
|---|---|---|---|
| candidate pool | k=3/doc | k=8–10/doc | none, CPU is free |
| chunks in the Gemini prompt | 6 | **10–12**, ≤4 per doc | none material — 12 × ~600 chars ≈ 2k tokens against a 1M context; the free tier caps *calls*, not tokens |
| excerpts rendered on screen | 6 | **3 inline + rest in one expander** | screen-reader burden |

`select_top` returns one ordered list of 12; `app.py` splits it 3 + 9 **for rendering only**;
`ask()` sends all 12. Same list, two presentations — a display path that slices differently from
`ask()` shows a system nobody measures (`app.py:241-244` already makes this point).

Streamlit's `st.expander` renders native `<details>/<summary>`, which screen readers announce as
a collapsed disclosure widget, so linear document order survives. Keep the 700-char truncation.

`scripts/test_phase05.py` asserts on `app.py`'s **source text** and will break by design —
update those assertions in the same commit.

**M1 green:** recall@12 reported on all three sets · false-refusal not worse · 3 inline excerpts
on screen · suites 03/04/05 green · `import app` clean.

### M2 — Dense retrieval via Gemini embeddings, fused by rank

Branch `phase10/dense-gemini`. This is the quality step.

**Open with the probe.** `scripts/probe_embed_quota.py` (new): batch sizes, RPM and RPD for
`gemini-embedding-001`, pushed until 429, error strings recorded verbatim into
`LEARNING_JOURNAL.md`. Reuse `rag.is_per_minute_429()` and `rag.retry_delay()` — they already
distinguish per-minute from daily caps. Everything below sizes itself on the result.

**Offline corpus embedding.** Extend the existing `embed_gemini()` (`src/retrieve.py`) to batch
(it currently loops one text per call) and add resumable checkpointing in the shape of
`scripts/.judge_phase06_checkpoint.json`. Use the **asymmetric task types** the model supports —
`RETRIEVAL_DOCUMENT` for chunks, `RETRIEVAL_QUERY` for queries — and request reduced output
dimensionality (768 or 256 via MRL) to keep the artifact small. Ship
`data/embed/chunks_gemini.f16.npy` + `manifest.json` (model id, task type, dim, corpus sha256,
build date, builder commit). 2214 v1 chunks batched ≈ tens of calls, not thousands.

**Runtime query side** (`src/retrieve.py`, new `DenseRetriever`): embed the query at tier 1,
cache it keyed on the normalised query string — reuse the `_cache_key`/`_cache_read`/
`_cache_write` pattern from `src/rag.py:391-432`, including its "corrupt cache is a miss, never
an error" property. Repeat questions then cost nothing. **No FAISS** — 2214 × 768 fp16 is a
3.4MB matrix and a numpy matmul is ~3 MFLOP.

**Fusion — Reciprocal Rank Fusion, within each doc.** RRF compares *ranks*, never raw scores, so
it structurally cannot reintroduce the invalid cross-doc comparison this session found:

```
per doc:  fused[c] = w_lex/(60 + rank_lex(c)) + w_dense/(60 + rank_dense(c))
cross-doc: select_top() quota, ordered by fused_score(c) / fused_score(that doc's top)
```

The cross-doc key is within-doc-relative, so it is comparable by construction. Document it as a
display/prompt-ordering heuristic that never touches the gate.

**The gate stays byte-identical — the most important design decision here.** Separate "should we
answer?" from "what do we show?":

- **Refusal**: computed exactly as today from `PerDocRetriever.query()`, including both
  expansion gates. `MIN_SCORE = 0.10` is untouched and the calibration block at
  `src/retrieve.py:26-44` stays valid without renegotiation. Assert refusal invariance in the
  ablation, as M2-of-the-old-plan did successfully across 106 probes.
- **Per-hit admission** must change, or every dense-only candidate is dropped and the arm does
  nothing: admit if `tfidf_cos ≥ MIN_SCORE` **or** `dense_cos ≥ DENSE_FLOOR`. Derive
  `DENSE_FLOOR` by the *same documented procedure* as `MIN_SCORE` — in-corpus minima across all
  52 answerable questions vs off-corpus maxima on the same probes (`sourdough`, `quantum`,
  `visa`, `maritime shipping insurance (law)`) — and write a new calibration block beside the
  existing one. Record whether dense bands separate better than TF-IDF's inverted bands; that is
  the first real evidence this project would have about semantic separability, interesting
  either way.

**Privacy + availability, shipped in this milestone:** the tier-1/3 ladder with silent fallback;
a visible notice that search sends the question to Google; a hard-offline toggle that pins tier
3; and `CLAUDE.md`'s offline invariant amended in the same commit with the reasoning.

**Retire the hand-written `SYNONYMS` map — measured, not assumed.** It is 40-odd entries curated
against 10 questions and it demonstrably does not generalise (vocab-mismatch 0.312 dev, 0.125
test). Give the dense arm the **raw** query and ablate: A lex+syn, B lex only, C lex+syn+dense,
D lex+dense. **If D ≥ C, delete the map** — that removes `_surface_forms`, the stem-collision
assert and both expansion gates. A large honest simplification only a dense arm makes available.

**M2 green:** test recall@6 materially above 0.338 · frozen-10 `recall_strict` not worse ·
refusal decisions bit-identical · `DENSE_FLOOR` derived and documented · retrieval still works
with the key removed, quota exhausted and network down (test all three) · privacy notice and
offline toggle present.

### M3 — Act parser, clause-aligned chunking, clean re-extraction

Branch `phase10/corpus-v2`. Zero quota. The stage that fixes the citation invariant.

**Versioned, never destructive:** `build_corpus(version="v2")` with `v1` preserved verbatim —
same paths, same splitters, same ref functions — so every published baseline stays reproducible
from the same commit. `data/processed/disability_act_2018_full.txt` is **not** touched; v2
writes new files.

**Act — manifest-anchored parsing, replacing ref inference.** The Arrangement of Sections
survived OCR well, so parse it into `{1..58 → title}`, then locate each clause body by searching
for `N.` near a fuzzy match of its known title (`difflib.SequenceMatcher`, already the idiom in
`src/load.py`). Anchoring on (number, expected title) rather than heading *shape* is what makes
`19.1`, `35.(1)`, `37.The` and `54.A` all resolve. One clause = one chunk; split over ~1,100
chars on `(1)`,`(2)` then `(a)`,`(b)`. **Strip `[MARGIN]` note lines out of the body and keep
them as metadata** — interleaved they are pure retrieval noise and the cause of the
heading-regex failures.

Ref grammar stays byte-compatible: `ref` remains `cl. 16` (number only). Subsection paths go in
a new defaulted field, `Chunk = namedtuple(..., defaults=("",))`, so `cite_tag()`,
`CITE_TAG_RE`, `verify_citations()` and every historical transcript's tag grammar are untouched.

`act_ref()` is kept and **demoted to a validator** — `audit_corpus.py` asserts it agrees with
the parser, so two sources must agree rather than one going unchecked. Same discipline as
`assert_frozen10_matches_notebook()`.

**Exclude the Arrangement of Sections from the retrievable corpus.** It is the Act-side twin of
the Constitution TOC trap.

**Constitution — re-extract from the text layer** (PyMuPDF, dev-only) into
`(chapter, part, section, subsection)` units. One section = one chunk, subsection-split above
~1,200 chars. Expect 2104 → ~400–600 chunks. Three wins: **dropping the Arrangement pages
deletes the entire `toc-trap` class** (7 of 60 questions) and lets the `_is_toc_fragment`
heuristic tower at `src/rag.py:140-185` become a lint assertion; s.46-split-across-chunks is
fixed; per-doc imbalance falls from 95% to ~75%.

**Factsheet — re-extract from its text layer**, parsing the S/N table so one row = one
`Section N`. That is the source of its 19/48 packed refs.

**Clauses 38 and 40.** Owner hunts for a born-digital Act first (PLAC/`placng.org`, National
Assembly, `nigeria-law.org`, ILO NATLEX, Official Gazette No. 11 Vol. 106 of 2019; also re-check
`data/raw/disability_act_JONAPWD.html`, 162KB raw vs 1.5KB processed). If that fails: record
`body_present: false` in `data/processed/act2018_manifest.json`, exclude them from the corpus,
and surface a caption — *"My copy of the Act is missing clauses 38 and 40 — for those, call DRAC
08000-3000-100."*

> **Three things that must never happen here.** No stub chunk tagged `[Act cl. 38]` with
> placeholder text — a citation tag in front of a generation model is precisely how a gap
> becomes a hallucinated provision that passes `verify_citations` mechanically. No
> reconstruction from the factsheet's paraphrase. No reconstruction from model knowledge. This
> is a legal-aid tool for disabled people; fabricated statute text behind a verbatim-looking
> citation is the worst output this codebase can produce.

**The hidden hazard — chunk length silently recalibrates the refusal floor.** `CONST_SIZE = 400`
is pinned by Phase 01 measurement, but that is a TF-IDF artifact: short chunks concentrate term
mass and inflate cosine. Longer chunks *lower every cosine*, which can manufacture false
refusals — the failure `CLAUDE.md` names as the worst one. Mandatory, in order:

1. Re-derive the `src/retrieve.py:26-44` calibration table against v2 and write the new numbers
   in. `MIN_SCORE` may move **down** (the gate is documented to err low); it may **not** move up.
2. Gate the rebuild on `false_refusal_v2 ≤ false_refusal_v1` (currently 0/10 frozen, 0/25 dev,
   0/17 test).
3. Escape hatch if any false refusal appears: keep a small frozen 400-char-window TF-IDF index
   used *only* for the answer/refuse decision while ranking and display use v2. Present it as
   the hatch, not the default — two indexes is real complexity.

**M3 green (`audit_corpus.py` thresholds):** `ref=="general"` ≤ 1% per doc · packed refs **0** ·
every clause 1–58 citable or in the gap manifest · no chunk at the size cap unless it is a
subsection split · false-refusal not worse than v1 · `act_ref` validator agrees with the parser.

### M4 — Fine-tune on free GPU, and distil the offline tier

Branch `phase10/finetune`. 0–20 calls. Two deliverables: a better dense arm, and tier 2 of the
ladder so the offline path stops being a downgrade.

**Synthetic queries** (`scripts/gen_synth_queries.py`, `notebooks/11_synth_queries_colab.ipynb`):
`Qwen2.5-7B-Instruct-AWQ` via vLLM on a Colab T4, or bf16 on Kaggle (2×T4, 30h/week). ~8 queries
per Act/factsheet chunk, ~3 per Constitution chunk ≈ 3k pairs, ~30 min batched. The prompt is
where the value is: Nigerian English, lay register, short, **explicitly forbid reusing
distinctive passage terms**, and mirror the real class mix (direct, vocab-mismatch, odd-wording,
first-person situational, cross-document) — plus **Pidgin** variants, which real users type and
nothing in the stack handles today. Do *not* use a doc2query T5 model as generator; it copies
passage terms, which is exactly the lexical bias not to train on.

**Hard negatives** (`scripts/mine_hard_negatives.py`): top-50 with the base encoder, remove the
positive **and every chunk sharing its `ref`** (a sibling subsection of the same clause is not a
negative), sample 4 from ranks 10–50, then **denoise with `cross-encoder/ms-marco-MiniLM-L6-v2`**
— drop anything it scores above the positive. That step is what stops training the model to
reject correct passages.

**Decontamination — must be an artifact, not an intention.** `scripts/decontaminate_train.py`
drops any synthetic query matching an eval question by exact match, token-Jaccard ≥ 0.6, or
char-5-gram containment ≥ 0.5, writing every drop and its colliding eval id to
`data/train/decontam_report.json`. Publish the count. **Select checkpoints and all
hyperparameters (RRF `k`, `w_lex`/`w_dense`) on a synthetic validation split, split by chunk** —
selecting on dev makes dev a training signal; selecting on test destroys the last clean
yardstick. Write down one honest caveat: the generation prompt reuses the class taxonomy that
authored the test questions. That is stylistic overlap, not answer leakage, but a reviewer
should read it from us first.

**Train and distil:** `bge-small-en-v1.5` or `e5-small-v2` (33M, 384-dim; if e5, bake the
`query:`/`passage:` prefixes into the artifact so runtime never knows),
`MultipleNegativesRankingLoss` with in-batch + mined negatives, batch 32–64, lr 2e-5, 2–3 epochs
≈ 600 steps ≈ **4–6 min on a T4**. Then `model2vec.distill(pca_dims=256, apply_zipf=True)` with
vocabulary extended by corpus terms and legal bigrams (`transitory period`, `reasonable
accommodation`, `first consideration`) → tier 2: `data/embed/tokens.f16.npy` (~15MB, mmapped) +
`src/static_embed.py` (~150 lines, numpy only, vendored so **zero new packages**), with a
build-time parity assertion of ≥0.9999 cosine against the reference `model2vec.StaticModel` on
500 sampled strings including all 60 eval questions.

**Report the distillation tax explicitly** — four rows at shipping depth: TF-IDF only /
off-the-shelf dense / fine-tuned transformer (dev-only, label it **unshippable**) / distilled
static (shippable). Only add `numpy` to `requirements.txt` as an explicit pin; a load-bearing
import arriving transitively through scikit-learn is how a future bump breaks production
silently. numpy is neither OCR, ONNX nor FAISS, so the stated prohibition stands.

**M4 green:** test recall@6 above M2 · distillation tax reported · tier 2 works with network
fully disabled · decontam report published · `requirements.txt` diff is the numpy pin only.

### M5 — Re-baseline honestly, then one fresh transcript

Branch `phase10/rebaseline`. ~42 calls over 2 days across both pools.

- **Re-verify ground truth against v2, corpus-only.** All 60 questions: re-read each `note`,
  confirm each expected number still names the same provision. frozen10 and dev first.
  **Re-verify `test` without looking at any v2 retrieval output** — the discipline under which
  it was authored. Add `verified_against: "corpus-v2"`, `verified_at`, `verified_by`.
- **Retire, never edit.** A question whose truth changed gets `"status": "retired-v2"` +
  `retired_reason`, stays in the file for provenance, and is excluded from means. Rewording a
  question to survive the rebuild would destroy everything the eval discipline bought.
- **New questions go to a new `test2` set**, authored from the v2 corpus before any v2 retrieval
  is measured. Clauses 19/35/37/38/40/54 are newly citable or newly documented and deserve
  coverage. Never merged into `frozen10`/`heldout`/`test`.
- **`verify_expected` gets easier, which is a trap** — v2 has strictly more citable numbers, so
  passing it stops being evidence. Add the reverse check: every corpus `ref` must be reachable
  from the manifest, so a parser bug that *invents* refs also fails.
- **One published table**: v1 and v2 × all sets × both recall definitions × recall@k curve ×
  false-refusal × corpus audit deltas, with an explicit paragraph naming which comparisons are
  legitimate. `recall_strict` across versions: yes. `recall` across versions: no. Anything on
  `test`: one-shot.
- **Claims to retire by name:** `frozen-10 0.925` / `dev 0.420` / `test 0.338` (v1-corpus) ·
  `context precision 0.333 is by design` (the *reasoning* survives, the number does not — it is
  a function of chunk count and `top_n`) · the Phase 01 chunk-size pinning (measured against a
  corrupted Act with TF-IDF only) · the `MIN_SCORE` calibration table (re-derived, not
  inherited) · `reverse_rel 0.630` and its 0.852 ceiling · every `test_phase02_results_*.json`
  and `judge_phase06_results_*.json` (still valid records of what was said on a date; no longer
  descriptions of the current system — say so in `HANDOFF.md`) · `Act cl.19 is uncitable`.
- **Fresh transcript last, once**: 12-call Phase 02 pass (`--no-cache`), then the ~30-call judge
  on a later day. Also fix the confirmed Q3 generation defect here (answer-shape floor: ≥2
  claims with ≥2 distinct citations when ≥2 distinct refs clear the floor; bump
  `PROMPT_VERSION`, which auto-misses the prompt-keyed cache).
- **Docs**: `STATUS.md`, `HANDOFF.md`, `README.md`, dated `LEARNING_JOURNAL.md`, this playbook,
  and `CLAUDE.md` (three-doc corpus section, chunk sizes, `MIN_SCORE` pointer, `data/embed/`
  artifacts, the numpy pin, the amended offline invariant, and an explicit note that a
  *verified, human-signed corpus re-extraction* is a different act from "cleaning up OCR quirks
  in section numbers" at generation time, which stays forbidden).

## Verification (from `D:\NGORAG`, project interpreter only)

```powershell
C:\conda-envs\drlca-rag\python.exe scripts\audit_corpus.py            # M0; gates in M3
C:\conda-envs\drlca-rag\python.exe scripts\eval_heldout.py            # frozen/dev/test, recall + recall_strict + @k
C:\conda-envs\drlca-rag\python.exe scripts\ablate_phase10.py          # lex / +dense / +synonyms arms
C:\conda-envs\drlca-rag\python.exe scripts\ablate_phase08.py          # integrity arms still PASS
C:\conda-envs\drlca-rag\python.exe scripts\bench_phase01.py
C:\conda-envs\drlca-rag\python.exe scripts\test_phase03.py
C:\conda-envs\drlca-rag\python.exe scripts\test_phase04.py
C:\conda-envs\drlca-rag\python.exe scripts\test_phase05.py
C:\conda-envs\drlca-rag\python.exe scripts\test_phase09_ops.py
C:\conda-envs\drlca-rag\python.exe -c "import app"
C:\conda-envs\drlca-rag\python.exe scripts\eval_phase06.py --out=scripts\eval_p10.json
git diff --stat main -- requirements.txt        # empty until M4, then the numpy pin only
```

`--out=` **equals form only** — the space form is silently ignored and would overwrite a
versioned transcript. Degradation ladder must be tested all three ways: key removed, quota
exhausted (inject a 429), network down.

## Out of scope

VLM re-OCR of the Act (own milestone, after the born-digital hunt resolves) · LangChain · FAISS
(a 3.4MB matmul beats it on every axis) · ONNX at runtime · nudging `MIN_SCORE` upward · a
query-time cross-encoder (same dependency problem, and BM25's 15-vs-16 result says re-ranking a
fixed candidate set is not where the recall is) · owner gates (GIF, NVDA, keyboard, mic,
LinkedIn) · the stray `D:NGORAG_review_judge.diff` (owner removes by hand).

## Traps

- **Never compare raw scores across docs** — not cosine, not BM25, not dense. Separate indexes,
  different IDFs. RRF is chosen precisely because it compares ranks.
- **The refusal gate stays on the TF-IDF signal.** That is what keeps the calibration valid and
  the false-refusal rate assertable. Admission widens; the gate does not move.
- **Publish v1 `recall_strict` before v2 exists.** Otherwise correct work reads as regression
  and the explanation reads as excuse-making.
- **`test` is read once, at the end of a milestone, never tuned against.** A disappointing test
  number is the finding. `test2` is authored from v2 before v2 retrieval is measured.
- **Never select a checkpoint or a fusion weight on dev or test.** Synthetic val split, by chunk.
- **No stub chunk, no paraphrase, no model knowledge for cl.38/40.**
- **Retire questions, never edit them. Never merge new questions into an existing set.**
- Every harness uses `select_top`, never its own `[:TOP_N]`.
- `verify_expected` hard-crashes before printing if an expected number is missing — verify each
  new expected ref against a real chunk `ref`.

## Results

*(none yet — planned 2026-09-13, no milestone started)*
