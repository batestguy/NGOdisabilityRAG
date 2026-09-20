# HANDOFF — start here (60 seconds, updated 2026-09-20)

> **LATEST (2026-09-20): PHASE E SESSION 0 + E1 ARE DONE. NEXT IS E2. Zero Gemini calls —
> today's spend is 0, and the whole of E1 spent 0.**
>
> Branch **`phase10/retrieval-quality`**, cut from `main` at `1ee6ea9`. **`3d280fb`** (E1a,
> measure-only) + **`9748086`** (E1b, shipped). **Unmerged and unpushed on purpose** — pushing
> `main` auto-deploys to real users and that call is the user's. Phase D's authorisation does
> **not** carry forward.
>
> **HEADLINE: held-out `test` strict recall `0.471 → 0.529` (+0.058), dev `0.473 → 0.573`,
> frozen-10 `0.633 → 0.734`.** False refusals still **0/10 · 0/25 · 0/17**. `MIN_SCORE` untouched.
> `requirements.txt` byte-identical. `audit_corpus` stdout byte-identical. **Session 0's control
> REPRODUCED** against `scripts/baseline_v2_2026-09-19.txt` before the first edit; raw captures are
> in `D:\e0_baseline\` and should stay there until E5 archives its own baseline.
>
> **⚠ E1 DID NOT SHIP WHAT THE PLAYBOOK SPECIFIED, AND THAT IS THE THING TO KNOW BEFORE E2.**
> The playbook's arm is `k=20/doc` (60 candidates). Measured, **it gains `+0.000` on test.** What
> gained `+0.058` was **`k=4/doc, top_n=12`**. Both show 12 chunks, so they are comparable, and the
> entire difference is **per-doc allocation, not pool depth**. Widening the pool at an unchanged
> budget is a **regression on all three sets** (`k=10 n=6`: 0.633/0.473/0.471 → 0.622/0.453/0.426),
> because the spare slots go to the global top and the Constitution owns it — the Act's share of
> displayed chunks falls **36% → 28% → 25%**. That is the flooding `PerDocRetriever` exists to
> prevent, re-introduced by widening. **The knob is `top_n == 3k`**: then `select_top` returns every
> candidate retrieved and the invalid cross-doc cosine cut never discards anything. A `max_per_doc`
> ceiling was prototyped and is **bit-identical to plain `k=4/doc`** — **it was not added.**
>
> **TWO PLAYBOOK NUMBERS WERE MISLABELLED AND ARE CORRECTED IN PLACE.** Its diagnosis table heads a
> column **"r@6 (shipping)"** reading test **0.426** — that is the **recall@k CURVE**, whose
> `select_top(top_n=60)` over 60 candidates makes the quota phase vacuous, so its `@6` has **no
> `min_per_doc` reservation**. **Shipping was 0.471.** The `+0.309` gap is really **+0.264**. Exit
> criterion 1 always said 0.471, so the playbook contradicted itself.
>
> **DO NOT QUOTE THE `eval_chat` GAINS AS E1's RESULT** (`chat_dev` ctx 0.607 → 0.786). **A budget
> showing twice as many chunks inflates any recall-shaped metric by construction**, D6's amendment
> says `recall_strict` does not neutralise the packed-ref subsidy in the `ctx` arm, and the Phase B
> gates are computed on `chat_dev`, the tuning set. **E1b's load-bearing evidence is the single-turn
> held-out `test` column.**
>
> **Re-pinned deliberately, all tightening, old values kept in comments:**
> `FROZEN10_STRICT_BASELINE_V2` `0.632738 → 0.733928` (the **truncated true float**, never the
> printed `0.734` — see `eval_heldout.py:155-165`), `ablate_phase08.ABLATE_MIN_STRICT_V2` likewise,
> and `eval_phase06`'s two digests (`V2 → 2429cafc…`, `V1 → 12bdeba0…`). The old v1 digest was
> proven still reproducible by running the **pre-commit code at the old budget** in a throwaway
> worktree — only the instrument moved.
>
> **NOT DONE, carry forward:** the **12-card fold has never been seen in a browser** (3 inline + 9
> behind one collapsed fold — no harness measures it, and it is E1b's only user-facing change) ·
> `probe_embed_quota.py` still **never run** · `scripts/baseline_phaseE_<date>.txt` not archived
> (E5 owns it) · **Phase G's prompt cost per legal turn has doubled** — confirm it fits *before* G
> spends its ~30 calls.
>
> **NEXT: E2 — BM25 re-rank INSIDE the existing gate**, never replacing the scorer. D6's length
> finding is its direct evidence (v2 clause chunks run to ~305 chars and lose to long ones under
> TF-IDF's length handling). **Re-run `calibrate_refusal.py` after it — it must still report 0
> disagreements.** E1's refusal invariance does **not** transfer for free: E1 was safe because the
> top-score vector is byte-identical from k=3 to k=20, which is a property of selection *depth*.

> **(2026-09-19, MERGED + DEPLOYED): PHASE D IS SHIPPED. PHASE E IS ACTIVE.**
>
> **`phase10/corpus-v2` merged to `main` as `8682869` on the user's explicit instruction, and
> Render auto-deployed it.** 25 commits, D0–D6. **The `[Act cl. 39]` mis-citation — cl.38's tail
> served to users under clause 39's number — was live in the deployed app from 2026-09-10 to
> 2026-09-19. It is fixed in production now.** Corpus v2 is what users get.
>
> **Verified BEFORE the push, not after** (which is the point of doing it in that order):
> `import app` clean · `audit_corpus` PASS · `test_phase03/04` ALL PASS · `test_phase05` 137/137 ·
> `test_phase09_ops` ALL PASS · `requirements.txt` **byte-identical to `main`'s** · **no
> OCR/ONNX/FAISS import anywhere in `src/`** · the v2 Act ships as committed JSON
> (`data/processed/act2018_v2_clauses.json`), so **nothing is re-OCRed at boot** · merged tree
> byte-identical to the branch tip. Full battery in the merge commit message.
>
> ⚠ **DEPLOY RULE, RESTATED BECAUSE IT JUST CHANGED IN PRACTICE:** pushing `main` ships to real
> users. **Phase D's merge was authorised for Phase D.** That authorisation does **not** carry
> forward — every future merge needs its own explicit go-ahead. Work Phase E on
> `phase10/retrieval-quality`.
>
> **NEXT: PHASE E — `docs/phases/13_retrieval_quality.md`**, which now opens with a **Session 0**
> section: cut the branch off `main`, re-capture the five baselines to `D:\e0_baseline\` and
> confirm they reproduce `scripts/baseline_v2_2026-09-19.txt` *before* editing anything, then E1.
> **Zero Gemini quota for E1–E4.** Two D6 findings bind on it and sit in that playbook's
> amendment box — read them before judging E1: `CT4.t3` is at **rank 104 at k=200**, i.e. outside
> the 60-candidate pool, so **E1's widening cannot reach it**; and **`recall_strict` does not
> neutralise the packed-ref subsidy in the `ctx` arm** (it corrects scoring, not retrieval).
> Order stays **E → G → F**; **G needs a multi-day quota plan before its first call.**
>
> Today's Gemini spend: **0 calls.** Phase D spent **0 across the entire phase**.

> **(2026-09-19, D6 EXECUTED): PHASE D IS COMPLETE. `CORPUS_VERSION = "v2"` IS THE
> DEFAULT.** Seven commits `02f42f8` → `5838beb` on `phase10/corpus-v2`. **Zero Gemini calls.**
> All five harnesses green on v2 (`scripts/baseline_v2_2026-09-19.txt`). **Superseded by the
> banner above: the branch is now merged and deployed.**
>
> **WHAT SHIPS WITH THE FLIP:** the Act's clause 38, absent from v1's text entirely because the v1
> scan records one physical page twice, and an end to cl.38's tail being served under an
> `[Act cl. 39]` tag. **That citation-integrity defect is live in `main` until this branch merges.**
>
> **THREE FINDINGS, in descending order of how much they change what you believe:**
>
> **1. The eval set was scoring turns correct against mis-attributed law.** `CT2.t2` and `CT2.t3`
> expect `act2018:[8]`, authored off v1's `[Act cl. 8]` chunk — which **carried clause SEVEN's
> subsection (3)** (the officer-approval offence). v2 files that text under `[Act cl. 7]`, where it
> belongs. **Same defect class as the `[Act cl. 39]` bug, found inside the eval set.** Both turns
> are `"status": "retired-v2"` — retired, *not* edited; correcting `[8]` to `[7]` would convert a
> blind turn into one authored against v2.
>
> **2. `chat_test`'s "ellipsis collapse" was v1's number being unearned, not v2 degrading.** The
> premise D6 was handed — gain class `+0.400 → 0.000`, harness green, regression hidden — is
> **inverted**. Three turns carried that whole gain; all three v1 hits are artifacts (two from the
> falsified ground truth above, one from `CT4.t3` scoring because a **packed** `cl. 25,26,27` chunk
> held its *neighbours'* words, "queue" and "accommodation", that contextualisation carried in).
> On the 3 surviving turns: v1 `0.000 → 0.333`, v2 `0.000 → 0.000` — and that 0.333 *is* the
> artifact. **Ellipsis gain on the blind set is zero on both corpora.**
>
> ⚠ **Consequence worth carrying forward: `recall_strict` does NOT neutralise the packed subsidy
> in the `ctx` arm.** It stops one chunk satisfying two expected refs (scoring); it cannot see a
> chunk *retrieved* because of text belonging to a different clause. D5's "strict == plain,
> therefore not the packed subsidy" inference is wrong for the retrieval side.
>
> **3. A guard had been failing open, and D5 published its output.** `eval_heldout.py:438` asserts
> the run is on v1 because plain recall is not comparable across corpus versions — but it read the
> module constant, so `--corpus=v2` saw `"v1"` and let it through. D5's
> `frozen-10 recall 0.666 vs recorded baseline 0.925 (corpus v1): FAIL` is **a v2 number against a
> v1 baseline, labelled v1, by the guard written to refuse exactly that.** The strict comparison
> (0.701 → 0.633) is the legitimate one. Every gate now has a v2 arm on a legitimate metric, each
> printing the metric it does not gate.
>
> **HANDED TO PHASE E, by name:** `CT4.t3` — cl.25 is **outside the 60-candidate pool entirely**
> (rank 104 at k=200), so **E1's `k=20/doc` widening does not reach it**; know that before judging
> E1. The mechanism is length — v2's clause-aligned chunks are short (305 chars) and TF-IDF's
> length handling works against them, which is **E2's BM25 rationale with direct evidence behind
> it** · `CT1.t1` — refusal fixed, ranking not (rank 20 → 22) · `chat_test`'s ellipsis class is
> **thin at 3 scoreable turns** · the Phase B gates are **still computed on `chat_dev`**, so
> `eval_chat` exits PASS while `chat_test` reads `GAIN CLASS DID NOT IMPROVE` — **that critique
> stands**, untouched by D6 on purpose.
>
> **NEXT: Phase E — `docs/phases/13_retrieval_quality.md`, unchanged and now unblocked.**

---

> **(2026-09-19, earlier): PHASE E IS PLANNED AND SPECIFIED — `docs/phases/13_retrieval_quality.md`
> is NEW and is the consolidated retrieval playbook. Nothing executed; docs only, zero quota.**
>
> **WHY THIS EXISTS: the legal Q&A path is the app's weak half, and the data says exactly why.**
> Held-out `test` (clean, never tuned, n=17) on corpus v2 reads **r@6 = 0.426 shipping** against
> **r@60 = 0.735 in the pool** — a **+0.309 gap** the user never sees. `eval_heldout.py` prints
> the interpretation rule itself: a large @6-to-@60 gap means the miss is **RANKING**, and a
> re-ranker can reach it. Three facts bound the work:
> 1. **Ceiling 0.824** (test found 14/17 in pool at all). 3 questions are genuinely absent —
>    corpus/encoder work, out of E1–E4's scope. Do not chase them by widening.
> 2. **The floor is innocent.** `kept=0` is 0 across every answerable class; false refusals are
>    **0/25 dev, 0/17 test**. **Phase E must not touch `MIN_SCORE`.**
> 3. **We barely select at all** — shipping is `k=3/doc` = **9 candidates for 6 slots**. Widening
>    the pool is a *precondition* for re-ranking, not an alternative.
>
> **Worst class is vocab-mismatch (dev recall 0.375, n=8) — the class the hand-written synonym
> map exists to fix.** `ablate_v2.txt` prices that map at **+0.061 mean on frozen-10, the set it
> was fitted to**, carried by Q9 (+0.500) and Q8 (+0.250), **harmful on Q2 (−0.143)**, inert on
> 6/10. With D5's `SYN:car`, **"expansion off entirely" is now a legitimate third arm.**
>
> **THE PLAN, in order, all $0 and zero Gemini quota:** **E1** separate the three budgets and
> widen the candidate pool to `k=20/doc`, **measure-only first** so widening is a control arm ·
> **E2** BM25 re-rank **inside** the existing gate (never replacing the scorer — that would move
> refusal behaviour) · **E3** replace the hand synonym map with a corpus-derived one, built
> **without looking at the eval questions**, three-arm ablation incl. *no expansion* · **E4**
> optional pure-numpy **static** embedding blend for the semantic gap (**not** dense retrieval —
> no ONNX/torch/FAISS/network, or it has left the step) · **E5** re-baseline, then decide M2.
> **One arm per commit** — a combined commit produces a number nobody can attribute, which is how
> the synonym map shipped in the first place.
>
> **M2 (dense via Gemini embeddings) is GATED, NOT REJECTED.** Its premises were re-checked and
> they hold — it already owns the query-side trade honestly (tiered fallback, privacy notice,
> hard-offline toggle, offline invariant amended in the same commit). But
> `scripts/probe_embed_quota.py` **has never run**, so it cannot be costed; the privacy cost is
> specific to a population asking about abuse and coercion; and E1–E4 target the same headroom.
> **Run the probe regardless; decide with E5's numbers.**
>
> **PHASE F (M4) NEEDS RE-EXAMINING BEFORE IT IS SCHEDULED.** Colab gives free *training*, not
> free *serving* — a fine-tuned transformer still cannot embed a query at request time under
> `requirements.txt`. The variant that survives is fine-tuning a **static** table (E4's artifact).
>
> **ORDER CHANGED: E → G → F.** This reverses the G-before-E call taken earlier the same day, on
> resource grounds: **E costs zero quota and improves the system; G costs ~30 calls — most of a
> day's free budget — and only measures it.** Judging first spends the scarce resource on a system
> about to change. AI prose is opt-in and defaults OFF, so unmeasured drift is not reaching users.
> The earlier decision is kept in `LEARNING_JOURNAL.md`, not erased.
>
> **NEXT: finish D6 first** (below), then Phase E.
>
> ---
>
> **Previous (2026-09-19, later still): D6 is PLANNED AND SPECIFIED — NOT STARTED. Nothing was
> executed.** Docs-only session, zero Gemini calls, **no `src/`, no `scripts/`, no `data/`
> touched.** Branch **`phase10/corpus-v2`**, still unmerged on purpose.
>
> **Read `docs/phases/12_corpus_v2.md` § D6 before touching anything** — it now carries the
> premises box, the order of operations, the blast radius, the gate checklist and the exit
> criteria. This banner is the index, that is the spec.
>
> **THREE PREMISES CORRECTED, all by diffing `D:\d5_baseline\chat_v1.txt` against `chat_v2.txt`.**
>
> **(1) The stamp bug is FIVE sites, not one.** D5 recorded `eval_heldout.py:438`. It is also
> **`eval_heldout.py:244`, `:373`** and **`eval_chat.py:344`, `:411`**. `chat_v2.txt` prints
> `CORPUS_VERSION=v2` on line 1 and `(corpus=v1, …)` on **`:10`, `:110`, `:197`** of the same
> file. The fix is the `(corpus or CORPUS_VERSION)` form already used at `eval_heldout.py:341`
> and `eval_chat.py:371`. **It must land BEFORE the `CORPUS_VERSION` flip** — while the constant
> is still `"v1"` the fix is provable (v2 tables flip, v1 run stays byte-identical); after the
> flip both readings are `v2` and the proof is gone forever.
>
> **(2) `eval_chat --corpus=v2` exits PASS, and that is the problem — DO NOT READ THAT PASS AS
> PERMISSION TO FLIP.** All 51 refs verify and the Phase B gates are computed on **`chat_dev`**,
> the tuning set, which still passes. Underneath, on the **blind** set, `chat_test`'s ellipsis
> gain class collapses **`0.200 → 0.600` (v1) to `0.000 → 0.000` (v2)** (`:146` in both files),
> pronoun becomes the gain class instead (`:150`), and the headline delta falls
> **`+0.130 → +0.043`** (`:200`). The `strict` columns are identical to the plain ones throughout,
> so this is a **real ranking move, not the packed-ref subsidy**. Sharpest instance:
> `chat_dev`'s pronoun row keeps a **byte-identical `+0.143` delta** while its level falls
> `0.571 → 0.143` (`:55`) — **a gate phrased on a delta cannot see the level move underneath it.**
>
> **(3) Two playbook predictions came true** — confirm, don't re-guess. `CT1.t1`'s
> `<-- FALSE REFUSAL` marker is at `chat_v1.txt:112` and **absent** at `chat_v2.txt:112` (recall
> still `0.000` — refusal fixed, ranking not). `CT7.t2` goes **`0.000 → 1.000`** (`:130`): the
> "unscoreable, not missed" turn is now scoreable.
>
> **PLUS ONE GAP: v2 has no content tripwire.** `V1_CORPUS_SHA256` is pinned at
> `audit_corpus.py:141` and checked at `:586-597`; there is no v2 equivalent, so after the flip
> the **shipping** corpus would be less protected than the retired one. **Add `V2_CORPUS_SHA256`
> in the same commit as the flip.**
>
> **`D:\d5_baseline\` IS THE LIVE "BEFORE" SET — DIFF IT BEFORE THE FIRST EDIT.** 18 stdout
> captures, v1 and v2 arms for every suite (`chat_*`, `heldout_*`, `audit_*`, `ablate_*`, `bench`,
> `ops`, `p03`–`p06`). It is **outside the repo and not backed up by git**; all three findings
> above exist only because it was kept on disk rather than summarised into prose. Do not delete
> it until D6 has archived `scripts/baseline_v2_<date>.txt`.
>
> **BLAST RADIUS, so the flip is not silent.** `app.py:458`, `scripts/test_phase05.py:73` and
> `scripts/test_phase09_ops.py:218` all call `build_corpus()` with **no argument**, plus
> `src/rag.py:642` (`ask()`'s own fallback). Flipping `src/rag.py:48` changes what those suites
> test with no announcement. **Any assert that fails there is a FINDING, not a number to relax.**
>
> **REPO STATE.** `f4b02d6` is HEAD of `phase10/corpus-v2`, pushed. Working tree clean except
> **`scripts/eval_tmp.json`, untracked scratch that stays untracked**. `main` untouched; **the
> branch stays unmerged** — merging auto-deploys a half-built corpus to Render.
>
> **NEXT: D6** (zero quota) — see the playbook checklist. **THEN PHASE G, NOT E — decision taken
> this session. `CLAUDE.md` is CORRECTED to `D6 → G → E → F` in the same commit** (dated in-place
> note; the still-true "D before E is load-bearing" line kept, since D → G → E satisfies it).
>
> **⚠ THE G-BEFORE-E HALF OF THIS WAS REVERSED LATER THE SAME DAY — see the LATEST banner at the
> top. The order is now `D6 → E → G → F`.** Kept here rather than edited, because the reasoning
> is the record: G-before-E was argued on "G is the only phase that measures what a user actually
> reads", which is true but makes *measurement* the priority; the reversal is on resource grounds
> (E is free and improves the system, G spends most of a day's quota and only measures it).
> **"D6 first" is unchanged and still correct.**
> G (judge + fresh transcripts + `cross_turn_drift`) goes first because it is **the only thing
> that measures what a user actually reads**; E tunes retrieval that no generated answer has yet
> been scored against. `cross_turn_drift()` has been wired and unmeasured since Phase 10 B
> (`chat_v2.txt:210-212`: *"STRUCTURALLY UNAVAILABLE here — it needs a generated answer"*).
> **G NEEDS A MULTI-DAY QUOTA PLAN BEFORE IT STARTS:** free tier is **20/day/model AND
> 10/minute/model**, with `gemini-2.5-flash` and `gemini-2.5-flash-lite` on **separate pools** →
> a real budget of **40/day**. The judge run alone is **~30**, so it does **not** fit in one day
> on one model. Plan the split (across both pools, and/or across two days) *before* spending the
> first call — a half-finished judge run is wasted quota.
>
> **`CLAUDE.md`'s quota section was wrong about this and is fixed in the same commit.** It read
> *"20 calls/day/model (`gemini-2.5-flash`)"*, naming one model and **under-counting the budget by
> half**. `docs/phases/11_chat.md:31-36` had flagged it stale since Phase 10 B and assigned the fix
> to Phase G; it is discharged early because G's first task is exactly the run that cannot be
> planned against the wrong number.
>
> ---
>
> **Previous (2026-09-19, later): D5 is DONE — the refusal floor was RE-DERIVED against v2 and
> `MIN_SCORE` DID NOT MOVE.** Zero Gemini calls spent. Branch **`phase10/corpus-v2`** (still
> unmerged on purpose).
>
> **The hazard D5 exists to catch did not materialise.** False refusals are **0/10 · 0/25 · 0/17**
> on frozen10/dev/test under **both** corpora. v2 is marginally *better* on the false-answer side
> (H25 0.1032 → refused, one fewer off-corpus row clearing the floor). The in-corpus/off-corpus
> band is still **INVERTED on both** (v2: weakest in-corpus 0.1209 vs strongest off-corpus 0.4195),
> so **`MIN_SCORE` stays `0.10`** — and no value above it would buy semantic discrimination
> anyway; that is the strict-prompt `NO_ANSWER_SENTENCE` layer's job.
>
> **The playbook's escape hatch (a second frozen v1 index for the answer/refuse decision) is
> DECLINED** — its trigger is "only if a false refusal appears", and none did across 52 answerable
> rows × 2 corpora.
>
> **NEW FILE: `scripts/calibrate_refusal.py`** — the battery `src/retrieve.py` asked for by name.
> 106 probes (60 eval rows + 12 `OFF_CORPUS` + 34 bare `SYNONYMS` keys, all **imported**, never
> copied) × both corpus versions, built in **one process**, zero network, **writes no files**.
> Refusal invariance: **212 probe-runs, 0 disagreements** — which retires the "a run nobody can
> reproduce" caveat that had sat in `src/retrieve.py` since 2026-09-13.
>
> **All three gates are negative-tested by injection** (`--negative-test`), and one result is
> reported honestly rather than glossed: **gate 1's prescribed injection cannot falsify it.**
> `floor=0.0` into `select_top` leaves invariance intact, because the global max is in the output
> at *every* floor. Gate 1 is proven live instead by a mutant selector that drops the global max
> (2 disagreements). Gates 2 (v2 floor → 0.30, **asymmetric** on purpose) and 3 (`MIN_SCORE` →
> 0.11) both fire. **Do not re-litigate this in D6.**
>
> **NO BEHAVIOUR CHANGED.** One new script + three comment blocks (`src/retrieve.py`'s calibration
> block and merge caveat, `src/rag.py`'s three deferral notes). The v1 sweep is **stdout
> byte-identical** — `eval_heldout`, `ablate_phase08`, `audit_corpus`, `eval_chat`, both arms —
> `eval_phase06` still `ce716fb3…5f19`, 137/137 · 51/51 · 16/16+7/7 · 10/10 · bench PASS.
> **The v2 arms still exit 1 for the recorded reasons; D5 made nothing pass.**
>
> **TWO FINDINGS HANDED TO D6** (full detail in `docs/phases/12_corpus_v2.md`, "Handed to D6"):
> **(1) `eval_heldout.py:438` reads the WRONG VARIABLE** — `assert CORPUS_VERSION == "v1"` tests
> the module constant, not the effective `--corpus=` value, so it **never fires** and the run trips
> the recall guard it was written to pre-empt. Same bug mislabels the stamp: a v2 run prints
> `(corpus v1)`. **(2) `SYN:car` is the only v1→v2 refusal flip and is NOT a false refusal** —
> v1 "answered" it with **Constitution s. 40** via expansion manufacturing overlap; v2 refuses and
> its best bare hit is the *correct* chunk. Real sentences improve. **Do not lower `MIN_SCORE` for
> it.**
>
> **REPO STATE, so you can trust `git status` on a cold start.** D2 `06a326a` · D3 `6a5f5d9` ·
> D4 `866db21` · **D5 `6c4a308` (feat) + this doc commit**, all **pushed** to
> `origin/phase10/corpus-v2`. Working tree clean except **`scripts/eval_tmp.json`, which is
> untracked scratch and should stay that way** — it is the `--out=` target of `eval_phase06.py` and
> pre-dates these sessions. Do not commit it. `main` is untouched; **the branch stays unmerged on
> purpose until D6** — merging auto-deploys a half-built corpus to Render.
>
> **NEXT: D6 — re-baseline, zero quota.** Flip `CORPUS_VERSION` to `"v2"`, keep the v1 tripwire
> runnable, re-scope `audit_corpus.py`'s two recorded FAILs (factsheet `packed` → `row_spanning`,
> Constitution `general` ≤1%), fix `eval_heldout.py:438` per the finding above, re-scope
> `ablate_phase08`'s `recall>0.75` gate, and DELETE `ACT_KNOWN_ABSENT` (not empty it).
>
> ---
>
> **Previous (2026-09-19): D4 is DONE — the Constitution's Arrangement of Sections is
> excluded, and ALL THREE DOCS ARE NOW v2.** Zero Gemini calls spent. Branch
> **`phase10/corpus-v2`** (still unmerged on purpose).
>
> **`audit_corpus.py --corpus=v2` on the Constitution: 2037 chunks · `general` 34 (1.67%) ·
> `toc_general` OUTSIDE Chapter VIII **0** · inventory **8 unnumbered + 26 Chapter VIII** · 0 over
> cap (400).** v1 carried **2104 chunks, 99 uncitable (4.71%), 7 `toc_general` outside Ch VIII.**
>
> **READ THIS BEFORE WRITING D6's GATE. `general ≈0` was UNREACHABLE and measurement said so —
> the SECOND phase running where a target written before measurement was aimed at the wrong
> thing.** Arrangement exclusion is the *whole* of the available fix (99 → 34) and **1.67% is the
> floor**. The residual 34 is **8 structurally unnumbered** chunks (Preamble ×2, six chapter
> dividers) plus **26 Chapter VIII Schedule / Enforcement-Procedure-Rules items**, where `general`
> is the **correct** ref — a Schedule **item** number is not a **section** number, and labelling
> `8. Census` as `s. 8` re-creates the Q10 misattribution class on purpose. **Deleting the
> Schedules to pass the gate is forbidden**: the Second Schedule is operative law and the Rules are
> how a PWD enforces Chapter IV.
>
> **`V2_MAX_GENERAL_PCT` was NOT touched.** `--corpus=v2` still prints
> `constitution1999 uncitable 1.7% <= 1.0%: FAIL` with the reason underneath, and **still exits 1**
> — now on the Constitution *and* the factsheet's `packed 16`. **D6 owns both.** The honest fix for
> the 26 is a citable `Sch. N item M` ref, which is a **fourth numbering scheme** → **Phase E**.
>
> **THE CUT POINT WOULD HAVE SILENTLY EATEN THE PREAMBLE.** Chapters I–VIII appear **twice** in
> `constitution_1999_NHRC.txt`. The naive cut is the body's second `Chapter I` (char 18,535) — and
> the real Preamble (*"We the people of the Federal Republic of Nigeria … Do hereby make, enact and
> give to ourselves the following Constitution:-"*, char **17,917**, 616 chars) sits **between** the
> two. Cut@2nd-Chapter-I gives a *better-looking* `general` count (2035 / 32) bought by deleting the
> enacting words. **Cut at the Preamble: 2037 / 34.** `CONST_PREAMBLE_RE` is asserted to match
> **exactly once** and the cut asserted to separate the two chapter runs — a silent fallback would
> rebuild v1 under a v2 label and the gate would "pass" for the wrong reason.
>
> **D4 CURES THE Q10 CLASS AT SOURCE.** The re-scoped metric `toc_general` (measured from each
> emitted chunk's **text**, never from construction) scores **v1 7 outside Ch VIII, v2 0** — and the
> 7th v1 chunk is the Q10 trap itself, `Chapter IV §39: "ion from fundamental human rights. 46
> Special jurisdiction of High Court and Legal aid."`. That chunk now **ceases to exist**;
> `_is_toc_fragment` only ever relabelled it. **The heuristic is KEPT** and is now the *instrument*
> that proves the cure held — deleting it removes the proof and restores the class.
>
> **The change is narrower than it sounds: 2035 of v2's 2037 chunks are byte-identical in
> `(ref, text)` to v1's last 2035.** The only two that differ are the Preamble, which in v1 was
> mislabelled `Constitution, Chapter VIII - Federal Capital Territory…` (it sat inside the
> Arrangement's Ch VIII block) and is now `Constitution, Preamble:`. **`CONST_SIZE` does not move
> and there is no `CONST_V2_SIZE`** — D4 replaces the *region*, not the text, not the splitter, not
> the ref shape. **Coverage: 318 sections reachable before, 318 after, set difference empty both
> ways.**
>
> **The excluded 3.44% carries no operative text, measured:** 690 non-empty lines, **zero**
> containing `shall`, longest line 14 words.
>
> **`audit_corpus.py`'s v1 stdout is re-baselined by 37 diff entries** (the new `toc-gen` column +
> legend + the `CONSTITUTION general INVENTORY` section, printed for **both** versions so v1's 7 is
> available as proof the metric can fail). **Every pre-existing v1 number is unchanged**,
> `corpus_sha256` still `25650238…e89a`, `eval_phase06` still `ce716fb3…5f19`.
>
> **Recorded, not fixed: `eval_heldout --corpus=v2` and `ablate_phase08 --corpus=v2` exit 1**
> (frozen-10 recall 0.666 vs the pinned v1 0.925). **This pre-dates D4** — re-verified identical at
> `6a5f5d9`. ~~D5 (refusal floor) and D6 (re-baseline) own it.~~ **D5 DIAGNOSED it and handed it to
> D6: the cause is `eval_heldout.py:438` reading the module constant instead of the effective
> `--corpus=` value, so its v1-only assert never fires and the recall guard trips instead. D5 did
> not fix it — see the LATEST banner.** Direction of travel is good: held-out
> 0.420 → 0.473, test 0.338 → 0.471, `eval_chat --corpus=v2` answers 19/23 vs D3's 18/23 (one fewer
> refusal). **Nothing was tuned against those numbers.**
>
> **REPO STATE, so you can trust `git status` on a cold start.** D2 `06a326a` · D3 `6a5f5d9` ·
> **D4 `866db21`**, all **pushed** to `origin/phase10/corpus-v2`. Working tree clean except
> **`scripts/eval_tmp.json`, which is untracked scratch and should stay that way** — it is the
> `--out=` target of `eval_phase06.py` and pre-dates these sessions. Do not commit it, and do not
> mistake it for work-in-progress. `main` is untouched; the branch is unmerged on purpose until D6.
>
> **`_const_chunks_v2()`'s two guards ARE empirically negative-tested — 2026-09-19, by review,
> not merely by reading.** This is stronger than what the D4 results section claims, which
> deliberately described only designed behaviour. Three degradation modes were injected against
> **mutated copies in a temp dir (the real TXT was never touched)** and **all three raise**:
> duplicated Preamble marker → `ValueError` *"matched 2 times"*; deleted marker → *"matched 0
> times"*; marker relocated ahead of the first `Chapter` heading (clears guard 1, must fail guard
> 2) → *"cut … is not between the two chapter runs"*. **None silently falls back to a v1-shaped
> corpus**, which was the failure that would have let the gate pass for the wrong reason. Treat
> this as settled; do not re-litigate it in D5/D6.
>
> ~~**NEXT: D5 — the refusal floor, MANDATORY.**~~ **DONE 2026-09-19 — see the LATEST banner.**
> D5 re-derived the calibration table at `src/retrieve.py:26-44` against v2 and gated on
> `false_refusal_v2 ≤ false_refusal_v1`. **Outcome: `MIN_SCORE` did NOT move — it stays `0.10`.**
> The rule is unchanged and now machine-enforced by `calibrate_refusal.py` gate 3: **it may move
> down on evidence, never up.** D5 needed no parameter change at all; measurement discharged it.
>
> ---
>
> **Previous (2026-09-18, later): D3 is DONE — the Factsheet is row-aligned, and its gate was
> RE-SCOPED on measurement rather than tuned.** Zero Gemini calls spent. Branch
> **`phase10/corpus-v2`** (still unmerged on purpose).
>
> **`audit_corpus.py --corpus=v2` on the Factsheet: 32 chunks · `general` 0 (0.0%) ·
> `row_spanning` 0 · 0 over cap (900) · 27 rows, S/N 1–27, zero flags.** v1 carried **48 chunks,
> 9 uncitable (18.8%), 19 packed and 26 of 48 cut across table rows.**
>
> **READ THIS BEFORE WRITING D6's GATE. `packed 0` was UNREACHABLE and measurement said so.**
> Eight sections — **11, 13, 15, 23, 34, 35, 46, 53** — are never row anchors; they exist only as
> cross-references inside another row's provisions (*"…may also accept a gift of land, money or
> property… - section 46"*). `evalset.verify_expected()` is a **hard assert**, and **frozen10/Q6
> expects 11**, so an anchor-only ref would delete those eight from the corpus and crash
> `eval_heldout` / `eval_phase06` / `audit_corpus`. The only escapes were editing frozen10
> (forbidden) or deleting held-out/test expectations. So the ref carries the **anchor first,
> cross-references ascending**, and `packed` reads **16** — a **declared non-defect**, because it is
> the table's own content.
>
> **`V2_MAX_PACKED` was NOT touched.** `--corpus=v2` still prints
> `factsheet2020 packed refs 16 <= 0: FAIL` with the reason printed underneath, so the collision
> stays visible in stdout until **D6 makes the factsheet's gate `row_spanning == 0`** — see the
> boxed warnings under **D3** and **D6** in `docs/phases/12_corpus_v2.md`.
>
> **The replacement metric has DEMONSTRATED discriminating power, not assumed.** `row_spanning`
> re-scans each emitted chunk's **text** for the S/N row-start line — never "we emit one row per
> chunk, therefore 0", which would restate the code. **v1 scores 26/48, v2 scores 0/32.** It is
> printed for **both** corpus versions, which is why `audit_corpus.py`'s v1 stdout is
> **re-baselined by 13 lines** (the new `row-span` column + legend). **Every pre-existing v1 number
> is unchanged**, `corpus_sha256` still `25650238…e89a`, `eval_phase06` still `ce716fb3…5f19`.
>
> **No manifest, on purpose.** D2's JSON seam exists because OCR must stay out of the slim Render
> runtime. The factsheet's source is already a clean TXT the repo parses at boot with stdlib, so
> `fact_v2_rows()` / `_fact_chunks_v2()` are in-process, stdlib `re` only. Symmetry is not a reason
> to add an artifact that must be kept in sync.
>
> **`fact_ref()` is NOT a v2 validator and must not be promoted to one** (unlike `act_ref()`): every
> sub-chunk carries the whole row's ref, so it legitimately names sections its own text does not
> contain, and disagreement is the design.
>
> **NEXT: D4 — exclude the Constitution's Arrangement pages.** Keep `CONST_SIZE = 400`, keep
> `_is_toc_fragment` as a **lint assertion** (do not delete it). Then D5 (refusal floor —
> mandatory) → D6 (re-baseline, and the factsheet gate re-scope above).
>
> ---
>
> **Previous (2026-09-18): D2 is DONE — the Act half of corpus v2 exists and clears its gate.**
> Zero Gemini calls spent. Branch **`phase10/corpus-v2`** (still unmerged on purpose).
>
> **`audit_corpus.py --corpus=v2` on the Act: 65 chunks · `general` 0 (0.0%) · `packed` 0 ·
> 58/58 citable · 0 over cap.** All three D2 exit criteria met. v1 carried **25 of 62 uncitable
> and 16 packed** — that class is now **closed on the Act**, and `ref = "cl. %d" % n` from the
> parser makes packed refs *structurally* impossible rather than merely absent.
>
> **The script still exits 1, and that is correct.** The Constitution (99 general) and Factsheet
> (9 general / 19 packed) rows are **untouched v1 numbers** — D3 and D4 own them. Do not wire
> anything to expect exit 0 until D4 lands.
>
> **`CORPUS_VERSION` is still `"v1"` and the user path CANNOT reach v2.** `build_corpus("v2")` is
> reachable only via `--corpus=`; `ask()` has no `version=`, `router._retriever` and `app.py` are
> untouched. Every v1 number still reproduces — `audit_corpus` v1 stdout diffs **0 lines against
> the pristine stashed code**, `eval_phase06` still hashes `ce716fb3…5f19`, `corpus_sha256` still
> `25650238…e89a`, both git guards empty.
>
> **READ BEFORE TRUSTING THE 100%.** The `act_ref()` validator reports **65/65 agreement** and it
> is **close to a tautology**: the parser writes `header = "%d. %s" % (n, title)` from the same `n`
> it builds `ref` from, and `act_ref()` recovers the numeral from that same header. The two differ
> in *inference*, **not in upstream** — this is NOT the `assert_frozen10_matches_notebook()`
> discipline it was written up as. **D6 must re-scope it before asserting** (validate against the
> Arrangement *title* text, or scope the assert to stray-`NN.` and header-drift cases). The limit
> is now printed next to the number and the script's docstring is amended in place.
>
> **A degradation-flag line was added** because `_act_chunks_v2()` does not read `clause["flags"]` —
> a regenerated manifest with `TITLE_WEAK`/`NUMERAL_MISSING` would chunk silently while D6 deletes
> `ACT_KNOWN_ABSENT` on its word. Reads `58/58 · missing none · flags none` today.
>
> **NEXT: D3 — the Factsheet S/N table** (one row = one `Section N`; drop cover / Arrangement /
> PLAC boilerplate). Its **19 packed refs are DISORDERED** (`Section 51,40`), i.e.
> `recursive_split(500/50)` cutting the table mid-row — **a different defect from the Act's, so the
> Act's fix does not transfer.** Then D4 → D5 → D6.
>
> ---
>
> **Previous (2026-09-17, later): D2's parser works — 58/58 clauses, and clause 38 is RECOVERED.**
> Zero Gemini calls spent. Branch **`phase10/corpus-v2`** (unmerged on purpose; Phase D is
> mid-flight and merging auto-deploys a half-built corpus).
>
> **58/58 clauses located on BOTH required anchors** — zero `TITLE_WEAK`, zero `NUMERAL_MISSING`,
> **no title authored**. Manifest on disk at **`data/processed/act2018_v2_clauses.json`**;
> all 27 OCRed pages at **`data/processed/gazette_rapidocr.json`**. **Do not re-derive either;
> do not re-run the OCR.**
>
> **The decisive result:** *"formulate and implement policies"* is **absent from v1** (Finding 1
> proved it by grep) and **present in v2's clause 38**. The gazette recovers clause 38's opening.
> All three written-in-advance cross-check predictions hold (cl.37 LARGE, cl.38 LARGE, cl.40
> agrees); 52/58 clauses agree with v1.
>
> **NEW: clause 53 is a second v1 truncation**, same class as cl.38 — *"awarded against the
> Commission"* is absent from v1 and v1 reads `53. | judgment debt. | shall bepaidfrom theFund of
> theCommission.` (marginal note spliced in, body cut). Decided on substring presence, **not** a
> ratio. cl.20/27/44 are OCR divergence, **not** recoveries.
>
> **Full-scope duplicate check discharged:** all 27 pages, **none** found (top adjacent pair 0.219
> vs v1's 0.978 outlier). `dedupe_pages()` not run and must not be.
>
> **READ THIS BEFORE EDITING THE PARSER.** Three geometry bugs each returned a *plausible* number
> rather than an error: (1) splitting columns on the widest **gap** reintroduced the verso/recto
> asymmetry — first run **16/58**; (2) body extent as **min/max** over wide lines broke on one
> merged OCR box (p11 lost all 13 notes; p13 clipped **cl.38's own title** into the body);
> (3) `FURNITURE_RE` under global `IGNORECASE` matched **`"Participation"`** as `PART`+`[IVX]` and
> deleted cl.30's note. The flags are what caught all three — a one-anchor accept would have
> shipped every one as 58/58.
>
> **And the ruler was wrong before the parser was.** The cross-check first said only 7/58 clauses
> agreed; that was a 40-char shingle measuring independent OCR noise, not the corpus. k=10 is
> **calibrated against clauses whose answer Finding 1 already settled**. A second, uncalibrated
> alignment measure scored cl.40 at 0.18 (vs 0.90) and was **discarded, not used**.
>
> **`ocr_gazette.py --pages=1-27` was one flag away from destroying the verified Arrangement
> manifest** (it would have parsed body pages as entries and overwritten it, without erroring).
> Now guarded by `--ocr-only` **and** a refusal to replace a clean manifest with a dirty parse.
>
> **NEXT: `_act_chunks_v2()` + `ACT_V2_SIZE = 1100`** — the only thing between the parse and D2's
> exit criteria (`general` ≤1%, `packed` 0, 58/58 citable). `ACT_V2_SIZE` is a **new** constant,
> **not tuned in D2** (that is D5's recalibration). `CORPUS_VERSION` stays `"v1"` until D6, and
> `ACT_KNOWN_ABSENT = {38, 40}` stays until **D6 deletes** it.
>
> ---
>
> **Previous (2026-09-17): the chat work SHIPPED, and Phase D's gate answers GO.**
> Zero Gemini calls spent. Branch **`phase10/corpus-v2`**, off a merged `main`.
>
> **Both open owner decisions below are now CLOSED.** Push+PR happened first: PR #12
> (Phase 10 A+B+C + D-planning) merged, `main` `bb6f931` → **`6b10f62`**, and Render
> auto-deployed — **users now get the multi-turn chatbot, not the single-turn form.**
> The branch stack is unwound; `phase10/chat-core` and `phase10/chat-ui` are pushed.
> The orphaned 740-line doc pass was committed before anything else.
>
> **D2's GO/NO-GO GATE: GO.** The gazette's Arrangement yields a clean **`1..58`** — no
> holes, no duplicates, nothing out of range. The manifest-anchored parser is unblocked;
> the marginal-note fallback was **not needed and not used**; **no title was authored.**
> Manifest is on disk at **`data/processed/gazette_arrangement.json`** (58 entries,
> `"title_source": "arrangement"`) — **do not re-derive it.**
>
> **Read this before writing an OCR parser.** The first parse returned **23 of 58** and
> looked exactly like the truncated source Finding 1c predicted. It was not. RapidOCR emits
> the clause number and its title as **separate boxes**, and their vertical centres differ
> enough that the title often sorts *before its own number* — so a line-at-a-time regex
> anchored on `^\d+\.` can never match. Group boxes into **visual rows by vertical overlap**,
> then order left-to-right. Same failure class as v1's 25/62 uncitable Act chunks. The tell
> that it was a parser bug and not a finding: OCR confidence was **0.978–0.984**.
>
> **`scripts/ocr_local.py` was a live hazard and is now fixed.** It had a bare `main()` at
> module scope with no `__main__` guard, and `main()` unconditionally overwrites
> `data/processed/disability_act_2018_full.txt` — the v1 Act corpus every published baseline
> is measured against. Guard + `--force` added, both verified. Shared helpers now live in
> **`scripts/ocrlib.py`** (keeps box geometry; pymupdf/rapidocr imports are function-local).
> Keep running the `git diff main -- data/processed/disability_act_2018_full.txt` guard.
>
> **D1 landed:** `Chunk.path` defaulted · `build_corpus(version=)` as **pure relocation** ·
> `--corpus=` (equals form only) on 6 harnesses. Two prose claims are now **negative-tested**
> gates: `corpus_sha256()` (`25650238…e89a`) catches text moving *between* chunks at constant
> count, which the nine shape integers cannot see; `eval_phase06` asserts `ce716fb3…5f19` and
> is **Windows/CRLF-specific on purpose**, reading the file back from disk as bytes.
> Stdout gained 2 lines in `audit_corpus` + one ` sha256=…` in `eval_phase06` — **re-baselined
> here, not broken silently.** Everything else reproduces byte-identically.
>
> **NEXT: D2's clause locator + the 27-page body OCR**, then `_act_chunks_v2()` / `ACT_V2_SIZE`.
> `ACT_KNOWN_ABSENT = {38, 40}` **stays** — cl.38's *title* being in the Arrangement says
> nothing about its *body*. D6 deletes that constant, after the re-OCR.
>
> ---
>
> **Previous (2026-09-16): Phase 10 C (chat UI) DONE. Zero Gemini calls spent.**
> Branch `phase10/chat-ui`, off `phase10/chat-core`. Playbook: `docs/phases/11_chat.md`
> (Step C results). **DRLCA is a chatbot now** — `streamlit run app.py` gives you a
> multi-turn conversation, not the single-turn form.
>
> **This phase spent Phase B's gain and measured nothing new.** No retrieval, scoring, corpus
> or prompt change — so `eval_chat.py` and `eval_heldout.py` were *required* to reproduce
> `368f083` exactly, and did: **byte-identical stdout**. `eval_phase06.py` still hashes
> `CE716FB3…5F19`. `git diff --stat main -- requirements.txt` **empty**. Baselines were
> captured **before** the first edit, which is the only reason that can be claimed.
>
> `app.py` → **`render_turn`** (computes + renders one new turn; compute and render stay
> fused because the banner invariant is asserted on literal source adjacency inside it) ·
> **`replay_turn`** (renders a stored `TurnPayload` — **no retrieval, no router, no
> network**, now asserted) · `render_history` · a `st.chat_input`-driven `run()`.
> `src/router.py` gained **one defaulted arg** and **stays stateless**.
> **`test_phase05.py` 104 → 137, all green**, 6 rescoped with an inline note each.
>
> **Two deviations from the plan, disclosed not absorbed:** (1) a **second** defaulted
> `TurnPayload` field, `help_payload` — without it, replaying a help turn forces a live
> router call every rerun, the exact thing `replay_turn` exists to prevent; neither new field
> is read by any eval. (2) the per-turn `answer_legal(..., use_llm=False)` **probe was
> deleted** — it existed only to print the prompt-version string and cost **a whole second
> retrieval per turn per rerun**; now `_prompt_id()`, reading the constants from `src/rag.py`.
>
> **Width/pool depth did NOT land here** (the older plan had it in this phase). `k=3/doc,
> top_n=6` is what both harnesses measure; Phase B measured the change at **test +0.000**. It
> moves in **Phase E**, in the same commit as the harnesses. The **display** split (3
> excerpts inline + rest in one fold) did land — that is presentation, not retrieval.
>
> **Privacy: history is `st.session_state` only.** After a full four-turn conversation
> **neither `scripts/.answer_cache.json` nor `scripts/.quota_log.json` existed at all** — the
> offline path wrote nothing. The new quota log (gitignored) holds counts only,
> `{"YYYY-MM-DD": {"model": 3}}`, and the sidebar says *"THIS INSTANCE SINCE RESTART"*, never
> *"today"* — the free host's filesystem is ephemeral and it sleeps after 15 min.
>
> **Browser-verified** (Chrome/DevTools, no key spent): ellipsis *"so can they fire me?"*
> carried on `unbound-pronoun:they`; *"I'm deaf"* → clarify, then *"anywhere in Kano?"* two
> turns later still answers **NNAD** from the carried slot; banner at page top **and** leading
> every assistant turn; per-turn read-aloud genuinely isolated (each `components.html` is its
> own iframe document); both AI toggles OFF; Clear conversation works; 360 px no overflow;
> dark + HC coherent. The three AI-failure paths (no key / 429 daily cap / network down) were
> proven **headlessly at zero quota** — `answer` stays `None`, **pending, never faked**.
>
> **Latent bug fixed in passing:** `try_voice_input()` wrote `session_state["q"]` *after* the
> `q`-keyed widget had rendered, which Streamlit forbids. It never fired because the mic path
> is owner-gated. It now writes `voice_draft`, copied into `q` before instantiation.
>
> **Fresh-eyes review: no blocking issues, verdict ship.** Two fixes taken (→ **137** asserts):
> `_prompt_id()` decided multi-turn from `turn_index > 0` while `ask()` branches on
> `rag._render_history()` being non-empty — equivalent today only by caller discipline, now
> `_multi_turn(prior)` calls the same two functions `ask()` calls; and a **pre-existing
> tautological assert** (`no-wide-columns-for-banner` ended in `or True`, padding every count
> published since Phase 05) was rewritten so it can fail. Both evals re-run after: still
> byte-identical to `368f083`.
>
> **Next: Phase D — corpus v2** (**`docs/phases/12_corpus_v2.md`**, written 2026-09-16; M3 of
> `10_corpus_rebuild_and_dense.md` is **superseded**). See **PHASE D — START HERE** below: the
> download is done, and **two of M3's premises turned out to be false** — Act cl.38/40 are
> **recoverable**, and the Constitution needs only the cheap fix.

> **Previous (2026-09-15): Phase 10 B (chat-core) DONE. Zero Gemini calls spent.**
> Branch `phase10/chat-core`. Playbook: `docs/phases/11_chat.md`. Full run:
> `scripts/baseline_chat_2026-09-15.txt`.
>
> **DRLCA is becoming a chatbot, and the reason it is a RETRIEVAL phase, not a UI phase:**
> *"so can they fire me?"* contains no disability term and no statutory term, so no
> re-ranker, no encoder and no corpus rebuild can answer it — the query does not contain the
> question. `src/router.py` is stateless (correctly, and it stays that way), so **nothing in
> the stack resolved ellipsis before this.** The multi-turn set was therefore built and
> measured **before** the chat UI and before corpus-v2/dense: tuning those on single-turn
> questions only would optimise a query distribution the chatbot never issues.
>
> New: `data/eval/conversations.json` (22 conversations / 62 turns / 51 corpus-verified refs)
> · `scripts/chatset.py` · `src/chat.py` · `history=` on `ask()`/`build_prompt()` ·
> `scripts/eval_chat.py`. **`chat_test` was authored BLIND before `src/chat.py` existed.**
>
> **Numbers (corpus v1, shipping arm, naive → contextualised):** chat_dev **0.464 → 0.571**,
> chat_test **0.435 → 0.565**. Ellipsis **0.000 → 0.333** (dev) / **0.200 → 0.600** (test);
> the `direct` control moves **+0.000** on both. recall@60 **0.714 → 0.929** / **0.783 →
> 0.913**. Help slots **3/5 → 5/5** and **1/2 → 2/2**. **False refusals FELL** (1/28 → 0/28,
> 3/23 → 1/23), **0 contextualisation-induced**.
>
> **The new chat-only trap did NOT fire.** Off-corpus-after-legal clears `MIN_SCORE` **2/2 in
> both arms, both sets, delta 0.000** — same as the published single-turn 5/5, a property of
> the inverted-band floor, **not** something chat introduced. **`MIN_SCORE` untouched.**
>
> **Two things recorded rather than fixed** (read this before "improving" them):
> chat_test's **pronoun class did not improve at all** (0.400 → 0.400), and a blind test-set
> note (`CT6.t3`) predicted a carry decision that behaves otherwise. Both stay as measured —
> tuning either against `chat_test` is exactly how the 30 held-out questions were spent on
> 2026-09-13. Thresholds were chosen on **chat_dev only**.
>
> **Two new hard invariants, now asserts** (`test_phase09_ops.py` 38 → **51**):
> `history=None` renders a **byte-identical** prompt (the cache keys on the whole rendered
> prompt), and history renders **BEFORE** the final `"Question: "` line — that one is
> **privacy**: `_cache_write` stores only that line, and this population discloses abuse and
> coercion. Chat has its own `CHAT_PROMPT_VERSION = "chat-cite-strict-v1"`.
>
> **Unmeasured on purpose:** cross-turn citation drift needs a generated answer to read, so it
> costs quota. `chat.cross_turn_drift()` is wired and runs in Phase G.
>
> ~~**Next: Phase C — the chat UI.**~~ **DONE 2026-09-16** — see the banner at the top.

## Session close 2026-09-16 — what is done, what is NOT

**Done this session:** Phase 10 **C only**, on `phase10/chat-ui` (branched off
`phase10/chat-core`). **Gemini spend this session: ZERO.** Nothing is pushed.

**Not started:** Phases **D, E, F, G**. Phase C touched no retrieval parameter, no corpus
file and no prompt string — the chat UI is a surface for Phase B's engine and nothing more.

Three of the remaining phases have hard external dependencies the next session should know
about before planning:

- ~~**D** needs a >10MB download…~~ **DISCHARGED 2026-09-16.** `6document.pdf` is downloaded
  (14.1 MB, repo root, to be moved into `data/raw/` in D1) and verified as the authoritative
  gazette. It resolved the cl.38/40 question — **they were never missing**. See Finding 1.
- **F** needs **Colab or Kaggle GPU**. `torch`/`sentence-transformers` must **never** be
  installed into `drlca-rag` — `CLAUDE.md` records an env break from exactly that.
- **G** needs **~42 Gemini calls across 2 days** (40/day budget, two pools). That is an owner
  decision to spend, not something to start unprompted.

~~Working tree is clean apart from the known stray `D:NGORAG_review_judge.diff` (0 bytes,
U+F03A in the name, in no commit, deletion permission-blocked — still needs removing by hand).~~
**RESOLVED — verified gone 2026-09-18**: `git status -uall` reports no untracked files and a
filename glob for `*review_judge*` in the repo root matches nothing. Working tree is clean.

## PHASE D — START HERE (corpus v2, **`docs/phases/12_corpus_v2.md`**)

> **The playbook moved.** Phase D is **`docs/phases/12_corpus_v2.md`**, written 2026-09-16, not
> M3 of `10_corpus_rebuild_and_dense.md`. **M3 is superseded and must not be executed** — two of
> its premises were measured on 2026-09-16 and are false. M3 is kept, with amendment boxes, so
> nobody re-picks up an invalidated step.
>
> **Branch:** `phase10/corpus-v2`, off `phase10/chat-ui`. **Zero quota. No new packages.**

**Phase D's download dependency is DISCHARGED.** `6document.pdf` (14.1 MB) is downloaded and sits
in the repo root awaiting a move into `data/raw/` (first task of D1).

### Finding 1 — the Act gap is a SOURCING failure, not an OCR failure. cl.38 and cl.40 are recoverable.

> **⚠ CORRECTED 2026-09-17 — the cl.38 row published in `4bcc763` was WRONG.** It claimed cl.38's
> body was in the v1 text at **L614**. **L614 is clause 48.** L612 reads `48.`; the Arrangement at
> **L74** says `48.Annual estimate and expenditure.`, which is exactly the marginal note wrapped
> around L614 at L613/L615; v1 continues `(a) cause tobekept accounts and records` (cl.48) where
> the gazette continues `(a) formulate and implement policies` (cl.38). `grep "formulate and
> implement"` returns **nothing** in v1. The match was made on string similarity to
> `38.TheCommissionshall-` **without reading the next line**.
>
> **cl.40's row is correct** — body at L545, bounded by `39.` (L524) and `41.` (L555), marginal
> note at L544/546/547/549/551 matching Arrangement L66.
>
> **The conclusion survives.** `ACT_KNOWN_ABSENT = {38, 40}` still retires — **cl.40 because it was
> never absent, cl.38 because the *gazette* recovers it (A109–A110)**, not because v1 had it. All
> 58 clauses still reachable in v2. 2026-09-13 was **right about cl.38's absence**, wrong only
> about its **irrecoverability**. Full detail + three new findings: `docs/phases/12_corpus_v2.md`.

The download is *Federal Republic of Nigeria Official Gazette No. **10**, Vol. 106, 21 January
2019, Act No. 2, pages **A97–A122*** — the authoritative gazette. 27 pages, 0 embedded text chars
(a scan, like the existing copy), but **no duplicate adjacent page pair**. Targeted OCR
(`rapidocr_onnxruntime`, dpi 200) of gazette pages **13, 14, 15** recovered both clauses in full.

**State of the v1 text, corrected 2026-09-17:**

| clause | gazette | `data/processed/disability_act_2018_full.txt` | verdict |
|---|---|---|---|
| 38 | `38.TheCommissionshall-` (A109) | opening + (a)–(i) **ABSENT**; its (j)–(r) tail is present at L501–522, misfiled | **absent from v1, recovered from the gazette** |
| 40 | `40.—(1) There shall be an Executive Secretary…` (A111) | `(1) There shall be an Executive Secretary for the Commission who shall-` (**L545**) | **never absent** — OCR dropped the numeral |

The duplicate page **is** real (adjacent-page cosine **0.978 p5–p6** vs a 0.794 runner-up, dpi 100,
16×16 mean-pooled, **mean-centred**) — and it **did** cost cl.38's opening. It did **not** cost cl.40.

**Three findings from the 2026-09-17 re-check, all strengthening the case for v2:**

1. **v1's clause 37 is silently corrupted.** A physical page is missing at the `===== PAGE 14 =====`
   boundary (**L500**): raw OCR p13 ends at cl.37(b), p14 opens mid-list at cl.38(j).
2. **A LIVE citation-integrity defect.** Act chunk 33 is reffed **`cl. 39`** and opens with cl.38's
   `(o)`–`(r)`, including *"procure assistive devices for all disability types"*. **The app can
   today serve cl.38's text under an `[Act cl. 39]` tag** — a wrong citation that passes
   `verify_citations()` mechanically. (Chunk 31 `cl. 36,37` is clean; chunk 32 is `general`.)
3. **v1 L542 reads `PARTVII`** where the Arrangement (L64) and the gazette say **PART VIII**; and
   **v1's Arrangement truncates at L77, `51.Power to acquire land.`** — so `audit_corpus.py:64-66`
   cites it as the source of `ACT_CLAUSES = range(1, 59)` when it does not contain 52–58. Right
   number, wrong source. **D2's Arrangement gate must therefore run on the gazette, whose
   Arrangement pages have not been OCRed yet.**

**Retires by name:** `ACT_KNOWN_ABSENT = {38, 40}` at **`scripts/audit_corpus.py:90`** (was `:80`
until D1 added the comment block above it — corrected 2026-09-18) (deleted,
**not emptied** — in **D6**, once the v2 corpus that recovers cl.38 exists) · `audit_corpus.py`'s
*"the pixels do not exist"* line · the **irrecoverability half** of the 2026-09-13
`LEARNING_JOURNAL.md` claim · the old standing fact below.

**All 58 clauses are reachable in v2 and the gap manifest may end up empty.** *Scope limit: only
pages 1, 13, 14, 15 of 27 were OCRed. "All 58 clauses present" is a D2 verification task, not a
finding.*

**D1 and D2 are designed, not just listed.** `docs/phases/12_corpus_v2.md` now carries
*"Implementation notes"* under both — the `Chunk`-field sweep, the three-tier caller policy, the
two prose-claims-become-gates, the three-layer OCR/parse/runtime split, the marginal-note geometry
measurements, the monotonic-cursor locator and the pre-written cross-check predictions. **Read
them before writing code; they exist so the next session executes rather than re-derives.**

### Finding 2 — the Constitution needs only the cheap fix to clear the gate

> **⚠ CORRECTED 2026-09-18 (D4) — the "→ ≈0" half is FALSE, and it was the gate's target.**
> Arrangement exclusion takes `general` **99 (4.71%) → 34 (1.67%)**, not ≈0, so
> `V2_MAX_GENERAL_PCT = 1.0` is **unreachable on this document** and D4 left it untouched on
> purpose (the FAIL stays in stdout until D6 re-scopes it). The residual 34 is **8 structurally
> unnumbered** chunks (Preamble ×2, six chapter dividers) + **26 Chapter VIII Schedule / Rules
> items**, where `general` is the **correct** ref. The first half of the finding **survives and was
> re-verified**: all 99 v1 uncitable chunks really are Arrangement material, zero substantive body
> text is uncitable, and `CONST_SIZE` really did not have to move. D4 re-scoped the gate to
> **`toc_general` outside Chapter VIII == 0** (v1 7, v2 0) plus the pinned 8 + 26 inventory.

**All 99 uncitable Constitution chunks are Arrangement-of-Sections material** — 88 under 60 words,
and every one of the 11 at ≥60 words is *also* a numbered title listing (`"236 Practice and
procedure"`). **Zero substantive body text is uncitable.** Excluding the Arrangement pages takes
`general` 99 (4.7%) → ~~≈0~~ **34 (1.67%)** and deletes the `toc-trap` class **without touching
`CONST_SIZE = 400`**.

M3's 2104 → ~500 section-unit re-extract — the riskiest change in the whole plan — **is not needed
for the gate** and defers to Phase E, where the dense arm actually wants it.

### Finding 3 — M3's milestone order is backwards

M3 runs M1 (width) → M2 (dense) → M3 (corpus). M2 ships `data/embed/chunks_gemini.f16.npy`, a
**per-chunk** artifact keyed on a corpus sha256 — rebuilding the corpus afterwards invalidates
every vector and forces a full re-embed. **Corpus first.** This is what `HANDOFF.md` already
assumed by putting D before E; the playbook never said why.

**Also measured:** the Act's **16 packed refs are all consecutive runs** (`cl. 3,4,5` … `cl. 56,57`)
— pure 800-char cutting, fixable mechanically. The Factsheet's 19 packed refs are **disordered**
(`Section 51,40`, `Section 50,45,54`) — `recursive_split(500/50)` cutting the S/N table mid-row.

**The audit gate is `ref == "general"` ≤1% per doc** — the gate that removes the uncitable-chunk
class named three separate times now (Act cl.19, `CT7.t2`, and the 25-of-62 uncitable Act chunks).

### What `app.py` looks like now (Phase C, so Phase D does not re-derive it)

- `render_turn(question, explicit, plain, history, turn_index) -> TurnPayload` — computes AND
  renders one new turn. Fused on purpose: `test_phase05.py` asserts the banner invariant on
  the *literal adjacency* of `render_helpline_banner()` and the `# Single routing seam`
  comment inside this function's body. Splitting compute from render makes that unassertable.
- `replay_turn(payload, turn_index, live)` — renders a stored turn. **No retrieval, no
  router, no network** — asserted, because Streamlit reruns the whole script on every
  interaction.
- `render_history(live_last)` · `render_excerpts` · `render_ai_expander` · `render_defects` ·
  `render_help_records` · `render_plain_caption` — the last five are shared by both paths.
- `run()` — sidebar → title → banner → history → voice draft → `st.chat_input`. A submitted
  question goes into `st.session_state["pending"]` and reruns, so the new turn paints in
  position at the end of the thread.
- Fixed-key controls (`switch-%s`, `clarify-legal`, `clarify-help`) render on the **last turn
  only**; acting on one pops that turn and re-queues it (`_requeue_last`).

**Three things Phase C recorded and deliberately did NOT fix.** Do not "tidy" them without
reading why:

1. **N read-aloud iframes means N `setInterval` theme pollers.** Each `components.html` is
   its own iframe carrying `theme_watch_html()`. `test_phase05.py:182` requires the watch to
   be present, so centralising it is a deliberate, asserted change — not a drive-by.
2. **Dark + high contrast together leaves the sidebar `#010409`, not `#000`** (equal
   specificity, dark rule emitted later in `accessibility_css()`). ~19:1 contrast, predates
   Phase C, `accessibility_css()` was not opened.
3. **Width / pool depth is Phase E, not a UI change.** `k=3/doc, top_n=6` is what
   `eval_chat.py:106-108` and `eval_heldout.py` measure, and `offline_legal_hits`' docstring
   forbids a display path that slices differently from `ask()`. Move the harnesses in the
   same commit or the shipped system detaches from every published number.

**Housekeeping.** `phase10/chat-core` → `phase10/chat-ui` → (`phase10/corpus-v2`) is about to be
**three unpushed branches deep** off `main` — **still open**, worth deciding whether to push and
PR the chat work before Phase D starts. `CLAUDE.md`'s *"Next up:
`docs/phases/08_retrieval_upgrades.md`"* pointer is **stale** — fix it when `CLAUDE.md` is next
opened, in D6. **DECIDED 2026-09-16:** the 14 MB gazette PDF **gets committed** to `data/raw/`
(consistent with the already-tracked 5.2 MB Act and 8.5 MB Constitution; never read at boot, so
the Render runtime is untouched) — in its **own commit** in D1, so the blob is easy to find later.

## Next, in this order

**Updated 2026-09-16.** The phase ordering is now:

| phase | what | playbook | quota |
|---|---|---|---|
| **D — NEXT** | **corpus v2** (Act re-OCR + manifest parse, Factsheet table, Constitution Arrangement exclusion, refusal re-calibration, re-baseline) | **`docs/phases/12_corpus_v2.md`** | **0** |
| E | width / pool depth + dense retrieval + the Constitution section-unit re-extract | `10_corpus_rebuild_and_dense.md` **M1, M2** (reordered to here) | probe + embeddings |
| F | fine-tune on free GPU + distil the offline tier | `10_...md` M4 | 0–20 |
| G | fresh transcripts, judge, cross-turn citation drift | `10_...md` M5 + `11_chat.md` | ~42 over 2 days |

**Why D before E:** M2's `data/embed/chunks_gemini.f16.npy` is a **per-chunk** artifact keyed on a
corpus sha256. Embedding before the rebuild throws all of it away. See Finding 3 above.

The older Phase 08/09 backlog below is **still open but now sits behind D**, and part of it is
already overtaken — Phase 10 measured lexical retrieval as exhausted, and Phase D is the response.
Read `docs/phases/09_evidence_and_generation.md` before picking any of it up. In short:

- **Phase 08 steps 4/5 as written cannot reach a real user.** Both need a model at *query*
  time (step 4 a cross-encoder; step 5 to embed the incoming query — prebuilt chunk vectors
  do not solve that half), and `requirements.txt` forbids ONNX/FAISS. Flag-gated = flag OFF
  in production. **Superseded by Phase 09 step 3**, which delivers both wins with zero
  query-time deps.
- **Retrieval is no longer the bottleneck; generation is.** recall 0.925 vs a 0.75 gate,
  while the judge confirmed Q3 thinness is a REAL prompt defect (Q3 recall 1.000).
- **The synonym map is fitted to the set that scores it** (n=10, entries kept/deleted by
  their effect on Q5/Q7/Q8/Q9). 0.925 cannot distinguish generalization from memorization.

Order (owner-confirmed 2026-09-11, all four, under a **runtime-shippable-only** constraint):

1. ~~**Ops hardening (zero quota, small).**~~ **DONE 2026-09-13, PR #9.** `--no-cache` +
   `--failover` on `test_phase02.py`; opt-in daily-cap-only failover in `src/rag.py`.
2. ~~**Widen the evidence base (zero quota).**~~ **DONE 2026-09-13, PR #10.** 30 held-out
   questions; **held-out recall 0.420 vs frozen-10 0.925** (see the banner at the top).
   False-refusal 0/25; gate-level false-answer 5/5.
3. **Shippable retrieval (zero quota).** ~~NEXT~~ — **BM25 was built and FALSIFIED 2026-09-13**
   (a coin flip: ranks the expected chunk higher on 15 of 91 pairs, lower on 16). The
   offline-computed `synonyms_auto.json` half is still open, but Phase 10 B/D supersede the
   motivation: the hand-written map's weakest class is the one it exists to fix, and the corpus,
   not the ranker, is the ceiling.
4. **Generation fix (quota-paced).** Q3 answer-shape floor + the named `reverse_rel` fix in
   its own commit + a fresh 12-call generation pass.
5. **Owner-side:** frames → GIF encode + README embed (`docs/demo/` + storyboard are
   ready) → NVDA/keyboard/mic gates → LinkedIn (+ optional Streamlit 2nd link).

## Standing facts (don't re-derive)

- ~~**Act cl.38 and cl.40 are absent from the source PDF; no OCR or VLM can recover them.**~~
  ~~**FALSIFIED 2026-09-16** — both clause bodies are in the v1 text right now, at L614 and L545.~~
  **RE-CORRECTED 2026-09-17 — the 2026-09-16 correction was itself half wrong. Read this version.**
  - **cl.40: never absent.** Body at **L545** (`(1) There shall be an Executive Secretary for the
    Commission who shall-`), numeral `40.—` OCR'd away. Bounded by `39.` (L524) and `41.` (L555).
  - **cl.38: genuinely absent from v1**, opening and (a)–(i). **L614 is clause 48, not 38** — L612
    reads `48.`, the Arrangement at L74 says `48.Annual estimate and expenditure.` (the marginal
    note wrapped at L613/L615), and v1 continues `(a) cause tobekept accounts and records` where
    the gazette continues `(a) formulate and implement policies`. `grep "formulate and implement"`
    → **nothing** in v1. cl.38 is recovered from the **gazette** (A109–A110), not from v1.
  - **cl.38's (j)–(r) tail IS in v1** (L501–522), and chunk 33 carries `(o)`–`(r)` under the ref
    **`cl. 39`** — so the app can serve cl.38's text with an `[Act cl. 39]` tag **today**.
  - The duplicate page 5–6 **is** real (adjacent-page cosine 0.978 vs a 0.794 runner-up) and it
    **did** cost a physical page — the one carrying cl.37's tail and cl.38's opening. It did not
    cost cl.40.
  - **`ACT_KNOWN_ABSENT = {38, 40}` at `scripts/audit_corpus.py:90` is still a false constant** and
    is deleted (not emptied) in **D6** — after the gazette re-OCR that recovers cl.38, not before.
  - **The no-stub / no-paraphrase / no-model-knowledge rule stands regardless** — it governs real
    gaps, and cl.38 was one until the gazette arrived.
  - **The lesson, twice over:** 2026-09-13 inferred *what* a measured duplicate cost without
    grepping the text. 2026-09-16 grepped the text but matched a line on string similarity
    **without reading the next one**. Both published. Check the neighbours, not just the match.
- ~~Q5 penalties = correct refusal ×4 runs~~ **SUPERSEDED 2026-09-11.** The synonym map
  closed the vocabulary gap (corpus says *offence/fine/imprisonment*, query says
  *penalties*): Q5 recall **0.000 → 0.250**, live-verified returning `[Act cl. 2]` /
  `[Act cl. 1]`. Still misses cl.8,9,10,13,29,30 — rerank/hybrid remain the real fix.
  On the old "NO synonym hack" warning: the map is not that hack — entries are
  corpus-verified legal vocabulary and the full matrix was re-run on every change — but
  the map IS a score-sensitive surface, so the warning still applies to new entries.
  **Expansion is not symmetric**: an `education` key cost Q7 recall 1.000 → 0.500 and was
  deleted; only `school → education` (user→corpus direction) survives.
- **Q5 faithfulness now reads 0.000 and that is CORRECT, not a regression.**
  `eval_phase06.py:176-182` scores a refusal 1.0 only if no expected ref was retrieved.
  The transcript answer is frozen pre-M1 (it refuses); retrieval is recomputed live and
  now finds `act2018:1,2`, so the refusal is no longer justified. Net effect:
  **faith_audited 0.867 UNDERSTATES the system** — a fresh generation pass would likely
  answer Q5. Don't "fix" this in the eval; it needs 12 generator calls.
- Synonym expansion is **two-side gated** (`src/retrieve.py`). Entry gate: expand only if
  the user's own words already clear `MIN_SCORE` (otherwise expansion manufactures corpus
  overlap and turns a refusal into an answer). Exit gate: keep the expansion only if it
  still clears the floor (otherwise appending absent terms dilutes the query-vector norm
  and creates a FALSE REFUSAL). Guaranteed property is narrow and exact: *expansion never
  turns a refusal into an answer, and never turns an answer into a refusal; it only
  re-ranks within the answered set.* It does NOT always raise the top score.
- Q10: v2 false refusal → fixA variance resolved (s.46 quotes) → fixA2 PARTIAL
  (s.39 3rd-claim misattr). Q9: v2 s.33 trap → fixA2 removed, s.34 still missing.
- Precision 0.333 is BY DESIGN (per-doc merging trades it for recall) — never gate it.
- Coverage/reverse_rel custom misses are metric artifacts (documented) — don't tune
  yardsticks; reverse_rel stays recorded FAIL until the judge rules.
- Fix A: 14 Constitution TOC fragments → `general` in `const_ref`; ranking untouched.
  **Fix B landed 2026-09-11: `MANUAL_FLAGS` is now `[]`.** `_is_toc_fragment` widened to
  orphan list-entries and `verify_citations` checks cited numbers against the chunk's own
  `ref` instead of pooled chunk text (pooled matching is exactly what let Q10 cite s.39 for
  High-Court text sitting in the same pool). Q10 `faithfulness_auto` 1.000 → 0.667,
  mechanically. **Trap for anyone widening it further:** `verify_ground_truth` asserts every
  EXPECTED number appears in some chunk's `ref`, and demoting a ref to `general` removes its
  numbers — an over-eager rule hard-crashes the eval before it prints anything. Measure the
  blast radius in isolation first (2026-09-11: 12/2,104 chunks relabelled, s.17/34/46 kept
  17/6/6, no section number lost).
- Eval script points at fixA2 transcript now. Never fake LLM rows.
  LLM runs → versioned files; dry runs → `--out=<temp path>` (space form ignored!).
- Test commands (all via project python): `bench_phase01` (PASS) · `test_phase03`
  (16/16+7/7) · `test_phase04` (PASS) · `test_phase05` (104) · `eval_phase06.py --out=...` ·
  `test_phase09_ops` (38/38, zero network) · `eval_heldout` (held-out retrieval baseline) ·
  `ablate_phase08` (PASS). `eval_heldout.py` exits nonzero **only** on ground-truth failure or
  a **frozen-10** regression — never on a held-out number, by design.
- Eval ground truth lives in **`data/eval/questions.json`** (10 `frozen10` + 30 `heldout`),
  loaded via `scripts/evalset.py`. `eval_phase06.EXPECTED` is now derived from it, and
  `judge_phase06.py` / `ablate_phase08.py` still import `EXPECTED` unchanged.
  `bench_phase01.load_questions()` is **KEPT, not retired**: `assert_frozen10_matches_notebook()`
  requires it and the JSON to agree in order on all ten texts, so a reworded frozen question
  fails loudly instead of silently moving the yardstick. **Frozen questions are frozen** — add
  new ones, never edit these, never merge held-out into the frozen 10.
- Quota: **TWO limits, not one** (corrected 2026-09-11 — the missing one cost 9 calls).
  20/day/model **and 10 requests/MINUTE/model**. The per-minute 429 is
  `GenerateRequestsPerMinutePerProjectPerModel-FreeTier` and carries its own `retryDelay`
  (~37s) — it is NOT terminal and must be retried, not treated as the daily cap. A daily-cap
  429 stays pending and unfaked. `scripts/judge_phase06.py` has the working pattern (7s
  pacing, `_is_per_minute()`, bounded backoff, checkpoint after EVERY call).
  503-transients retry with backoff, same day OK. Models draw from **separate pools**:
  the judge run spent `gemini-2.5-flash-lite` and touched `gemini-2.5-flash` zero times.
  **Lever now WIRED (2026-09-13, was "unused"):** the real daily budget is **40, not 20**.
  `rag.FALLBACK_MODEL = gemini-2.5-flash-lite`; `ask(failover=True)` / `generate(failover=True)`
  fail over **once**, on a **daily-cap** 429 only, and record `model_used` (top level and in
  `route`; `route["model"]` still means the model *requested*). Off by default — a flash-lite
  answer is not a flash answer. A per-minute 429 **re-raises** so the caller retries it.
  `is_per_minute_429()` / `retry_delay()` now live in `src/rag.py`, not the judge script.
- Answer cache live (`src/rag.py`, gitignored at `scripts/.answer_cache.json`): keyed by
  sha256(model + NUL + **whole rendered prompt**), so context and prompt version are in the
  key. Fails OPEN. Every hit sets `cached=True` and `test_phase02.py` persists it — a replay
  can never be written up as a fresh call.
  **Corollary found 2026-09-11, FIXED 2026-09-13:** the cache defeated the pending two-run
  flakiness check — `test_phase02.py` never passed `use_cache`, which defaults `True`, so run
  two would have been 12 cache hits measuring nothing. `test_phase02.py --no-cache` now exists
  and threads `use_cache=False` through. **Use it for the flakiness check** (still unrun).
  *(A prompt-version bump does NOT need the flag — the key covers the whole rendered prompt,
  so a new `PROMPT_VERSION` misses the cache automatically.)*
- **Phase 08 steps 4/5 are SUPERSEDED, not just deferred (2026-09-11).** Both need a model at
  *query* time — step 4 a cross-encoder, step 5 to embed the incoming query (prebuilt chunk
  vectors do not solve that half) — and `requirements.txt` bans ONNX/FAISS. "Flag-gated"
  therefore means OFF in production: local eval numbers move, users see nothing. Replacements
  in `docs/phases/09_evidence_and_generation.md` step 3: BM25 re-rank *inside* the cosine gate
  (zero new packages) and an offline-computed `synonyms_auto.json`. **Never re-rank by
  replacing the cosine scorer** — BM25 scores are unbounded and would silently invalidate the
  `MIN_SCORE` calibration at `src/retrieve.py:26-44` and change refusal behaviour.
- **recall 0.925 is measured on the same 10 questions the synonym map was tuned on.** Entries
  were kept or deleted by their effect on Q5/Q7/Q8/Q9, so the number cannot distinguish
  generalization from memorization. Treat it as an upper bound until the Phase 09 held-out set
  exists. The frozen 10Q must stay frozen AND separate — never merge held-out questions into
  it, or every historical artifact from Phase 01 onward loses comparability.
- CSS rules of the road (learned 2026-09-09): watermark div lives INSIDE
  stMainBlockContainer (z-1), so sidebar needs z-index 2; Streamlit's own section
  rules beat un-`!important` ones; height=0 iframes never mount (use 1); srcdoc
  scripts race `<body>` (DOMContentLoaded-ready wrapper); restart server after
  edits; HC mode trips the luminance gate (bodyDark=true — harmless).
- Render notes: create via `render services create --name ... --type web_service
  --repo ... --branch main --runtime python --plan free --build-command
  "pip install -r requirements.txt" --start-command 'streamlit run app.py
  --server.port $PORT --server.address 0.0.0.0' --env-var PYTHON_VERSION=3.11.0`
  (+ `GOOGLE_API_KEY` from env, never printed). Free sleeps 15 min idle (~1 min
  wake); ephemeral FS fine (corpus prebuilt). Token expired once → user `render login`.

**Pending owner inputs:** frames→GIF encode + README embed (`docs/demo/` 5 frames +
`docs/demo_storyboard.md` are ready) + NVDA/keyboard/mic gates + LinkedIn (+ optional
Streamlit link).
**Pending quota:** two-run flakiness check (24 calls with failover, or 2 days) — **UNBLOCKED
2026-09-13, not run.** Use `test_phase02.py --no-cache --failover --out=<versioned path>`;
+ AI-expander live smoke. **Nothing has been spent on Gemini since 2026-09-11.**
**Pending code:** `docs/phases/09_evidence_and_generation.md` steps **3** (BM25 re-rank inside
the gate + offline `synonyms_auto.json`) and **4** (Q3 answer-shape floor + named reverse_rel
fix). Steps 1 and 2 are DONE (2026-09-13). Phase 08 steps 4/5 are superseded by (3). Step 3 now
has a real target — vocab-mismatch is the weakest held-out class at 0.312 — and, for the first
time, an uncontaminated set to be judged on. Ablate on frozen-10 **and** held-out, always both.
Nothing is blocked.
**Housekeeping:** ~~a 0-byte stray file `D:NGORAG_review_judge.diff` (U+F03A in the name, from a
bad shell redirect) sits untracked in the repo root~~ — **RESOLVED, verified gone 2026-09-18.**
Nothing outstanding.
