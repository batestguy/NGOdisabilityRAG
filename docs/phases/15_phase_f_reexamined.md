# Phase F — re-examined (2026-10-15): measure an offline static dense arm first, fine-tune only if it earns it

**Status: PLANNED. Planning session only: no code, zero quota.** It supersedes
`10_corpus_rebuild_and_dense.md` **M4 as written**. That text stays for reference only; do not
execute it. The order stays **E → G → F**, and E and G are closed.

## Why M4 can't run as written

| M4 premise | Status 2026-10-15 |
|---|---|
| "Deliverable 1: a better dense arm than M2" | **Gone.** M2 was declined for launch (E5.6). There is no M2 arm to beat, and `test recall@6 above M2` can't be evaluated. |
| "Deliverable 2: distil tier 2 from the dense arm" | **Gone in that form.** The tier ladder was never shipped; tier 1 (Gemini embeddings) doesn't exist. |
| Fine-tuned transformer at query time | **Forbidden.** It needs ONNX/torch in `requirements.txt`, and Render free is 512 MB. Colab gives free *training*, not free *serving*. |
| Static embedding table, numpy-only at serve time | **Survives.** A matrix lookup plus mean-pool, no new runtime package. It is offline, so the zero-network invariant and the privacy position stay intact. That is its advantage over M2, which sent every question to Google. |

**What changed the question.** E2, E3 and E4 showed that *term-level* lexical signals
(BM25, corpus synonyms, the OOV bridge) don't reach the `+0.206` pool headroom; E4a bought only
+2 test questions. A static sentence embedding is still bag-of-words at heart. But scoring a
**whole chunk against a whole query** in a dense space is a different signal from adding terms
to a TF-IDF query. It's the cheapest untested idea that differs in kind. **The prior is still
"decline"**, and the gate is set strictly in advance, as it was for E4a.

**Off the shelf before fine-tuning.** Distilled static models already exist (for example
`minishlab/potion-base-8M`, a model2vec distillation of a BGE-class encoder: 256-dim, about
15 MB at f16). If an off-the-shelf table can't move dev, a fine-tuned one built on synthetic
queries is unlikely to rescue it on free tier. If it *can*, fine-tuning becomes a measured
follow-up, not a leap. So the order is **F0 measure → F1 port → (F2 fine-tune, optional and
after launch)**.

## Steps

### F0 — Reach + arm, dev only, measure-only (zero quota, one session)
Branch `phase10/f0-static`. Nothing on the shipping path changes.

1. **Control first.** Reproduce `scripts/baseline_phaseE_2026-09-24.txt` on the current `main`
   (post cl.1 fix: same recall_strict, 0/212; captures `runs\cl1_after\`).
2. **Model and env.** `pip install model2vec` into **`C:\conda-envs\drlca-rag` only**, as a dev
   dependency (`requirements-rag.txt`, never `requirements.txt`). Download one model to
   `D:\NGORAG\runs\f0_static\` (gitignored). **The model is fixed now: `potion-base-8M`.** The
   one allowed retreat is `potion-retrieval-32M` if 8M's dev reach (step 4) is 0.
3. **Author a probe set BEFORE measuring** (`data/eval/register_probes.json`, ~20 queries:
   Nigerian lay register + **Pidgin**, e.g. "dem fit sack me because say I dey for wheelchair?").
   Each probe carries a corpus-verified expected ref. It is report-only and never gates; it
   exists because nothing in the stack has ever been measured on Pidgin and real users will type it.
4. **Reach (`scripts/f0_reach.py`, dev only):** among the failing dev questions, how many have
   their expected chunk in the static arm's per-doc top-k but not TF-IDF's? Oracle ceiling, as
   E4.0 did. **If reach is 0 after the one retreat, stop: F is declined without an arm.**
5. **Arm (`scripts/ablate_static.py`):** per-doc **selection** fusion. For each doc, RRF over the
   TF-IDF and static rankings (**k_rrf = 60, equal weights, fixed now**), then take k=4/doc,
   top_n=12 as shipped. It has to be selection, not ordering: E2 proved ordering is inert at
   `top_n == 3k`. **The `MIN_SCORE` gate stays on the TF-IDF top score**, so the arm structurally
   can't move a refusal. `calibrate_refusal` must still show 0/212 with the arm on, as proof.

**F0 ship gate (all required, written before any number is seen):**
* dev recall_strict: **net ≥ +2 questions, and 0 questions down on frozen-10**;
* only then read **test2 once**: a net win (≥ +1 question), with `vocab-mismatch` not down;
* `calibrate_refusal` **0/212** and false refusals 0 on every set, with the arm on;
* serving cost: artifact ≤ 40 MB, cold load ≤ 2 s on the dev box, **numpy only at serve time**.

**If dev fails, decline without reading test2** (E4a's rule), record it, and close F.

### F1 — Port (only if F0 passes)
Vendor a numpy-only `src/static_embed.py` (tokenise → lookup → mean-pool → normalise). Assert
parity ≥ 0.9999 cosine against `model2vec.StaticModel` on 500 strings, including every eval
question. Pin `numpy` explicitly in `requirements.txt`; that is the only runtime diff allowed.
Precompute the chunk matrix at build time, keyed on the corpus sha256 (fail hard on mismatch,
exactly like `oov_bridge.json`). Re-run all 16 harnesses and re-pin with a reason. The merge
is the user's call.

### F2 — Fine-tune the static table (optional; recommended only AFTER launch)
M4's synthetic-query, hard-negative and decontamination design still applies (see
`10_corpus_rebuild_and_dense.md` M4). The target becomes **fine-tune the transformer, then
model2vec-distil it into the same static artifact F1 ships**, and the bar becomes "beats the F1
off-the-shelf table". **Recommendation: do it after launch, on real query logs.** Synthetic
queries reuse the class taxonomy that authored the eval sets, while real logs fix the query
distribution the rest of the stack has been guessing at. It is the same reasoning as M2's
"revisit post-launch" (E5.6).

## Not Phase F, but queued before launch
* **Generator refusal threshold** (G exploratory, CD1.t2 "so can they fire me?" refused over
  `[Act cl. 28]`). `calibrate_refusal`'s 0/212 measures the retrieval floor only. Before the AI
  expander is *recommended*, write a small probe set of in-corpus, lay-register questions and
  count LLM-layer refusals. It needs quota (~10 calls), so plan it into a day's budget.
* OCR slips for the user's review: cl.12 `N1,0o0`, cl.20 `selivere` (the corrections-file route
  and a human sign-off apply; `CLAUDE.md` normally leaves quirks alone).

## Exit criteria
F is **closed** when either (a) F0 is declined and the decline is recorded with its numbers, or
(b) F1 is merged to local `main`, every harness is green and the re-pins are explained. **Then
the deploy decision goes to the user.** Every phase in the E → G → F order will be done.

## Results

### F0 pre-measurement amendment (2026-10-15, written and committed before any F0 number)
Fixed while reading the harness code, before measuring:
* **The gated metric is budget-matched by construction.** `recall_strict` (`ablate_oov_bridge.measure`)
  scores all 12 `select_top` hits *before* the display's per-hit `MIN_SCORE` trim. Arm D swaps
  *which* 4 chunks each doc contributes, so both arms score exactly 12. The E1b "more chunks
  inflates recall" trap can't apply to the gate.
* **Arm D, exactly:** the TF-IDF side is the shipping effective query (hand map + OOV bridge, both
  expansion gates), ranked over each doc's whole index. The static side is the **raw user
  query** (no expansion) embedded by `potion-base-8M`, with cosine against each chunk's embedding,
  per doc. Per doc, RRF `1/(60+r_tfidf) + 1/(60+r_static)`, top 4, ties broken by TF-IDF rank.
  Each Hit keeps its **TF-IDF** score.
* **Refusal is S's decision, verbatim.** D refuses iff S refuses, computed on S's hits. Refusal
  invariance therefore holds by construction. The 0/212 requirement is met by the identity, and
  the harness asserts it per row rather than re-running `calibrate_refusal`.
* **Shown-on-page (report-only):** D's 12 after the current per-hit TF-IDF trim (what today's
  display would render), and the untrimmed 12. If a gain lives only in the untrimmed set, F1
  would need a display change. That is a finding to record, not a reason to re-gate.
* **Reach:** dev questions where S misses an expected ref and the static-only per-doc top-4
  contains it.

### F0 — MEASURED AND DECLINED 2026-10-15. Zero quota. test2 NOT read. PHASE F CLOSED.
Harness `scripts/ablate_static.py` with the `model2vec==0.10.0` dev pin lives **only** on branch
`phase10/f0-static` at `27ed13d` (pushed as an archive; it does not deploy). Same precedent as E2a/E3a:
declined code doesn't go on `main`. `model2vec` is installed in `drlca-rag` (dev env) and touched
neither numpy (2.4.6) nor scikit-learn (1.9.0). The model is in `runs\f0_static\` (gitignored).

| set | S (ship) | D (static RRF) | questions |
|---|---|---|---|
| frozen-10 recall_strict | **0.734** (reproduced) | 0.676 | 0 up / **2 down** (Q4, Q8) |
| dev recall_strict (SELECTOR) | **0.613** (reproduced) | 0.620 | 1 up (H4) / 1 down (H17), **net 0** |
| dev `vocab-mismatch` (n=8) | 0.625 | 0.688 | — |
| dev `cross-document` (n=7) | 0.476 | 0.429 | — |
| register probes, report-only (n=20) | 0.650 | 0.750 | 3 up (P03, P15, P16) / 1 down (P01) |
| false refusals | none | none (by identity) | — |

**Gate: dev net +0 (needed ≥ +2), frozen-10 down 2 (needed 0) → DECLINE.** The playbook's
one retreat (`potion-retrieval-32M`) was conditioned on dev reach = 0. Reach was **3 of 11**
(H4, H11, H14; oracle ceiling 0.720), so the retreat didn't apply and wasn't run.
**Harness check:** with the static ranking replaced by the TF-IDF ranking, D reproduces S on
35/35 questions, so the decline isn't a wiring bug.

**What the numbers say.** The static arm does what a semantic signal should on vocabulary
mismatch (dev 0.625 → 0.688) and on lay/Pidgin register (probes +3/−1). But fusing it costs
precise lexical hits elsewhere (frozen-10 Q4/Q8, cross-document), and dev nets to zero. **Even a
pass would have needed a display change for F1:** D's chunks carry lower TF-IDF scores, so today's
per-hit trim shows **4.08** of D's 12 on dev against **6.92** for S, and the shown-path recall
*falls* (0.473 → 0.460). Report-only, recorded so it doesn't have to be rediscovered.

**For later (post-launch, not now).** The probe result is the one signal in this direction that
points up, and it's on register, the gap the curated sets under-sample. With real query logs, a
*register-routed* use (static arm only when the query is Pidgin / out-of-vocabulary-heavy) is the
hypothesis worth testing. Pre-declare it then; it is **not** being tuned now, after the read.

### Phase F exit (2026-10-15)
Exit (a) holds: F0 declined and recorded with its numbers. F2 (fine-tune) isn't scheduled:
its premise was "improve an arm that ships", and none does. **All phases in the E → G → F order are
done.** Before launch: the generator-refusal probe set (~10 calls, the CD1.t2 class) and the user's
call on cl.12 / cl.20. **Then deployment, which is the user's decision.**
