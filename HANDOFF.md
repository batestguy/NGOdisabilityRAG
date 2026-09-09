# HANDOFF — start here (60 seconds)

**Env:** `C:\conda-envs\drlca-rag\python.exe` (py 3.11). Rebuild: `requirements-rag.txt`.
Never install into `ds-general` / `base` / system Python. Full machine notes: `ENVIRONMENTS.md`.
Live app (if server still up): http://localhost:8501 (`python -m streamlit run app.py`).

**State:** Phases 01, 03, 04, 05 DONE (all test suites green). Phase 02 IN PROGRESS
(blocked on Gemini free-tier quota reset — 20/day exhausted). Phases 06, 07 not started.
Details: `STATUS.md`. Spec: `RAGNGO.txt`. Agent rules: `AGENTS.md`. Helplines always on top:
DRAC Toll-Free `08000-3000-100`, DRAC WhatsApp `08000-3000-10`.

## Known issue (fix next): dark mode still has invisible text/buttons
The config.toml theme fixed most of it (verified by screenshot), but the user reports
**some text and buttons still don't display in dark mode**. Suspects: Streamlit widgets
whose colors come from neither config.toml tokens nor our CSS (e.g. mic-recorder iframe,
expander headers, slider labels, toast/alerts), plus the `white-on-#3fb950` primary-button
contrast note in the journal. Repro: set browser to dark, walk every control + an answer
+ the LLM expander, screenshot each, fix at the token/CSS layer (never hardcode light colors).

## Incomplete phases (work in this order)
1. **Phase 02 re-run (first, needs quota):** run
   `C:\conda-envs\drlca-rag\python.exe scripts\test_phase02.py --out=scripts/test_phase02_results_cite-strict-v2_<date>.json`
   (12 calls, 6s spacing) → manual verdict table (Q1 N100k chunk-quote proof, Q9 dignity@s.33,
   Q5 refusal layer, R1/R2 exact refusal text) → exit call (10/10 cited, 0 hallucinations).
   Q5 likely still refuses (retrieval miss → Phase 06 material, do NOT synonym-hack).
2. **Dark-mode residual** (above) — fix + screenshot both modes + extend `scripts/test_phase05.py`.
3. **Phase 06 RAGAS eval:** install ragas in drlca-rag only (or custom faithfulness-as-citation-coverage
   fallback); targets faithfulness >0.85, answer relevancy >0.80, context relevancy >0.75; fix misses
   at the correct layer (retrieval vs prompt vs corpus); Q5 vocabulary gap (fine/offence) belongs here
   (dense/hybrid retrieval or query-expansion — spec research areas).
4. **Phase 07 deploy + docs:** `app.py` to Hugging Face Spaces (slim requirements, no OCR/ONNX at boot,
   secrets via Spaces Secrets), smoke test 3 legal + 2 help queries, README + architecture diagram +
   demo video + spec-checklist audit. Ship only verified NGO rows (NAB/NNAD recheck due; full CSV
   re-verification stamped 2026-09-08, 3-month expiry).
5. **Human-only before deploy:** NVDA pass, physical keyboard-only run, live mic/read-aloud + denial
   states, Spaces cold-start timing, light-mode eyeball of the watermark UI.

**Pending user inputs:** none blocking — NGO verification DONE 2026-09-08 (10 verified, 2 pruned;
table in `LEARNING_JOURNAL.md`). Quota reset timing is the only external dependency.

**Rules:** every build session ends updating `STATUS.md` + the active playbook's results.
Agentic workflow: plan in main session, execute via subagents (`ml-builder` build,
`ship-reviewer`/`general` review), verify by execution, record results. Never fake LLM rows —
pending stays pending. Test commands: `bench_phase01` (PASS), `test_phase03` (16/16),
`test_phase04` (10/10), `test_phase05` (69 asserts) — all via the project python.
