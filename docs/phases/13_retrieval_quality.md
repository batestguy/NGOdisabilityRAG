# Phase E — retrieval quality: close the ranking gap, spend nothing

**Status:** **ACTIVE** as of 2026-09-19 — planned, not yet started. Zero Gemini quota for E1–E4.
**Runs after:** Phase D (`12_corpus_v2.md`) — **COMPLETE, MERGED to `main` and DEPLOYED
2026-09-19 (`8682869`).** `CORPUS_VERSION = "v2"` is the default **and is what users are now
getting**, which changes one thing about this phase: it is no longer working on a side corpus.
**Every E arm that lands on `main` reaches real users on the next push.**
**Branch:** `phase10/retrieval-quality`, cut from `main` at `8682869`.

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

| set | r@3 | **r@6 (shipping)** | r@10 | r@20 | **r@60** | MRR | med-rk | found in pool |
|---|---|---|---|---|---|---|---|---|
| frozen-10 (fitted on) | 0.512 | 0.655 | 0.684 | 0.713 | 0.904 | 0.925 | 1 | 10/10 |
| dev (n=25) | 0.373 | 0.440 | 0.527 | 0.607 | 0.733 | 0.435 | 2 | 20/25 |
| **test (clean, n=17)** | 0.324 | **0.426** | 0.441 | 0.559 | **0.735** | 0.400 | 3 | **14/17** |

`eval_heldout.py` prints the interpretation rule itself: *"A large gap between @6 and @60 means
the miss is RANKING, and a re-ranker can reach it. A flat curve would mean the chunk is simply
absent."* The test gap is **+0.309**. That is the budget Phase E is trying to collect.

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

*(nothing executed yet — Phase E is planned as of 2026-09-19)*
