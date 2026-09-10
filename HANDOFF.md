# HANDOFF — start here (60 seconds, updated 2026-09-10)

**Env:** `C:\conda-envs\drlca-rag\python.exe` (py 3.11). Rebuild: `requirements-rag.txt`.
Never install into `ds-general` / `base` / system Python. Full machine notes: `ENVIRONMENTS.md`.
Local app: http://localhost:8501 (`python -m streamlit run app.py` from `D:\NGORAG`).
**Live:** https://ngodisabilityrag.onrender.com (Render free, service
`srv-dah26opt0dsc73e9a350`, python 3.11, Oregon; auto-deploys on push to `main`).
Render CLI v2.27.0 installed (winget `Render.CLI`); auth in `~/.render/cli.yaml`.
Git: https://github.com/batestguy/NGOdisabilityRAG (`main`, pushed, tree clean —
latest `b2b8dbc` deploy-live docs).

**State:** Phases 01–05 DONE (re-verified 2026-09-10: bench 10/10, 03 16/16+7/7,
04 10/10, 05 **96/96**, boot import OK).
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

## Next, in this order

1. **RAGAS-judge day (needs quota reset).** 2026-09-10 spent ~13/20
   (`gemini-2.5-flash`): probe + 10 + Q3/R2 retry. Run judge (~30 calls) fresh
   day: it decides answer-relevancy (reverse_rel 0.630), Q10 s.39, Q9 s.34.
   `ragas` NOT installed (env protection); install only in `drlca-rag`, or
   Gemini-judge-by-hand. Then: two-run check, manual-100% re-confirm → close 06.
2. **3-legal live smoke** (excerpts/cites render offline — safe; AI expander =
   quota). Then comprehensive demo GIF + NVDA / keyboard-only / live-mic gates +
   LinkedIn (owner).
3. **Optional variety:** 2nd link on Streamlit Community Cloud (share.streamlit.io
   → repo → `app.py` → Secrets `GOOGLE_API_KEY`). HF Spaces is DROPPED
   (Streamlit SDK deprecated 2025-04 → Docker/PRO only; Static can't run Python).

## Standing facts (don't re-derive)

- Q5 penalties = correct refusal ×4 runs (retrieval miss; penalty clauses verified in
  corpus at Act cl.1/2/8/9,10/13/29,30 — dense/hybrid queued, NO synonym hack).
- Q10: v2 false refusal → fixA variance resolved (s.46 quotes) → fixA2 PARTIAL
  (s.39 3rd-claim misattr). Q9: v2 s.33 trap → fixA2 removed, s.34 still missing.
- Precision 0.333 is BY DESIGN (per-doc merging trades it for recall) — never gate it.
- Coverage/reverse_rel custom misses are metric artifacts (documented) — don't tune
  yardsticks; reverse_rel stays recorded FAIL until the judge rules.
- Fix A: 14 Constitution TOC fragments → `general` in `const_ref`; ranking untouched.
  Fix-A2 flag: `("Q10", "Constitution s. 39", "high court")` in `MANUAL_FLAGS`.
- Eval script points at fixA2 transcript now. Never fake LLM rows.
  LLM runs → versioned files; dry runs → `--out=<temp path>` (space form ignored!).
- Test commands (all via project python): `bench_phase01` (PASS) · `test_phase03`
  (16/16+7/7) · `test_phase04` (PASS) · `test_phase05` (96) · `eval_phase06.py --out=...`.
- Quota: 20/day/model (`gemini-2.5-flash`); 503-transients retry with backoff, same day OK.
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

**Pending owner inputs:** demo GIF + human gates + LinkedIn (+ optional Streamlit link).
**Pending quota:** RAGAS judge + AI-expander live smoke. Nothing else is blocked.
