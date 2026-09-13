# HANDOFF — start here (60 seconds, updated 2026-09-13)

> **Latest (2026-09-13): Phase 09 steps 1 and 2 DONE. Zero Gemini calls spent.**
> PRs #9 (`phase09/ops-hardening`) and #10 (`phase09/evidence-base`).
>
> **READ THIS BEFORE TOUCHING RETRIEVAL — the headline number changed meaning.**
> Held-out mean recall is **0.420 (n=25)** against frozen-10 **0.925**, delta **−0.505**.
> The frozen 10 are the questions the synonym map was *fitted on*; the held-out 30 are
> questions nothing has been tuned on. **0.925 was mostly fitting.** Quote both numbers or
> neither. Per class, vocab-mismatch is worst at **0.312** — the class the synonym map exists
> to fix — so **the hand-written map does not generalize**. That is step 3's target.
>
> Measured for the first time: **false-refusal 0/25 = 0.0%** on answerable held-out questions
> (the floor is *not* denying help to PWDs — ranking is the problem, not the gate), and
> **gate-level false-answer 5/5 = 100%** of off-corpus questions clear `MIN_SCORE`. The second
> is reported **ungated with its caveat and is NOT a reason to touch `MIN_SCORE`** (weak-overlap
> floor, not a semantic filter; inverted bands, `src/retrieve.py:26-44`; the semantic layer is
> the strict-prompt `NO_ANSWER_SENTENCE` path, which costs quota to measure).
>
> **Budget is 40/day, not 20** — `gemini-2.5-flash` and `gemini-2.5-flash-lite` draw from
> separate free-tier pools. `ask(failover=True)` uses the second pool on a **daily-cap** 429
> only, never a per-minute one, and records `model_used`.
>
> New commands: `scripts\test_phase09_ops.py` (38/38, zero network) · `scripts\eval_heldout.py`
> (retrieval-only baseline) · `test_phase02.py --no-cache --failover`.
>
> **Next: Phase 09 step 3**, then step 4. The two-run flakiness check is now *possible* but was
> NOT run (24 calls). Details: 2026-09-13 journal entry + the Results section of
> `docs/phases/09_evidence_and_generation.md`.

> **Previous (2026-09-11): Phase 06 CLOSED, Phase 08 steps 1/2/3/6a SHIPPED and live.**
> `main` @ `f4d18fe`. recall **0.800 → 0.925**, faith_audited **0.867 earned**
> (`MANUAL_FLAGS == []`), reverse_rel 0.630 arbitrated as a metric artifact.
> Live-verified on Render. Details in the 2026-09-11 journal entry; the pre-existing
> text below is kept as dated history and is superseded where it conflicts.
>
> **Planned next: `docs/phases/09_evidence_and_generation.md` (written 2026-09-11, NOT
> started).** Read that playbook first — a planning pass found three code facts that
> **reorder the Phase 08 backlog**, summarised under "Next, in this order" below. Phase 08
> steps 4/5 are superseded there, not merely deferred.

**Env:** `C:\conda-envs\drlca-rag\python.exe` (py 3.11). Rebuild: `requirements-rag.txt`.
Never install into `ds-general` / `base` / system Python. Full machine notes: `ENVIRONMENTS.md`.
Local app: http://localhost:8501 (`python -m streamlit run app.py` from `D:\NGORAG`).
**Live:** https://ngodisabilityrag.onrender.com (Render free, service
`srv-dah26opt0dsc73e9a350`, python 3.11, Oregon; auto-deploys on push to `main`).
Render CLI v2.27.0 installed (winget `Render.CLI`); auth in `~/.render/cli.yaml`.
Git: https://github.com/batestguy/NGOdisabilityRAG (`main`, pushed, tree clean).

**State:** Phases 01–05 DONE (re-verified 2026-09-10: bench 10/10, 03 16/16+7/7,
04 10/10, 05 **104/104**, boot import OK; NGO 10/10 HIGH incl. NAB/NNAD byte-verified).
Phase 02 fixA2 COMPLETE 12/12 (`test_phase02_results_cite-strict-v2-fixA2_2026-09-10.json`):
Q9 s.33 hallucination REMOVED (s.17 x3+general) but s.34-body omission remains
(recall 0.5); Q10 PARTIAL (2×s.46 correct + s.39 misattr of High-Court text —
same TOC-trap class, `MANUAL_FLAGS` now flags it); Q3 recovered (cl.29,30 5%);
Q8 five-years; Q5 correct-refusal ×4; R1/R2 verbatim DRAC refusal.
Phase 06 custom eval on fixA2 (`eval_phase06_results_fixA2-flagged_2026-09-10.json`,
pointer swapped): recall 0.800 PASS, faith_audited 0.967 PASS (Q10 flagged),
reverse_rel 0.630 FAIL gated (short-answer artifact — recorded FAIL, judge arbiter).
Phase 07 LIVE on Render (browser-verified banner + help query; README link in).
Helplines always on top: DRAC Toll-Free `08000-3000-100`, DRAC WhatsApp `08000-3000-10`.

## Next, in this order (full plan: `docs/phases/09_evidence_and_generation.md`)

Phase 08 steps 1 (synonym map), 2 (cite-constrain fix-B), 3 (judge) and 6a (answer cache)
are **DONE 2026-09-11 and live**. A planning pass on 2026-09-11 then found three code facts
that **change what should come next** — read `docs/phases/09_evidence_and_generation.md`
before picking anything up. In short:

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
3. **Shippable retrieval (zero quota) — NEXT.** BM25 re-rank *inside* the existing cosine gate
   (step 4's win, no ONNX) + an offline-computed `synonyms_auto.json` (step 5's win, no
   query-time model).
4. **Generation fix (quota-paced).** Q3 answer-shape floor + the named `reverse_rel` fix in
   its own commit + a fresh 12-call generation pass.
5. **Owner-side:** frames → GIF encode + README embed (`docs/demo/` + storyboard are
   ready) → NVDA/keyboard/mic gates → LinkedIn (+ optional Streamlit 2nd link).

## Standing facts (don't re-derive)

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
**Housekeeping:** a 0-byte stray file `D:NGORAG_review_judge.diff` (U+F03A in the name, from a
bad shell redirect) sits untracked in the repo root; deletion was permission-blocked twice, so
it needs removing by hand. It is in no commit.
