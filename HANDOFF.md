# HANDOFF — start here (60 seconds, updated 2026-09-11)

> **Latest (2026-09-11): Phase 06 CLOSED, Phase 08 steps 1/2/3/6a SHIPPED and live.**
> `main` @ `fcd2129`. recall **0.800 → 0.925**, faith_audited **0.867 earned**
> (`MANUAL_FLAGS == []`), reverse_rel 0.630 arbitrated as a metric artifact.
> Live-verified on Render. Details in the 2026-09-11 journal entry; the pre-existing
> text below is kept as dated history and is superseded where it conflicts.

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

## Next, in this order (full plan: `docs/phases/08_retrieval_upgrades.md`)

Steps 1 (synonym map), 2 (cite-constrain fix-B), 3 (judge) and 6a (answer cache) are
**DONE 2026-09-11 and live**. What remains:

1. **Phase 08 step 4 — rerank (local ONNX CPU, zero quota).** Top-20 → top-5,
   flag-gated so the TF-IDF path stays intact for ablation. ONNX export friction is
   the known risk — time-box it.
2. **Phase 08 step 5 — dense hybrid (Colab/Kaggle afternoon).** Embed 2,214 chunks
   once, ship vectors prebuilt, RRF-fuse with TF-IDF. Runtime stays offline. Do NOT
   replace TF-IDF; hybrid preserves citations + the per-doc design.
3. **Phase 09 — Q3 answer thinness.** The judge confirmed this is a REAL
   prompt/generation defect (Q3 recall is 1.000 — the material was in context and the
   answer ignored it). Fix at the prompt layer. Also carries the named `reverse_rel`
   fix: count only hits from docs `EXPECTED` names. Deliberately NOT applied on
   2026-09-11 — changing a metric in the session it failed is yardstick-tuning.
4. **Quota when available:** two-run flakiness check (12 generator calls on
   `gemini-2.5-flash`) + AI-expander live smoke. The answer cache makes repeats cheap.
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
  (16/16+7/7) · `test_phase04` (PASS) · `test_phase05` (104) · `eval_phase06.py --out=...`.
- Quota: **TWO limits, not one** (corrected 2026-09-11 — the missing one cost 9 calls).
  20/day/model **and 10 requests/MINUTE/model**. The per-minute 429 is
  `GenerateRequestsPerMinutePerProjectPerModel-FreeTier` and carries its own `retryDelay`
  (~37s) — it is NOT terminal and must be retried, not treated as the daily cap. A daily-cap
  429 stays pending and unfaked. `scripts/judge_phase06.py` has the working pattern (7s
  pacing, `_is_per_minute()`, bounded backoff, checkpoint after EVERY call).
  503-transients retry with backoff, same day OK. Models draw from **separate pools**:
  the judge run spent `gemini-2.5-flash-lite` and touched `gemini-2.5-flash` zero times.
- Answer cache live (`src/rag.py`, gitignored at `scripts/.answer_cache.json`): keyed by
  sha256(model + NUL + **whole rendered prompt**), so context and prompt version are in the
  key. Fails OPEN. Every hit sets `cached=True` and `test_phase02.py` persists it — a replay
  can never be written up as a fresh call.
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
**Pending quota:** two-run flakiness check (12 generator calls) + AI-expander live smoke.
**Pending code:** Phase 08 steps 4 (ONNX rerank) + 5 (dense hybrid); Phase 09 Q3 thinness +
the named reverse_rel fix. Nothing else is blocked.
