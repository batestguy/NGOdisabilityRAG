# Phase 09 — Evidence base, generation fix, shippable retrieval (planned 2026-09-11)

## Goal
Phase 08 left retrieval at recall **0.925** against a 0.75 gate, and the judge confirmed the
one *real* remaining defect sits at the **prompt/generation** layer, not retrieval. This phase
widens the evidence base so retrieval claims can be trusted, fixes the confirmed generation
defect, and reshapes Phase 08 steps 4/5 into forms that actually reach production. Free tier
only ($0.00): `drlca-rag` env, Gemini free, Render free, local CPU, Colab/Kaggle.

## Background — three findings that reorder the Phase 08 playbook

Found 2026-09-11 by reading the harness while planning steps 4 and 5. All three are code
facts, not opinions, and each is cited to a line.

**1. Steps 4 and 5 as written cannot reach a single real user.**
`requirements.txt` is six packages and its own header says OCR/ONNX/FAISS "must NEVER be added
here." Step 4 needs a cross-encoder at *query* time. Step 5 needs to embed the *incoming
query* at query time — shipping prebuilt chunk vectors does not solve that half. "Flag-gated"
therefore means the flag is OFF in production: both steps would move local eval numbers and
change nothing for users. → Superseded by step 3 below, which delivers the same two wins with
zero query-time dependencies.

**2. Retrieval is no longer the bottleneck; generation is.**
Recall 0.925 vs a 0.75 gate, while the judge confirmed Q3 thinness is a REAL
prompt/generation defect (Q3 recall is **1.000** — the material was in context and the answer
ignored it). The Phase 08 step order was written when recall was 0.800 and is now aimed at the
half that already works.

**3. The synonym map is fitted to the set that scores it.**
An `education` key was deleted because it cost Q7; other entries were kept because they helped
Q5/Q8/Q9 — all tuned on the same 10 questions used to report 0.925. With n=10 there is no
held-out signal, so **0.925 cannot distinguish generalization from memorization.** This is the
strongest methodological weakness in the project right now, and it is free to fix. It matters
most for steps 4/5, which would otherwise be tuned on the same 10 points.

Two smaller blockers, both verified:

- **The pending two-run flakiness check is currently impossible.** `scripts/test_phase02.py:49`
  calls `ask(q, retriever=ret, use_llm=use_llm)` and never passes `use_cache`, which defaults
  `True` — run two would be 12 cache hits measuring nothing. `ask()` already accepts
  `use_cache` (`src/rag.py:438`); only the harness needs the flag.
- **Quota is being left on the table.** The 2026-09-11 judge run proved models draw from
  **separate pools** (spent `gemini-2.5-flash-lite`, touched `gemini-2.5-flash` zero times).
  A failover roughly doubles effective daily quota for free.

## Design decisions (settled before work starts)

- **The frozen 10Q stays frozen and stays SEPARATE.** New questions form a *held-out* set
  reported alongside it, never merged into it — merging destroys comparability with every
  artifact from Phase 01 onward.
- **`bench_phase01.load_questions()` keeps its exact contract** (returns exactly the 10). Both
  `assert len(questions) == 10` sites stay valid and untouched; the wider set gets a new loader.
- **Runtime-shippable only** (owner decision, 2026-09-11). Nothing may add a query-time
  dependency. Anything needing a model at query time is computed offline and shipped as a
  static artifact.
- **Both refusal layers untouched.** `MIN_SCORE = 0.10` is calibrated to *cosine* scores — this
  is exactly why step 3 re-ranks *inside* the gate instead of replacing the scorer.

## Steps

### 1. Ops hardening (zero quota, small, unblocks the rest — DO FIRST)

| File | Change |
|---|---|
| `scripts/test_phase02.py` | add `--no-cache` → pass `use_cache=False` to the existing `ask()` parameter |
| `src/rag.py` | opt-in model failover on a **daily-cap** 429 only |

Failover rules, so it can never corrupt evidence: **opt-in by flag**; record the model
*actually used*, not the one requested; trigger only on the daily cap — a per-minute 429 must
still be retried, never failed over. Reuse the working pattern already in
`scripts/judge_phase06.py` (7s pacing, `_is_per_minute()`, bounded backoff, checkpoint after
every call) instead of writing a second one.

**Green:** `--no-cache` run shows `cached: false` on every row · failover records the real
model id · a per-minute 429 still retries.

### 2. Widen the evidence base (zero quota — the yardstick for steps 3 and 4)

New canonical set at **`data/eval/questions.json`**: `id`, `text`, `set`
(`frozen10` | `heldout`), `expected: {doc_id: [nums]}`. `EXPECTED` moves out of
`scripts/eval_phase06.py:86` into this file; `verify_ground_truth` then runs over all of it.
Add `load_eval_set()` alongside the untouched `load_questions()`. This also retires the fragile
regex that currently parses questions out of `notebooks/01_foundation.ipynb` (it caps at
`qs[:10]` and falls back to a hardcoded list).

~30 held-out questions, ground truth authored **by corpus inspection only, never from LLM
answers** (the existing no-circularity rule, `eval_phase06.py:14`). Cover the failure classes
deliberately:

- vocabulary mismatch (Q5-class) — tests whether the synonym map generalizes
- TOC-trap candidates — tests fix-B beyond the two cases it was built on
- cross-document questions — exercises the per-doc merge design
- **~5 genuinely off-corpus** — measures false-*answer* rate; only R1/R2 exist today
- **~5 in-corpus but oddly worded** — measures false-*refusal* rate, which matters most
  (false refusals deny help to PWDs) and is currently almost unmeasured

The last two probe `MIN_SCORE` and the two-side expansion gate *without touching either*. They
measure the floor; they do not move it.

**Green:** `verify_ground_truth` passes over the full set · frozen-10 numbers reproduce
**bit-identically** · held-out numbers recorded separately as a new baseline, whatever they say.

Good candidate for the `executor` subagent — ~30 questions of corpus verification is
high-volume reading.

### 3. Retrieval that actually ships (zero quota — REPLACES Phase 08 steps 4 and 5)

**(a) BM25 re-rank inside the existing gate — step 4's benefit, no ONNX.**
Keep cosine scoring and `MIN_SCORE` exactly as the admission gate, then re-order the
already-admitted hits by BM25. Implement BM25 inline over the existing vectorizer (~30 lines,
**zero new packages**) rather than adding `rank_bm25`.

> **Hazard this avoids:** BM25 scores are unbounded and not comparable to cosine. Swapping the
> scorer outright would silently invalidate the calibration documented at
> `src/retrieve.py:26-44` and change refusal behaviour. Re-ranking *within* the admitted set is
> a pure ordering change — it cannot create or destroy a refusal.

**(b) Offline embedding thesaurus — step 5's benefit, no query-time model.**
On free Colab, embed corpus vocabulary, take nearest neighbours, filter to legal terms, ship
`data/processed/synonyms_auto.json`. Runtime cost is a dict lookup. This generalises the
hand-curated map and — validated on the held-out set — finally makes the generalization claim
testable. The proven two-side expansion gate in `src/retrieve.py` stays exactly as is.

**Green:** frozen-10 recall ≥ 0.925 (no regression) · **held-out recall is the real result** ·
precision still never gated · suites 03/04/05 green · `requirements.txt` byte-identical.

### 4. Fix the confirmed generation defect (quota-paced)

- **Answer-shape floor** in the prompt: require ≥2 claims with ≥2 distinct citations when ≥2
  distinct refs clear the floor. Scoped to Q3's class — the judge found **Q8 adequate**, so this
  is not a blanket "write more." Bump `PROMPT_VERSION`; the cache keys on the whole rendered
  prompt, so the bump misses the cache automatically and cannot replay stale answers.
- **Named `reverse_rel` fix**: count only hits from docs named in `EXPECTED`. Ship in a
  **separate commit** from any quality change, report as a re-baseline with old and new side by
  side, and re-run the deterministic ceiling analysis (currently 0.852) to show the new cap.
- **Fresh 12-call generation pass.** This is also the only thing that clears the Q5
  faithfulness artifact — the eval recomputes retrieval live against a frozen transcript, so
  **0.867 currently understates the system**. Any honest post-Phase-08 faithfulness number
  requires it.

**Green:** Q3 answer carries ≥2 cited claims · faith_audited ≥ 0.85 **earned** · recall still
> 0.75 · reverse_rel re-baselined with both numbers recorded.

## Sequencing and quota

Step 1 → step 2 → steps 3 and 4. Step 1 first because it unblocks the flakiness check and
doubles quota. Step 2 before step 3 because tuning retrieval on the same 10 points is the
contamination this phase exists to stop. Step 3 is zero-quota and can overlap step 4's quota
waits.

Budget after step 1: 20/day `gemini-2.5-flash` + 20/day `gemini-2.5-flash-lite` = **40
effective**. A 12-call generation run fits one day; the two-run flakiness check (24) fits one
day with failover, two without.

## Exit criteria
- [x] `--no-cache` flag exists and the two-run flakiness check is actually runnable.
      (2026-09-13. The check itself is **not** run — it costs 24 calls.)
- [x] Held-out set of ~30 questions with corpus-verified ground truth; frozen-10 reproduces
      bit-identically; held-out baseline recorded. (2026-09-13; 30 questions, 16335 B both runs.)
- [x] False-refusal and false-answer rates measured for the first time. (2026-09-13.)
- [ ] BM25 re-rank shipped inside the gate, ablated on frozen-10 **and** held-out.
- [ ] `synonyms_auto.json` shipped and ablated against the hand-written map on held-out data.
- [ ] Q3 answers ≥2 cited claims; faith_audited ≥ 0.85 earned on a FRESH transcript.
- [ ] `reverse_rel` re-baselined in its own commit, old and new numbers side by side.
- [ ] `requirements.txt` still byte-identical; live smoke green on Render.

## Results — steps 1 and 2, session 2026-09-13 (steps 3 and 4 NOT started)

**Zero Gemini calls spent this session.** Both milestones are offline by construction.

### Step 1 — ops hardening (PR #9, `phase09/ops-hardening`)

| Green criterion (as written above) | Outcome |
|---|---|
| `--no-cache` run shows `cached: false` on every row | flag lands; threaded into the existing `ask(use_cache=)` |
| failover records the real model id | `model_used` at top level **and** in `route`; `route["model"]` keeps its old meaning |
| a per-minute 429 still retries | proven: RPM 429 re-raises, zero fallback calls |

`FALLBACK_MODEL = gemini-2.5-flash-lite`. `is_per_minute_429()` / `retry_delay()` moved
verbatim from `scripts/judge_phase06.py` into `src/rag.py`; the judge imports and aliases them,
so its call sites and printed output are byte-unchanged.

New `scripts/test_phase09_ops.py`, **38/38**, zero network. The failover path is proven by
**injection**, not by spending quota — a live call only ever exercises the happy path, and the
sole way to make failover fire for real is to exhaust a daily cap, which costs a day.

Two honest deviations from this playbook's step-1 text:
- It says to reuse the judge's "7s pacing … checkpoint after every call" pattern. Only the two
  **classifiers** were reused. The pacing loop and checkpointing live in `judge_call()` and are
  specific to a long batch run; `ask()` answers one question and has no batch to checkpoint.
- The per-minute 429 test string is **reconstructed, not captured**, and is labelled as such in
  the test. The planning note expected it to be recoverable from
  `judge_phase06_results_gemini-2.5-flash-lite_2026-09-11.json`; that file holds verdicts only
  and contains no error strings, and the checkpoint that held the raw text was deleted after the
  run. The daily-cap string **is** genuine, read out of the 2026-09-09 transcript at runtime.

### Step 2 — held-out evidence base (PR #10, `phase09/evidence-base`)

| Green criterion (as written above) | Outcome |
|---|---|
| `verify_ground_truth` passes over the full set | 40 questions, 87 expected refs, verified against live chunk refs |
| frozen-10 numbers reproduce **bit-identically** | **16335 B == 16335 B**, byte-compared; baseline kept at `scripts/eval_p09pre.json` |
| held-out numbers recorded separately, whatever they say | done — see below |

**THE FINDING — the number this phase was built to produce:**

| set | n | mean recall | note |
|---|---|---|---|
| frozen 10 | 10 | **0.925** | the set the synonym map was fitted on |
| held out | 25 | **0.420** | nothing has been tuned on these |
| delta | | **−0.505** | |

Held-out recall is **less than half** the frozen figure. Per class: vocab-mismatch 0.312 (n=8),
cross-document 0.429 (n=7), toc-trap 0.500 (n=5), odd-wording 0.500 (n=5). The weakest class is
exactly the one the synonym map was supposed to fix. Nothing was reworded or re-expected in
response to this; every `text` and `expected` was fixed from corpus reading before the harness
was first run.

**Measured for the first time:**
- **False-refusal rate 0/25 = 0.0%** on answerable held-out questions (frozen-10 0/10).
  Retrieval returns *something* for every answerable question. It is frequently the wrong
  something — that is what recall 0.420 says. The floor is not denying help to PWDs.
- **Gate-level false-answer rate 5/5 = 100%** of off-corpus questions clear `MIN_SCORE`.
  Printed **ungated with the caveat attached** and **not** a reason to touch `MIN_SCORE`:
  it is a weak-overlap *floor*, not a semantic filter, and the in-corpus/off-corpus cosine
  bands are inverted (`src/retrieve.py:26-44`) — "sourdough" already scored 0.125 and
  "maritime shipping insurance" 0.318 before any of this work. The semantic layer is the
  strict-prompt `NO_ANSWER_SENTENCE` path, and measuring it costs quota.

**Deviation from this playbook's step-2 text, deliberate:** it proposed *retiring* the
notebook-parsing `load_questions()`. It is **kept**. `assert_frozen10_matches_notebook()` now
requires the canonical file and the notebook literal to agree, in order, on all ten texts —
two independent sources that must agree is a stronger invariant than one source nobody checks.
Drift was verified to raise.

**Verification-integrity note.** Ground truth was authored by `executor` from corpus inspection
only and reviewed by `reviewer`, which re-derived 15 of 30 rows against `data/processed/`
independently. The author raised a real hazard — `const_ref` labels Second Schedule legislative
list items as `s. N`, so a schedule hit could be a false positive for Constitution recall. It
was checked directly: of every hit that counted toward Constitution recall across all 40
questions, exactly one looked schedule-shaped, and it was a duplicate of a genuine Chapter II
body hit for the same question, so set-based recall is unaffected. **No held-out score is
inflated.** The `const_ref` mislabelling is real but pre-existing and out of scope here.

**Corpus gap found while authoring (H1):** the Act's cl.19 subsidy for special-education
personnel is **uncitable** — OCR rendered the heading `19.1`, so the sentence straddles chunks
labelled `cl. 18` and `cl. 20` and no `act2018` chunk ref carries 19. H1 expects the factsheet
limb only. Worth a look in a later phase; not touched here (`data/processed/` is read-only).

### Not done this session (unchanged, still open)
Steps 3 and 4 · the two-run flakiness check itself (step 1 only makes it *possible*; running it
costs 24 calls) · any Gemini call.

## Record results in
`LEARNING_JOURNAL.md` → per-step ablation tables (frozen-10 vs held-out side by side, always
both), quota ledger per run, and the generalization verdict on the synonym map.

## Traps
- Never edit a frozen question to make a metric pass. New questions may be added; existing ones
  are frozen once baselined.
- **Held-out numbers get reported whatever they say.** A drop versus the frozen 10 is *the
  finding* — it is the thing this phase was built to detect, not a bug to tune away.
- `verify_ground_truth` hard-crashes before printing anything if a ref carrying an EXPECTED
  number gets demoted to `general`. Measure blast radius in isolation first.
- Do not nudge `MIN_SCORE`. Step 2 measures the floor; step 3 re-ranks inside it.
- Never fake an LLM row: a daily-cap 429 stays pending and unfaked.
- Do not add a query-time dependency. If a technique needs a model at query time, it is the
  wrong technique for this deployment — precompute it offline and ship the artifact.
