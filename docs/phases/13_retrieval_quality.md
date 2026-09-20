# Phase E — retrieval quality: close the ranking gap, spend nothing

**Status:** **ACTIVE.** **E1 DONE and SHIPPED 2026-09-20** (`3d280fb` + `9748086`) · **E2
MEASURED and DECLINED 2026-09-20** (`measure(phase10-E2a)` — see the amendment box on E2) ·
**E3 MEASURED and DECLINED 2026-09-20** (`measure(phase10-E3a)` — see the amendment box on E3;
all four arms lose, the auto map halves its own target class, `SYNONYMS` unchanged) ·
**NEXT IS E4 — and it MUST BE RE-SCOPED BEFORE IT IS RUN** (amendment box on the E4 step): as
written it is inert at the shipping budget for E2a's exact reason, and two consecutive term-level
arms have now failed to reach the pool headroom while E4 is also term-level.
**E1b is staged for `main` on `phase10/ship-e1b` and is NOT YET MERGED — until it is, users are
still served the `3/6` budget, i.e. the `0.471` arm and not the `0.529` one.**
Zero Gemini quota spent in the phase so far, and none is needed for E4.
*(This line read "planned, not yet started" until 2026-09-20.)*
**Runs after:** Phase D (`12_corpus_v2.md`) — **COMPLETE, MERGED to `main` and DEPLOYED
2026-09-19 (`8682869`).** `CORPUS_VERSION = "v2"` is the default **and is what users are now
getting**, which changes one thing about this phase: it is no longer working on a side corpus.
**Every E arm that lands on `main` reaches real users on the next push.**
**Branches — TWO, and the split is deliberate (2026-09-20).**
`phase10/ship-e1b`, cut at `9416fef`, carries **only** the measured E1 win and the written record;
**it is what merges to `main`.** `phase10/retrieval-quality`, cut from `main` at `8682869` and
retained untouched at `a6016e4`, carries E2a's and E3a's **declined code** —
`scripts/ablate_rerank.py`, `scripts/build_synonyms.py`, `scripts/ablate_synonyms.py`, their opt-in
`src/retrieve.py` consumers and both `data/processed/synonyms_auto*.json` artifacts (~36.6k lines).
**It is the only copy. Re-run declined arms from there; none of it is on `main`.**

---

> ## ⚠ AMENDED 2026-09-19, AFTER D6 RAN — two findings bind on the steps below
>
> Both come from the D6 chat-set triage (`12_corpus_v2.md` D6 results;
> `scripts/baseline_v2_2026-09-19.txt`). Neither was known when this playbook was written, and
> **each one contradicts something stated below.** Read them before judging E1 or E2.
>
> **1. `CT4.t3`'s correct chunk is OUTSIDE the 60-candidate pool entirely.** Act cl. 25 sits at
> **rank 104 at k=200** for that contextualised query. **E1's `k=20/doc` widening does not reach
> it.** The diagnosis section below is still right that *most* of the loss is ranking — but "found
> in pool" is measured on the held-out sets at k=60, and the chat sets have misses past that
> depth too. Do not read an E1 arm that fails to move `CT4.t3` as E1 having failed; it is out of
> E1's reach by construction, exactly like the 3 test questions named under "Ceiling" below.
>
> **2. The mechanism is chunk LENGTH, and that is direct evidence for E2.** `CT4.t3` scored on v1
> only because a **packed** `cl. 25,26,27` chunk carried its *neighbours'* words ("queue",
> "accommodation") that contextualisation had introduced. v2's clause-aligned cl. 25 chunk is
> **305 chars** and contains neither. The naive-arm rank barely moved (v1 40 → v2 41), so the
> rebuild did not damage retrieval — what changed is that short, correctly-scoped chunks lose to
> long ones under TF-IDF's length handling. E2's stated `1100` vs `400` spread **understates** it:
> real v2 chunks run down to ~300 chars. **This is the strongest single piece of evidence in the
> playbook for doing E2 at all.**
>
> **3. `recall_strict` does NOT neutralise the packed-ref subsidy in the `ctx` arm.** It corrects
> **scoring** — one chunk cannot satisfy two expected refs. It cannot see a chunk *retrieved*
> because of text belonging to a different clause. E2 green below says "held-out `recall_strict`
> **is the real result**"; that stays true for the *naive* arm, but **a contextualised `strict`
> number is not by itself proof that a gain is real.** D5's "strict == plain, therefore not the
> packed subsidy" inference was wrong on the retrieval side.

---

## Why this playbook exists

Phase E work was scattered across two older playbooks written before the evidence existed:

- `09_evidence_and_generation.md` **step 3** — BM25 re-rank (3a) + offline synonym thesaurus (3b).
  Scoped 2026-09-13, **never started**.
- `10_corpus_rebuild_and_dense.md` **M1** (pool/prompt width) and **M2** (dense via Gemini
  embeddings). Reordered to after Phase D on 2026-09-16, **never started**.

Neither was written with the held-out recall@k curve in hand, because that curve did not exist
until Phase 09 step 2. **It changes the priorities and the sizing**, so Phase E gets a
consolidated playbook the way Phase D did when M3's premises moved. The originals are **kept,
not deleted**, with amendment boxes pointing here.

---

## The diagnosis — measured, not assumed

All numbers below are from `D:\d5_baseline\heldout_v2.txt` and `ablate_v2.txt` (D5 session,
corpus v2, shipping arm `k=3/doc → top_n=6, MIN_SCORE=0.10`).

### The problem is RANKING, not absence

| set | r@3 | r@6 | r@10 | r@20 | **r@60** | MRR | med-rk | found in pool |
|---|---|---|---|---|---|---|---|---|
| frozen-10 (fitted on) | 0.512 | 0.655 | 0.684 | 0.713 | 0.904 | 0.925 | 1 | 10/10 |
| dev (n=25) | 0.373 | 0.440 | 0.527 | 0.607 | 0.733 | 0.435 | 2 | 20/25 |
| **test (clean, n=17)** | 0.324 | 0.426 | 0.441 | 0.559 | **0.735** | 0.400 | 3 | **14/17** |

> **⚠ CORRECTED 2026-09-20 (E1). The `r@6` column above was headed "(shipping)" and it is NOT the
> shipping arm** — this whole table is the **recall@k CURVE**, and `eval_heldout.py:128-131` warns
> against quoting its `@6` as the shipping number. The curve builds `select_top(top_n=60)` over 60
> candidates, so its quota phase is **vacuous** and `@6` carries no `min_per_doc` reservation.
> **Shipping test recall was `0.471`, not `0.426`** (and is `0.529` since E1b). Exit criterion 1
> below always said `0.471`, so the playbook contradicted itself; the criterion was right.

`eval_heldout.py` prints the interpretation rule itself: *"A large gap between @6 and @60 means
the miss is RANKING, and a re-ranker can reach it. A flat curve would mean the chunk is simply
absent."* From the **real** shipping baseline the test gap is **+0.264** (0.471 → 0.735), not the
`+0.309` this section originally claimed. That is the budget Phase E is trying to collect, and E1
has taken **+0.058** of it.

### Three hard numbers that bound the work

1. **Ceiling: 0.824 on test (14/17), 0.800 on dev (20/25).** Even a perfect re-ranker cannot
   exceed this — 3 test questions have no expected ref anywhere in the top-60 pool. Those need
   corpus or encoder work and are **out of scope for E1–E4**. Do not chase them by widening.
2. **The floor is innocent.** `kept=0` is `0/8 · 0/7 · 0/5 · 0/5` across every answerable class —
   every question already retrieves something, and false refusals are **0/25 dev, 0/17 test**.
   **Phase E must not touch `MIN_SCORE`.** There is nothing wrong with it and D5 re-derived it.
3. **We are barely selecting at all.** Shipping is `k=3/doc` = **9 candidates for 6 slots**. Two
   thirds of everything retrieved is displayed. A "re-ranker" over 9 candidates has almost no
   room to work — widening the pool is a *precondition* for re-ranking, not an alternative to it.

### Where the loss is concentrated

Means by class, dev, corpus v2:

| class | n | recall | precision | kept=0 |
|---|---|---|---|---|
| **vocab-mismatch** | 8 | **0.375** | **0.125** | 0/8 |
| cross-document | 7 | 0.476 | 0.238 | 0/7 |
| toc-trap | 5 | 0.500 | 0.233 | 0/5 |
| odd-wording | 5 | 0.600 | 0.200 | 0/5 |

**The worst class is the one the hand-written synonym map exists to fix.** That was already the
2026-09-13 finding; corpus v2 did not change it.

> **⚠ THE SYNONYM MAP'S ONLY POSITIVE EVIDENCE IS ON THE SET IT WAS FITTED TO.**
> `ablate_v2.txt:15-28` measures expansion on/off across **frozen-10** — the fitted set — and gets
> mean `0.605 → 0.666`, **+0.061**. Inside that mean: **Q9 +0.500, Q8 +0.250, Q2 −0.143**, and six
> questions at `+0.000`. So the map is carried by two questions, actively harms one, and is inert
> on the rest. D5's `SYN:car` finding is the same defect from the other side: expansion
> *manufactured* overlap and top-1'd `Constitution s. 40` on a query about parking.
>
> **The map is a coin flip fitted to 10 points. E3 replaces it, and the replacement must be
> validated on held-out data, never on frozen-10.**

---

## What Phase E will and will not cost

| resource | E1–E4 | E5 decision |
|---|---|---|
| money | **$0** | $0 |
| Gemini quota | **zero calls** | probe only, if taken |
| new runtime dependency | **none** (numpy/scikit-learn already present) | — |
| network on the default path | **none — offline invariant preserved** | would be amended |
| free GPU (Colab/Kaggle) | optional, build-time only for E3/E4 artifacts | — |

**This is the cheapest phase in the project and it targets the weakest measured number.** That
combination is why it runs before Phase G.

---

## Session 0 — how to start (written 2026-09-19, right after the Phase D merge)

Phase D's own first session lost time re-deriving state that nobody had written down. This
section exists so Phase E's does not.

**1. Cut the branch and establish the control.**

```powershell
git checkout main; git pull; git checkout -b phase10/retrieval-quality
C:\conda-envs\drlca-rag\python.exe scripts\eval_heldout.py  > D:\e0_baseline\heldout_v2.txt
C:\conda-envs\drlca-rag\python.exe scripts\eval_chat.py     > D:\e0_baseline\chat_v2.txt
C:\conda-envs\drlca-rag\python.exe scripts\ablate_phase08.py > D:\e0_baseline\ablate_v2.txt
C:\conda-envs\drlca-rag\python.exe scripts\audit_corpus.py  > D:\e0_baseline\audit_v2.txt
C:\conda-envs\drlca-rag\python.exe scripts\calibrate_refusal.py > D:\e0_baseline\refusal_v2.txt
```

These must reproduce `scripts/baseline_v2_2026-09-19.txt` **before any edit**. If they do not,
stop and find out why — that is a finding about the repo, not a nuisance.
**Keep the files on disk, not in a summary.** D6 found a guard that had been failing open only
because D5's raw captures still existed to diff against.

**2. Know what is already false in this playbook.** The amendment box at the top is not optional
reading. `CT4.t3` is out of E1's reach *by construction*, and a contextualised `recall_strict`
gain is **not** self-certifying.

**3. Deploy discipline changed with the merge.** `main` now serves corpus v2 to real users.
Work on `phase10/retrieval-quality`; **never push `main`** without the user asking for that
specific merge. Phase D's authorisation was for Phase D.

**4. Budget.** E1–E4 spend **zero Gemini quota** — there is no reason to touch the API in this
phase at all. If a step seems to need it, that step has drifted out of scope.

**5. Finish each step the way Phase D did:** one arm per commit, ablated on its own, doc hygiene
at session end (`STATUS.md` + this playbook's Results + a dated `LEARNING_JOURNAL.md` entry).
Record declined arms as declined — a losing E4 that is quietly dropped costs the next session the
same experiment.

---

## Steps

### E1 — Separate the three budgets, and measure before changing anything

> **✅ DONE 2026-09-20 — but NOT as specified below. `3d280fb` (E1a, measure-only) + `9748086`
> (E1b, shipped). SHIPPED `k=4/doc, top_n=12`, NOT the `k=20/doc` this step asks for — that arm
> measures `+0.000` on test. See the amendment box in **Results** before reading anything below as
> current. Test strict recall 0.471 → 0.529. Zero Gemini calls.**

Zero quota. **Measure-only first**; no ranking change ships in this step.

Three budgets are conflated under one `top_n` today. `10_corpus_rebuild_and_dense.md` M1 already
made this argument and is absorbed here, **with one sizing correction**:

| budget | now | M1's 2026-09-13 target | **E1 target** | constraint |
|---|---|---|---|---|
| candidate pool | k=3/doc (9) | k=8–10/doc | **k=20/doc (60)** | none, CPU is free |
| chunks in the Gemini prompt | 6 | 10–12, ≤4/doc | 10–12, ≤4/doc | 12 × ~600 chars ≈ 2k tokens vs a 1M context; the free tier caps **calls**, not tokens |
| excerpts on screen | 6 | 3 inline + expander | **already shipped** (Phase 10 C) | screen-reader burden |

> **⚠ WHY k=20/doc AND NOT M1's k=8–10.** M1 was sized before the recall@k curve existed. The
> curve is now measured and it is **not** flat between @20 and @60: test goes `0.559 → 0.735`,
> dev `0.607 → 0.733`. Sizing the pool at 8–10/doc would leave roughly **half the available
> headroom outside the pool**, where no re-ranker can reach it. `eval_heldout.py` already builds
> a k=20/doc pool for its own curve, so this number is not a guess — it is the depth we have
> already proven contains the answers.

**Order within E1, and why:** land the pool width and report `recall@12` on all three sets
**before** any re-ranker exists. A widened pool with today's ordering is a control arm — it
isolates "did widening help by itself" from "did the re-ranker help", and those must not be
measured together in one commit.

**E1 green:** recall@12 reported on frozen-10 / dev / test · false-refusal **not worse** (still
0/25, 0/17) · `MIN_SCORE` untouched · display still 3 inline + expander · suites 03/04/05 green ·
`import app` clean · `requirements.txt` byte-identical.

> **Not in E1's reach:** `CT4.t3` (rank 104 at k=200) — see the amendment box at the top. A
> widened pool is not expected to recover it, and E1 is not failing if it does not.

> **⚠ `scripts/test_phase05.py` ASSERTS ON `app.py`'s SOURCE TEXT and will break by design.**
> Update those assertions in the same commit, never by relaxing them. Same for any
> `k=3`/`top_n=6` constant pinned in `test_phase09_ops.py`.

---

### E2 — BM25 re-rank **inside** the existing gate

> ## ⚠ AMENDED 2026-09-20 (E2a, `measure(phase10-E2a)`). **E2 AS WRITTEN BELOW IS A NO-OP, AND THE MEASURED REPLACEMENT LOST.**
>
> **Code measure-only and DELIBERATELY NOT MERGED** — `scripts/ablate_rerank.py` and its
> `src/retrieve.py` consumers (`bm25=`, `rerank=`, `pool_per_doc`, `pin_top`) live on branch
> `phase10/retrieval-quality` at `a6016e4`, **not on `main`**. Re-run from there; do not rebuild them.
>
> **1. E1b invalidated the STAGE this step acts on.** The text below says *"re-order the
> already-admitted hits by BM25 … re-ranking within the admitted set is a pure ordering change"*.
> At the E1b arm that is **provably inert**, and it is provable by reading the code rather than by
> measuring: `PerDocRetriever.query(q, k=4)` returns 12 candidates, `select_top(hits, 12,
> min_per_doc=1)` fills to `top_n` and therefore returns **all 12**, `select_top` **re-sorts its
> output by score** so it also discards any incoming order, and every recall metric in the repo
> scores a **set** (`eval_heldout.py:215-224`, `ablate_phase10.py:145-147`,
> `eval_phase06.py:286`). Measured anyway as arm `0b`: BM25 re-ordered the displayed chunks on
> **55 of 60 questions** and moved `recall_strict` by **exactly +0.000 on all three sets**, with
> the displayed **set** changed on **0/60**. The only reachable effects are MRR, which chunks land
> inline vs in the fold, and prompt order — and whether prompt order helps generation **cannot be
> measured until Phase G spends quota.**
>
> **2. So the re-rank was moved one stage earlier, to SELECTION — and it did not pay.** Cosine
> still admits a pool per doc; BM25 chooses which `k` of that pool the doc contributes; the doc's
> cosine argmax is pinned in as a refusal guard. That is the only version of E2 that can reach the
> pool headroom. `recall_strict`, corpus v2, every arm showing 12 chunks:
>
> | arm | frozen-10 | dev | **test (clean)** | pool ceiling (test) |
> |---|---|---|---|---|
> | **0 control (= E1b)** | **0.734** | **0.573** | **0.529** | 0.529 |
> | 0b bm25 order-only | 0.734 | 0.573 | 0.529 **(+0.000)** | 0.529 |
> | 1 bm25 pool=10/doc | 0.734 | 0.573 | 0.471 (**−0.059**) | 0.618 |
> | **2 bm25 pool=20/doc (primary)** | 0.734 | 0.573 | **0.471 (−0.059)** | **0.735** |
> | 3 bm25 pool=40/doc | 0.734 | 0.573 | 0.471 (−0.059) | 0.824 |
> | 4 bm25 pool=20, **not pinned** | 0.734 | 0.573 | 0.471 (−0.059) | 0.735 |
> | 5 rrf pool=20/doc | 0.734 | 0.573 | 0.500 (−0.029) | 0.735 |
> | 6 bm25 pool=20, unigrams only | 0.748 | 0.580 | 0.500 (−0.029) | 0.735 |
>
> **No arm gains on any set. `test` loses on every arm that fires.** Corpus v1 corroborates
> (frozen `0.753 → 0.728`, dev `0.533 → 0.520`, test flat) — this is not a v2 artifact.
>
> **Read those with the sample sizes attached: n = 10 / 25 / 17.** One `test` question is worth
> 0.059, so the primary arm's `−0.059` is **two half-questions**, not a trend, and `+0.000` on
> frozen-10 and dev means "nothing crossed a threshold", not "provably zero". What carries the
> verdict is not the size of any single delta — it is that **nine arms across two corpora produced
> no gain anywhere**, plus the mechanism in point 4. A decline on a coin-flip-sized loss would be
> over-reading; a decline on "no arm gains on any set, for a reason that predicts it" is not.
>
> **3. The mechanism FIRED; it just bought nothing.** This is the distinction the table is built
> to make, because "flat" has two very different causes. The primary arm changed the **displayed
> set on 51 of 60 questions** and still moved `0 up / 0 down` on frozen-10 and dev, `0 up / 2 down`
> on test. BM25 is swapping chunks that carry no expected ref, and on two clean questions it swaps
> out one that does.
>
> **4. THE REASON GENERALISES, AND IT IS THE FINDING WORTH CARRYING TO E3/E4.** The `+0.206`
> headroom on test is real and none of it was collected. BM25 is **the same family of signal as
> TF-IDF cosine** — lexical term overlap over the same stemmed (1,2)-gram vocabulary, differing
> only in saturation and length normalisation. Where cosine fails to rank the right chunk into a
> doc's top-4, BM25 fails in the same direction, because the query and the chunk **do not share
> the words**. That is the vocab-mismatch class, and the diagnosis section above already names it
> the worst one (dev recall 0.375, n=8). **The pool headroom is not lexically reachable**, which
> is direct evidence for a *semantic* signal (E4) over further lexical work.
>
> **5. D6's length argument (amendment point 2 at the top of this file) is NOT confirmed.** It
> reasoned that v2's short clause chunks lose to long ones under TF-IDF's length handling, and
> called that "the strongest single piece of evidence in the playbook for doing E2 at all". BM25's
> `b` **is** the length knob, and turning it did not recover the class. The argument may still be
> true about *why* short chunks lose; it is now measured **false** as a prediction that BM25
> recovers them.
>
> **6. The arm is knife-edge on `b`, which is independent evidence against shipping it.** Swept at
> pool=20, `test` reads `0.500 / 0.500 / 0.471 / 0.529` at `b = 0.00 / 0.50 / 0.75 / 1.00` — a
> 0.058 swing, the same size as E1b's entire gain, from a parameter with no principled setting
> here. `b=1.00` is the only value that does not lose, and choosing it because it did not lose is
> exactly how the synonym map was built. **`b` stays at the textbook `0.75` and the arm stays
> declined.**
>
> **7. `max_per_doc`-style depth is inert again, for the second phase running.** Arms 2 and 3
> (pool 20 vs 40) are **identical on every cell of every set** — BM25's top-4 within the first 20
> candidates is its top-4 within the first 40. Pool depth beyond 20 contributes nothing, which is
> the selection-stage restatement of E1a's "pool width is inert once `top_n == 3k`".
>
> **8. The refusal guard cost nothing and is kept anyway.** Arm 4 drops the pin and produced **0
> false refusals** and a **bit-identical top-score vector** on all 60 questions. That prices the
> pin at zero *here*; it does not make it safe to drop, because the pin is what makes the
> invariance a **proof** rather than an observation, on questions nobody has measured.
>
> **VERDICT: E2 IS DECLINED, not deferred.** The code is committed and measurable **on
> `phase10/retrieval-quality` at `a6016e4`** (`src/retrieve.py`, `rerank` defaults to `None`;
> `scripts/ablate_rerank.py`) so the next session does not re-run the experiment — but it was
> **deliberately NOT merged to `main`**, because it is inert on the shipping path and would ship in
> the Render image for no runtime purpose. **Nothing on the shipping path moved and nothing should.**
> Full detail in **Results**.

Zero quota. This is `09_evidence_and_generation.md` step 3(a), unchanged in substance.

Keep cosine scoring and `MIN_SCORE` exactly as the **admission gate**, then re-order the
already-admitted hits by BM25. Implement inline over the existing vectorizer (~30 lines, **zero
new packages** — do not add `rank_bm25`).

> **⚠ RE-RANK WITHIN THE ADMITTED SET, NEVER REPLACE THE SCORER.** BM25 scores are unbounded and
> not comparable to cosine. Swapping the scorer outright would silently invalidate the
> calibration at `src/retrieve.py:26-44` and **change refusal behaviour**. Re-ranking within the
> admitted set is a pure ordering change: it cannot create or destroy a refusal. D5's
> `calibrate_refusal.py` is the proof harness — **re-run it after E2 and it must still report 0
> disagreements.**

**Why BM25 specifically, and why now.** TF-IDF cosine handles two things badly that our corpus
now does aggressively: **term saturation** (a chunk repeating "disability" ten times is not ten
times more relevant) and **length normalisation**. After Phase D the chunk-length spread is
`ACT_V2_SIZE = 1100` against `CONST_SIZE = 400` — a **2.75×** spread. BM25's `k1`/`b` parameters
exist precisely for those two effects. This is the highest-confidence item in the playbook.

**E2 green:** held-out `recall_strict` **is the real result** (on the *naive* arm — see amendment
box point 3: a contextualised `strict` gain can still be a packed-chunk artifact) ·
frozen-10 `recall_strict` not
worse · precision still never gated (0.333 is by design — see `CLAUDE.md`) ·
`calibrate_refusal.py` still 0 disagreements · ablated **separately from E1** so the two gains
are attributable.

---

### E3 — Replace the hand-written synonym map with a corpus-derived one

> ## ⚠ AMENDED 2026-09-20 (E3a, `measure(phase10-E3a)`). **THE AUTO MAP LOSES ON EVERY SET AND MAKES ITS OWN TARGET CLASS WORSE. E3 SHIPS NOTHING.**
>
> **Code measure-only and DELIBERATELY NOT MERGED** — `scripts/build_synonyms.py`,
> `scripts/ablate_synonyms.py`, both `data/processed/synonyms_auto*.json` artifacts and their
> `src/retrieve.py` consumers (`load_auto_synonyms()`, `auto_terms()`, `expand_query_auto()`) live on
> branch `phase10/retrieval-quality` at `a6016e4`, **not on `main`**. Re-run from there; do not
> rebuild them.
>
> Four arms, budget fixed at E1b's `k=4/doc, top_n=12`, `recall_strict`, corpus v2
> (`scripts/ablate_synonyms.py`; map from `scripts/build_synonyms.py`, PPMI + truncated SVD over
> term-chunk co-occurrence, **built without reading `data/eval/questions.json`**):
>
> | arm | frozen-10 (fitted) | **dev (SELECTOR)** | test (check) |
> |---|---|---|---|
> | **A hand map (control = E1b)** | **0.734** | **0.573** | **0.529** |
> | B auto map (corpus-derived) | 0.601 (−0.133) | 0.387 (**−0.187**) | 0.382 (−0.147) |
> | C **no expansion at all** | 0.634 (−0.100) | 0.500 (−0.073) | **0.588 (+0.059)** |
> | D hand ∪ auto | 0.702 (−0.032) | 0.440 (−0.133) | 0.382 (−0.147) |
>
> **1. Arm B is declined on evidence that is not close.** It loses on all three v2 sets and, on the
> per-question breakdown, **gains not one single question anywhere**: `0 up / 3 down` on frozen-10,
> `0 up / 7 down` on dev, `0 up / 3 down` on test — **0 up / 13 down across 52 answerable rows.** A
> loss that never once wins is not a tuning problem.
>
> **2. It made the class it exists to fix WORSE, by half.** Pooled `vocab-mismatch` strict (n=18)
> falls **0.479 → 0.229**. Per set: `0.562/0.500/0.438` → `0.312/0.312/0.125`. This is the specific
> class E3 was justified on and the one E4's ship gate reads.
>
> **3. It fired hard, so this is dilution, not inertness.** Post-gate, the auto map expanded
> **58/60** questions (the hand map expands 32/60) and changed the displayed set on **59/60**,
> appending a **median 8** terms — i.e. saturating `AUTO_MAX_TERMS` on nearly every query. The hand
> map appends a median 4 to about half as many questions. **Expansion MASS, not expansion quality,
> is the dominant effect**, and the mechanism that "adds terms the query lacks" is the same one that
> buries the terms it has.
>
> **4. Why a corpus-derived map cannot be rescued by better parameters.** Chunk-level co-occurrence
> over a corpus that is **2037 of 2134 chunks Constitution** yields topical association within
> constitutional register — `penalty → complaint, award, level, runs, week, revoke`. And the keys a
> user actually needs are structurally unreachable: **6 of the 34 hand keys — `fined`, `fired`,
> `jail`, `job`, `lawyer`, `sack` — do not occur in the corpus at all**, and 11 more fall below the
> a priori `min_df`/length filters. Those six are exactly the user-register bridges ("can they sack
> me" → "terminate the employment of"). **No corpus-derived generator emits them at any parameter
> setting.** Arm D exists precisely to test whether restoring them rescues the method: it does not
> (dev −0.133, test −0.147).
>
> **5. Arm C is the real finding, and it is a genuine dev/test disagreement — not a win for either
> side.** `C − A` is **−0.100 / −0.073 / +0.059** on v2 and **−0.100 / −0.047 / +0.088** on v1:
> **the same sign on every set across both corpora.** Read it honestly:
> * frozen-10's −0.100 is **not evidence**. That is the set the hand map was fitted to; it is
>   measuring memorisation, which is the whole reason `evalset.py` exists.
> * dev (n=25) favours the hand map by 0.073 ≈ **1.8 questions**.
> * test (n=17), **the only clean set left**, favours *no expansion* by 0.059 = **exactly 1
>   question**.
>
> Both live inside sampling noise. **The declared rule — dev selects, test checks — keeps the hand
> map, and so does the tie-break that a change to the shipping path requires positive evidence and
> there is none.** But record the weaker statement plainly: **after two sessions we still have no
> held-out evidence that the hand map is worth having**, and the one uncontaminated set says the
> opposite. That is an E5 item, not something to settle on 17 questions.
>
> **6. What this hands to E4, including the uncomfortable half.** This is the **second consecutive
> phase** in which a term-level lexical signal failed to reach the `+0.206` pool headroom — E2a
> because BM25 only reweights terms the query has, E3a because adding associated terms dilutes
> faster than it bridges. E3a was supposed to be the arm that *could* cross vocabulary mismatch
> without a semantic model; it crossed nothing and cost 0.187 on the selector. **That is evidence
> for E4's semantic arm and evidence against it at the same time**: a static-embedding blend is also
> term-level association, and it will append or re-weight on the same principle that just failed
> twice. **E4's ship gate should be strict, and E4 should be prepared to be declined.**
>
> **VERDICT: E3 IS DECLINED IN FULL — B, C and D all stay off; `SYNONYMS` and `expand_query` are
> unchanged.** The generator, the artifact, the opt-in consumer and the harness are committed **on
> `phase10/retrieval-quality` at `a6016e4`** so nobody re-runs the experiment — but they were
> **deliberately NOT merged to `main`**: the two JSON artifacts alone are **36,636 lines** that
> would ship in the Render image for no runtime purpose. **Nothing on the shipping path moved.**
> Full detail in **Results**.

Zero quota at runtime. Build-time may use free Colab.

`09_evidence_and_generation.md` step 3(b), with the evidence above sharpening it. Compute term
neighbours from the **corpus itself** (co-occurrence / PMI, or embeddings built offline on free
Colab), filter to legal vocabulary, ship `data/processed/synonyms_auto.json`. Runtime cost is a
dict lookup. The two-sided expansion entry gate in `src/retrieve.py` **stays exactly as is**.

> **⚠ BUILD IT WITHOUT LOOKING AT THE EVAL QUESTIONS. This is the whole point.**
> The hand map was built by keeping and deleting entries according to their effect on
> Q5/Q7/Q8/Q9 — which is why frozen-10 read 0.925 and held-out read 0.420. If the automatic map
> is tuned the same way, we will have spent the effort and learned nothing. Derive it from corpus
> text only; validate **once**, on held-out data; report whatever it says.

> **⚠ SHIP IT ONLY IF IT BEATS THE HAND MAP ON HELD-OUT DATA — and be willing to ship NEITHER.**
> Given `ablate_v2.txt` (+0.061 on the fitted set, `−0.143` on Q2, inert on 6/10) plus `SYN:car`,
> **"expansion off entirely" is a legitimate third arm** and must be measured alongside A (hand
> map) and B (auto map). Do not assume expansion is worth having.

**E3 green:** three-arm ablation (hand / auto / none) on dev **and** test · the winner reported
with its held-out number, not its frozen-10 number · `SYN:car`-class bare-key flips re-checked
via `calibrate_refusal.py` · whichever arm wins, the decision recorded with its evidence.

---

### E4 — Static-embedding re-rank signal (candidate, measure before committing)

> ## ⚠ AMENDED 2026-09-20 (after E2a and E3a). **E4 AS WRITTEN BELOW IS INERT AT THE SHIPPING BUDGET. RE-SCOPE IT BEFORE RUNNING IT.**
>
> **1. The step's stated mechanism — "one signal in the re-rank score" — cannot move any number we
> publish.** This is E2a's finding applied verbatim: at E1b's `k=4/doc, top_n=12`, `top_n == 3k`, so
> `select_top` returns **every** candidate retrieved *and* re-sorts by score; every recall metric in
> the repo scores a **set**. E2a measured exactly this as arm `0b` — the displayed order changed on
> 55/60 questions and `recall_strict` moved **+0.000 on all three sets**. A static-embedding
> *re-rank* is the same shape and will measure the same way. **Do not spend a session re-deriving
> this.**
>
> **2. To fire, a re-rank must become SELECTION over a wider pool — and that is the arm E2a already
> measured and LOST** (`test` 0.529 → 0.471, no gain on any set, same on v1). So "E4 = E2 with a
> different score function" is not a plan; it inherits a stage that has already been shown to cost
> questions.
>
> **3. What E4 genuinely has that E3 structurally could not — and it is not re-ranking.** E3a's
> decisive finding was that **6 of the 34 hand keys (`sack`, `fired`, `jail`, `job`, `lawyer`,
> `fined`) never occur in the corpus at all**, so no corpus-derived generator emits them at any
> parameter setting — and those six are exactly the user-register bridges. A **pretrained** static
> table was trained on general English and *does* contain them. That is a real difference in kind,
> and it sits on the **expansion** side, not the ranking side.
>
> **So E4's live mechanism is external-vector query EXPANSION, not a re-rank signal** — nearest
> neighbours of the query's out-of-corpus terms, mapped into corpus vocabulary, feeding the
> existing `expand_query` stage. Under that reading `data/processed/` gains a **pruned vocabulary +
> vector artifact**, not a re-ranker, and the "BLEND, NEVER REPLACE" box below still applies (blend
> against the hand map, do not replace it). **E4 must be re-specified this way before it is run, or
> declined cheaply.**
>
> **4. Set the ship gate strict, and expect to decline.** E3a is the **second consecutive phase**
> where a term-level lexical signal failed to reach the `+0.206` pool headroom, and E3a was
> supposed to be the arm that differed in kind. A static-embedding blend is **also term-level
> association**. E3a additionally showed the failure mode to watch for: the auto map was not inert
> but **dilutive** — it fired on 58/60 questions and *halved* `vocab-mismatch` recall
> (0.479 → 0.229). **Any E4 arm must report the `vocab-mismatch` class specifically and must win on
> held-out `test`, not merely avoid losing.**

Zero quota, zero network, **no new runtime dependency**. This step is **optional and
evidence-gated** — it ships only if E2/E3 leave vocab-mismatch still the worst class.

The gap nothing else in this playbook closes is **semantic** matching: a user who writes "can
they sack me" against a corpus that says "terminate the employment of". BM25 is still lexical;
corpus-derived synonyms are still term-level.

**The idea:** *static* word embeddings (GloVe/fastText-style) are a matrix lookup plus a
mean-pool — **pure numpy**, which is already present via scikit-learn. A vocabulary pruned to the
corpus plus common legal terms is roughly **10–20k terms × 100 dims in float16 ≈ 2–4 MB**: it
fits in the repo, fits in Render's 512 MB, loads at boot, and runs fully offline.

> **⚠ THIS IS NOT "DENSE RETRIEVAL". Do not let it become M2 by increments.**
> No transformer, no ONNX, no torch, no FAISS, no network. If an implementation starts needing
> any of those, it has left this step and must stop — `requirements.txt` is the constraint that
> makes the whole app deployable on the free tier.

> **⚠ BLEND, NEVER REPLACE.** Static embeddings are *weak on exact legal terminology*, which is
> the one thing our lexical arm is good at — "section 34" and "section 43" have near-identical
> static vectors. Use it as one signal in the re-rank score alongside BM25, with the weight
> chosen on **dev only**, and ablate it as its own arm. If it does not beat E2+E3 on held-out
> data, **do not ship it** — a 4 MB artifact and a blend weight are real complexity.

**E4 green:** ablated as its own arm against E2+E3 · vocab-mismatch class recall reported
specifically · shipped only on a held-out win · `requirements.txt` still byte-identical.

---

### E5 — Re-baseline, then decide about M2 with evidence instead of ambition

Zero quota to re-baseline.

Publish the full sweep on corpus v2 with all shipped E-arms on: recall + `recall_strict` per set,
recall@k curve, MRR, false-refusal, per class. Archive `scripts/baseline_phaseE_<date>.txt`.
**`test` is read once, at the end.** A disappointing number is the finding.

Then, and only then, make the **M2 decision** (`10_corpus_rebuild_and_dense.md` M2, dense
retrieval via Gemini embeddings).

> **⚠ M2's PREMISE IS INTACT — IT IS THE PRICE THAT NEEDS RE-EXAMINING.**
> M2 is **not** superseded and this playbook does not supersede it. It already handles the
> query-side problem honestly: embed the query at tier 1, cache on the normalised query string,
> fall back through tiers, ship a visible notice that the question is sent to Google, ship a
> hard-offline toggle, and **amend `CLAUDE.md`'s offline invariant in the same commit**. That is
> a deliberate, documented trade, not an oversight.
>
> **What has changed is that we can now price it.** Three things must be on the table before M2
> is scheduled:
> 1. **Its quota premise is still unmeasured.** `scripts/probe_embed_quota.py` has never run.
>    Free-tier embedding limits are unpublished. M2 cannot be costed until it does — and the
>    probe is cheap, so run the probe even if M2 is declined.
> 2. **The privacy cost is real and specific to this population.** M2's own text records that the
>    questions describe *disability, abuse and begging coercion*. Sending them to a third party is
>    a different decision here than it would be for a generic search box.
> 3. **The residual gain may be small.** If E1–E4 land near the 0.824 in-pool ceiling, M2 is
>    buying the *absent* 3/17 — which dense retrieval may not reach either, because those refs are
>    missing from the pool, not mis-ranked.
>
> **Decide with the E5 numbers in hand. Record the decision either way, with its reasoning.**

---

## What free tier genuinely blocks — so nobody re-derives this

- **Query-time transformer inference is out.** Any dense arm must embed the *incoming query*.
  Prebuilt chunk vectors do not solve this. That needs a model in `requirements.txt` (ONNX/torch
  — forbidden; Render free instances are 512 MB) or a network call per query (breaks the offline
  invariant and is quota-bound). This is why `08_retrieval_upgrades.md` steps 4/5 are superseded,
  and the reasoning still holds.
- **Phase F (free-GPU fine-tune, `10_corpus_rebuild_and_dense.md` M4) is standing on the same
  wall and must be re-examined before it is scheduled.** Colab gives free *training*; it does not
  give free *serving*. A fine-tuned transformer still cannot run at query time under
  `requirements.txt`. **The one variant that survives the constraint is fine-tuning a static
  embedding table** (E4's artifact), which is pure numpy at serving time. If F is kept, that is
  probably what it should become.
- **Generation quality cannot be improved without quota.** The answer-shape floor and the
  `reverse_rel` fix (`09_evidence_and_generation.md` step 4) are Phase G work, paced by the
  20/day/model cap.

---

## Traps

- **Do not touch `MIN_SCORE`.** D5 re-derived it against v2 and it did not move. The floor is not
  the problem here; `kept=0` is 0 across every answerable class. The floor **may move down on
  evidence and may never move up** — `calibrate_refusal.py` gate 3 enforces this.
- **Do not gate or "fix" precision 0.333.** It is a designed consequence of `PerDocRetriever`
  merging top-k per doc. See `CLAUDE.md`.
- **Do not tune on frozen-10.** It is the fitted set; D5 showed it was the *only* set that got
  worse under v2 (strict `0.701 → 0.633`) while dev and test improved. It is a regression
  tripwire, not a target.
- **Do not tune on `chat_test`.** It is the last blind set in the project. If chat thresholds
  need to move, author a new set first — see `12_corpus_v2.md` D6.
- **One arm per commit.** E1, E2, E3 and E4 must each be ablatable on their own. A combined
  commit produces a number nobody can attribute, which is how the synonym map got shipped in the
  first place.
- **Insertion order breaks ties** in `PerDocRetriever` (`src/retrieve.py:331-338`). Any change to
  candidate ordering must not silently reorder the `docs` dict in `build_corpus()`.
- **`eval_phase06.py` must still hash `CE716FB3…5F19` under `CORPUS_VERSION="v1"`** — v2/E output
  goes to a new `--out=` path (**equals form only**).

---

## Exit criteria

1. **Held-out `test` strict recall reported, once, at the end**, with every arm attributable.
   The honest target is meaningful movement off **0.471** toward the **0.824** ceiling; a number
   below that is a finding to record, not to tune away.
2. **False refusals still 0/25 and 0/17**, and `calibrate_refusal.py` still 0 disagreements.
3. **`MIN_SCORE` still `0.10`.**
4. **`requirements.txt` byte-identical**, no new runtime dependency, default path still fully
   offline with zero network calls.
5. **Every arm ablated separately**, with its own held-out number, and the losing arms recorded
   as declined rather than quietly dropped.
6. **The M2 decision made and written down**, with `probe_embed_quota.py` actually run.
7. `scripts/baseline_phaseE_<date>.txt` archived, and 03/04/05/09 suites green.

---

## Results

### Session 0 + E1 — 2026-09-20. Zero Gemini calls.

Branch `phase10/retrieval-quality` cut from `main` at `1ee6ea9`. Commits: **`3d280fb`** (E1a,
measure-only) · **`9748086`** (E1b, the shipping flip).

**Session 0 control: REPRODUCES.** All five harnesses re-captured to `D:\e0_baseline\` before the
first edit and diffed against `scripts/baseline_v2_2026-09-19.txt`: `audit_corpus` (153 lines),
`eval_heldout` (151), `eval_chat` (218), `ablate_phase08` (71) and `eval_phase06` (31) are
**byte-identical** to the archived sections. `eval_phase06`'s only difference is the `--out` path it
prints; the sha256 digest matched. `calibrate_refusal` has no archived counterpart (it postdates the
archive) and was captured fresh: PASS, 0/212 disagreements.

**HEADLINE: held-out `test` strict recall 0.471 → 0.529 (+0.058); dev 0.473 → 0.573 (+0.100);
frozen-10 0.633 → 0.734.** False refusals still **0/10 · 0/25 · 0/17**. `MIN_SCORE` untouched at
`0.10`. `requirements.txt` byte-identical. `audit_corpus` stdout byte-identical (the corpus was not
touched). Exit criterion 1's "meaningful movement off 0.471 toward the 0.824 ceiling" is **22% of
the available headroom**, from one number.

> ### ⚠ THIS PLAYBOOK'S E1 SIZING WAS WRONG, AND TWO OF ITS PUBLISHED NUMBERS WERE MISLABELLED
>
> **1. `k=20/doc` buys nothing. The knob is `top_n == 3k`.** E1 above specifies a 60-candidate pool
> plus a prompt budget of "10–12, ≤4/doc". Measured (`ablate_phase10.py`, recall_strict):
>
> | arm | frozen10 | dev | test | shown | Act share of slots |
> |---|---|---|---|---|---|
> | ship `k=3 n=6` | 0.633 | 0.473 | 0.471 | 6 | 36% |
> | `k=10 n=6` | 0.622 | 0.453 | **0.426** | 6 | 28% |
> | **`k=20 n=12` (this playbook's arm)** | 0.698 | 0.527 | **0.471 = +0.000** | 12 | 25% |
> | **`k=4 n=12` (SHIPPED)** | **0.734** | **0.573** | **0.529** | 12 | 33% |
> | `k=5 n=15` | 0.748 | 0.587 | 0.529 | 15 | 33% |
> | `k=6 n=18` (**declined**) | 0.748 | 0.587 | 0.559 | 18 | 33% |
>
> `k=20 n=12` and `k=4 n=12` both show 12 chunks, so they are comparable, and the playbook's arm
> gains **+0.000 on test**. The whole difference is per-doc allocation, not pool depth.
>
> **2. Widening the pool at an unchanged budget is a REGRESSION on all three sets.** `k=10 n=6`
> isolates it: 0.633/0.473/0.471 → 0.622/0.453/**0.426**. The extra slots go to the global top,
> which the Constitution (2037 of 2134 chunks) owns — the Act's share of displayed chunks falls
> 36% → 28% → 25% as the pool widens. **This is the flooding `PerDocRetriever` exists to prevent,
> re-introduced by widening**; `min_per_doc=1` is too weak a guarantee at 30–60 candidates.
> The section "We are barely selecting at all… widening the pool is a *precondition* for
> re-ranking" is therefore **half right**: widening is fine, widening *without fixing the
> allocation* is harmful, and that distinction is not in the text above.
>
> **3. `max_per_doc` is UNNECESSARY.** A per-doc ceiling was prototyped. `k=20/doc capped at
> ≤4/doc` is **bit-identical to plain `k=4/doc, top_n=12`** on every cell of every set — within a
> doc, global score order *is* that doc's own order, so each doc's best 4 of 20 is its best 4 of 4.
> `k=8` and `k=20` capped at 4 both reproduce `k=4 n=12` exactly. E1 shipped **one number** and no
> new `select_top` parameter.
>
> **4. The diagnosis table above mislabels the curve as shipping.** Its `r@6` column is headed
> "**r@6 (shipping)**" and reads test **0.426**. That is the **recall@k CURVE** row, not the
> shipping arm. `eval_heldout.py:128-131` warns against exactly this quote: the curve builds
> `select_top(top_n=60)` over 60 candidates, so its quota phase is **vacuous** and its `@6` has no
> `min_per_doc` reservation. **Shipping test recall was 0.471.** The `+0.309` gap in "The problem is
> RANKING" is therefore **+0.264** from the real baseline. Exit criterion 1 already said 0.471, so
> the playbook contradicted itself; the criterion was right.
>
> **5. `MIN_SCORE` cannot be reached by this class of change, and that is now measured.** The
> top-score vector is **byte-identical from k=3 to k=20** and the refused-row count never moves, so
> **neither `k` nor `top_n` can create or destroy a refusal.** `ablate_phase08`'s off-corpus top
> scores are identical digit-for-digit before and after E1b; only hit counts moved. E2 does not get
> this for free — it re-orders, which is still refusal-invariant, but it must re-run
> `calibrate_refusal.py` as the playbook already requires.

**`k=6 n=18` is DECLINED, not dropped.** frozen-10 and dev plateau at `k=5` (0.748/0.587); only
test keeps climbing (0.529 → 0.559). Paying **6 more excerpt cards** of screen-reader burden for a
gain visible on one set is not a trade this project takes — accessibility is a requirement, not
polish. Recorded so the next session does not re-run the experiment.

**The gain is not the eval set's prior.** Every `top_n == 3k` arm allocates 4/4/4, so the obvious
objection is that an even split just matches the set's shape. It does not: expected refs run
**~50% Act / ~20% Constitution / ~30% Factsheet** (frozen 59/8/33, dev 50/25/25, test 47/15/38).
The even split **under-serves the Act**, which owns half the answers. `ablate_phase10.py` prints
this distribution so the check is in output, not prose. And the gain replicates on **test**, never
tuned against. *Corollary worth having, and it is a fit-risk not a free win:* an Act-weighted
allocation would probably score higher still, but choosing weights against these numbers is fitting
to the eval set's doc prior. If it is ever tried, it belongs in E5 with a declared fit-risk and a
test-set-only validation.

**Two baselines were deliberately re-pinned, and both tightened.** `FROZEN10_STRICT_BASELINE_V2`
`0.632738 → 0.733928` (the truncated true float `0.7339285714285714`, **not** the printed `0.734` —
`eval_heldout.py:155-165` warns why) and `ablate_phase08.ABLATE_MIN_STRICT_V2` likewise. The second
was not in the brief; it was taken because that file's own comment reserved the edit for Phase E and
a stale tripwire would let a revert of E1b pass silently. Both old values are kept in comments
recording that **E1's budget moved them, not a corpus change**. `eval_phase06`'s two digests moved
too — `V2 10751076… → 2429cafc…`, `V1 ce716fb3… → 12bdeba0…` — and the old v1 digest was proven
still reproducible by running the **pre-commit code at the old budget** in a throwaway worktree.
Only the instrument moved.

**Controls that held.** `eval_heldout`'s RECALL@K CURVE block is **numerically identical** before
and after (`K_CURVE=20` untouched by design); only its generated caption changed.
`calibrate_refusal` 0/212 disagreements and all three gates PASS. `audit_corpus`, `test_phase03`,
`test_phase09_ops` and `bench_phase01` stdout byte-identical. `test_phase05` **137/137, with no
assertion edited** — the source-text asserts survived because they assert `>= 1`, not `== 6`.
`import app` clean. Suites 03/04/05/09 green.

> **⚠ READ THE `eval_chat` GAINS WITH THE AMENDMENT BOX AT THE TOP OF THIS FILE.** `chat_dev` ctx
> 0.607 → 0.786 and `chat_test` ctx 0.571 → 0.714 are **not self-certifying**: amendment point 3
> says `recall_strict` does not neutralise the packed-ref subsidy in the `ctx` arm, and Phase B's
> gates are computed on `chat_dev`, the tuning set. Two things make the direction credible anyway —
> `chat_test`'s ellipsis class moved off the flat `0.000 → 0.000` that D6 recorded, to
> `0.000 → 0.333` on the **blind** set, and the change is justified independently by the
> single-turn held-out `test` gain. But **a budget that shows twice as many chunks inflates any
> recall-shaped metric by construction**, so E1b's load-bearing evidence is the `test` column, not
> these. Do not quote the chat deltas as E1's result.

**Recorded as moved, not fixed:** context precision falls **0.333 → 0.217**. This is arithmetic —
the same relevant chunks over twice the shown chunks — and `CLAUDE.md` says precision is by design
and must never be gated. What is stale is the **figure** `0.333` quoted in `CLAUDE.md`, not the
design point; corrected in place there. `eval_phase06`'s frozen-10 recall gate still reads
**FAIL (0.734 vs >0.75)** and was left unrelaxed.

**Not done in this session, and outstanding for E5 / later:** `probe_embed_quota.py` still has
**never been run** (exit criterion 6), `scripts/baseline_phaseE_<date>.txt` is not yet archived
(criterion 7 — E5 owns it), and the **12-card fold has not been eyeballed in a browser**. No
harness measures that, and it is the one user-facing part of E1b: each assistant turn now renders
3 inline + **9** behind one `expanded=False` fold. Read-aloud speaks only the answer, so it is
unaffected; default tab/screen-reader burden is unchanged because the fold stays collapsed.

**Also found: `scripts/ablate_phase10.py` had apparently never been run.** It is a committed
measure-only width-ablation harness, absent from `CLAUDE.md`'s harness list and from the Phase D
baseline archive, and it is exactly E1's instrument. It ran clean first time and reproduced the
scratch probe on every shared arm. E1a extended it with the no-cut ladder and two new output blocks
(displayed-chunks-per-doc, and the expected-ref prior check). **It is now in `CLAUDE.md`'s list.**

### E2a — 2026-09-20. Zero Gemini calls. **MEASURE-ONLY: nothing on the shipping path moved.**

> **Code measure-only and DELIBERATELY NOT MERGED** — `scripts/ablate_rerank.py`,
> `scripts/build_synonyms.py`, `scripts/ablate_synonyms.py` and their `src/retrieve.py` consumers
> live on branch `phase10/retrieval-quality` at `a6016e4`. Re-run from there; do not rebuild them.

Commit **`measure(phase10-E2a)`** on `phase10/retrieval-quality`. One source file
(`src/retrieve.py`, opt-in and default-off), one new harness (`scripts/ablate_rerank.py`), the E2
amendment box above. `src/rag.py` and `app.py` were **not edited in this session**.

**HEADLINE: BM25 buys nothing here, and the reason is that it is the wrong family of signal.**
No arm gains on any set; every arm that fires loses on the clean `test` set. **E2 is DECLINED.**
The full arm table, the `b` sweep and the seven supporting findings are in the amendment box on
the E2 step above — they are recorded there rather than only here so that a reader of the *step*
cannot act on the superseded text.

**The harness validates itself three independent ways, and this matters more than any arm row.**
A negative result is only worth recording if the instrument is trustworthy, so
`scripts/ablate_rerank.py` was built to be checkable against numbers it did not produce:

1. **Arm 0 (control) reproduces E1b exactly** — 0.734 / 0.573 / 0.529, gated in the script
   (`CONTROL_STRICT`) and printed PASS/PASS/PASS. If it failed, no other row would mean anything.
2. **Arm 2's pool ceiling equals the published `rs@60`** — 0.904 / 0.733 / 0.735, matching
   `scripts/baseline_v2_2026-09-19.txt:278-281` to three decimals. At pool=20/doc the candidate
   set **is** `eval_heldout.py`'s 60-candidate curve pool, so this is a cross-harness check that
   E2a's pool is the pool the ceiling was measured on.
3. **Arm 3's pool ceiling equals the "3 questions absent" ceiling** — test **0.824**, the exact
   number "Three hard numbers that bound the work" #1 records as 14/17. A pool of 40/doc finds
   everything findable.

**The `b` gate is corpus-aware, and that is a deliberate correction made during the session.** The
first version compared `--corpus=v1` against `CONTROL_STRICT`, which is a v2 number, and exited
nonzero for a correct run. It now gates on v2 and merely prints on v1 — the same
one-baseline-per-corpus rule `eval_heldout.py`'s frozen-10 guard follows.

**What moved in `src/retrieve.py`, and what did not.** `TfidfRetriever` gained `bm25: bool =
False` (default off, so `scripts/bench_phase01.py`'s direct construction and raw-cosine asserts are
untouched) and an Okapi BM25 index built over the **reused TF-IDF vocabulary** — identical term
space by construction, not by coincidence, and zero new packages. `PerDocRetriever` gained
`rerank=None, pool_per_doc=20, pin_top=True` plus the three BM25 knobs. **`Hit.score` is still
cosine in every arm**: BM25 chooses, cosine scores, orders and gates, so the calibration block at
`src/retrieve.py:26-93` is untouched by construction rather than by argument. `MIN_SCORE` is still
`0.10`.

**"The only new output in the repo is the new harness's" — verified by diff, not by assertion.**
Captured to `D:\e2_baseline\` **before the first edit** and re-run after:
`eval_heldout`, `ablate_phase10`, `bench_phase01`, `audit_corpus`, `ablate_phase08`, `eval_chat`,
`calibrate_refusal` and `test_phase09_ops` are **stdout byte-identical**. `test_phase05` differs
only in Streamlit's timestamped bare-mode warning (137/137 either way). `eval_phase06` differs only
in the `--out=` path it echoes; **the digest is identical** (`2429cafc…`). `calibrate_refusal`
**PASS, 0/212 disagreements**. `import app` clean, no server. `git diff main -- requirements.txt`
empty.

**Cost of the index, recorded now for a ship decision that did not happen.** `bm25=True` adds
**1.5 MB** (count matrix + idf + doc lengths across all three docs) and **+0.9 s** to corpus build.
Render free is 512 MB, so cost was never the blocker — **the absence of a gain was.**

**What E2a hands to E3/E4, and it is the useful half of a negative result.** The `+0.206` test
headroom to the pool ceiling is untouched and is now known to be **not lexically reachable**: two
different lexical rankings over the same vocabulary (TF-IDF cosine, BM25) and a rank fusion of them
(RRF) all fail on the same questions. E4's static-embedding blend is the arm that addresses the
actual mechanism; **E3 should be read with this in mind too**, since a corpus-derived synonym map
is also term-level and the "three-arm ablation including *no expansion*" is the part of E3 most
likely to be informative.

**Declined, recorded, not dropped:** the ordering-only arm (`0b`, +0.000 by construction), pool
depths 10 / 20 / 40, the unpinned variant, RRF, and unigram-only BM25. All seven live in
`scripts/ablate_rerank.py:ARMS` and re-run in about a minute.

### E3a — 2026-09-20. Zero Gemini calls. **MEASURE-ONLY: nothing on the shipping path moved.**

> **Code measure-only and DELIBERATELY NOT MERGED** — `scripts/ablate_rerank.py`,
> `scripts/build_synonyms.py`, `scripts/ablate_synonyms.py` and their `src/retrieve.py` consumers
> live on branch `phase10/retrieval-quality` at `a6016e4`. Re-run from there; do not rebuild them.

Commit **`measure(phase10-E3a)`** on `phase10/retrieval-quality`. One source file
(`src/retrieve.py`, opt-in and default-off), two new scripts (`scripts/build_synonyms.py`,
`scripts/ablate_synonyms.py`), two artifacts (`data/processed/synonyms_auto.json` and its v1 twin),
the E3 amendment box above. `src/rag.py` and `app.py` were **not edited in this session**.

**HEADLINE: the corpus-derived map loses on every set, never wins a single question, and halves
the recall of the exact class it was built to fix. E3 ships nothing.** The arm table, the
structural reason a corpus-derived generator cannot reach the user register, and the arm C
dev/test disagreement are in the amendment box on the E3 step above — recorded there rather than
only here so that a reader of the *step* cannot act on the superseded text.

**THE ONE RULE THIS STEP EXISTED TO RESPECT, AND HOW IT WAS ENFORCED.** The playbook's warning was
that the hand map was curated by its effect on Q1–Q10, so building the automatic one the same way
would spend the effort and learn nothing. `scripts/build_synonyms.py` **never reads
`data/eval/questions.json`**, and every filter is declared a priori with a stated principle that
does not mention a metric — `min_df=5` (fewer occurrences give no usable co-occurrence
statistics), `max_df=0.20` (drops `person`/`act`/`section`/`shall` boilerplate, otherwise
everyone's nearest neighbour), alphabetic and `len>=4` (numbers are citation refs), 4 neighbours
per key (the hand map's own median), `min_cos=0.50` (weak keys emit **nothing** rather than noise).
None was moved after seeing a result. **The map was built once and measured once**, which is what
makes the −0.187 on dev believable rather than an artifact of a bad draw.

**The harness validates itself at BOTH ends, and the second check caught a real bug.** Arm A must
reproduce E1b (0.734 / 0.573 / 0.529) *and* arm C must reproduce `ablate_phase08.py`'s
independently published expansion-off figure on frozen-10 (**0.634**, printed by that script as
`MEAN 0.634 -> 0.734 (strict)` since Phase 08). Both are gated in-script on v2 and print
PASS. Checking only arm A would not have been enough: the draft of this harness computed each arm's
effective query correctly but then called `ret.query()`, which resolves `expand_query` as a module
global — so it measured the **shipping map four times while printing four different arm labels**,
and the arm A check passed perfectly throughout. The arm is now swapped by monkeypatching
`retrieve.expand_query` (the technique `ablate_phase08.py:118-149` already uses), restored in a
`finally`.

**The firing rate is POST-GATE, and that distinction is load-bearing.** `PerDocRetriever.query()`
scores the original query first and discards an expansion that cannot clear `MIN_SCORE`, so a
pre-gate count would overstate every arm. Measured post-gate: hand **32/60**, auto **58/60**, union
**59/60**, none 0/60. Terms appended, median/max: hand 4/12, auto 8/8 (**saturating the cap on
nearly every query**), union 11/19.

**`AUTO_MAX_TERMS = 8` is a declared cap, not a tuned one.** It was fixed before measuring, and the
harness reports map size and firing rate as first-class columns precisely so dilution is **priced
rather than dialled out**. The auto map has **1063 keys / 3952 terms** against the hand map's **34 /
121** — ~30× — because it covers the whole corpus vocabulary rather than 34 curated user-register
words. That size *is* the finding; lowering the cap or raising `min_cos` until the number improved
would have been the fitted-map mistake with a new name.

**Corpus v1 corroborates, which is what rules out a v2 artifact.** `C − A` is `−0.100 / −0.047 /
+0.088` on v1 against `−0.100 / −0.073 / +0.059` on v2 — **the same sign on every set**. Arm B on
v1: `0.582 / 0.293 / 0.412`, i.e. −0.171 / −0.240 on the fitted and selector sets. The v1 auto map
(1102 keys) is built and committed, so `--corpus=v1` reproduces from this commit.

**What moved in `src/retrieve.py`, and what deliberately did not.** Added: `AUTO_MAX_TERMS`,
`auto_synonyms_path()`, `load_auto_synonyms()` (lazy, cached, returns `{}` when the artifact is
absent so a checkout without it behaves exactly as today), `auto_terms()` and `expand_query_auto()`
— which mirrors `expand_query`'s contract exactly (original query plus appended terms, never a
replacement; deterministic; deduped; capped). **Not touched: `SYNONYMS`, `expand_query`, and the
two-sided gate in `PerDocRetriever.query()`.** Leaving `SYNONYMS` alone is what keeps
`calibrate_refusal.py` at exactly **106 probes / 212 runs** with byte-identical output, since
`calibrate_refusal.py:150` builds 34 of its probes from that map's keys. Leaving the gate alone is
what makes refusal invariance hold for *any* map: **0 false refusals in all four arms**, which is a
property of the gate rather than of the map's contents.

**"The only new output in the repo is the new harness's" — verified by diff, not by assertion.**
Captured to `D:\e3_baseline\` **before the first edit** and re-run after: `eval_heldout`,
`ablate_phase10`, `ablate_phase08`, `bench_phase01`, `audit_corpus`, `eval_chat`,
`calibrate_refusal` and `test_phase09_ops` are **stdout byte-identical**. `ablate_rerank` differs
in **two lines, both wall-clock** (`build time: bm25 off 0.88s -> on 1.44s`); no metric moved.
`test_phase05` differs only in Streamlit's timestamped bare-mode warning (**137/137** either way).
`eval_phase06` differs only in the `--out=` path it echoes; **digest identical**
(`2429cafc…`). `calibrate_refusal` **PASS, 0/212**. `test_phase09_ops` **ALL PASS**. `import app`
clean, no server. `MIN_SCORE` still `0.10`. `git diff main -- requirements.txt` empty.
`scripts/eval_tmp.json` left untracked.

**The generator is deterministic, checked rather than claimed.** Two consecutive runs produced a
byte-identical file (sha256 `3F6E9B77…`). SVD `random_state` is fixed, neighbour ties break on the
term string, keys are written sorted, and `_meta.built` — the one field that would otherwise move
across days — is **preserved from the existing file whenever the corpus sha256 is unchanged**, so
it records when the map was derived rather than when the script last ran.

**Declined, recorded, not dropped:** the auto map (arm B), the union (arm D), and no-expansion
(arm C). All four arms live in `scripts/ablate_synonyms.py:make_arms` and re-run in about a minute
on either corpus.
