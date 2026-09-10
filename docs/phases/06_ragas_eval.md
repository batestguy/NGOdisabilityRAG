# Phase 06 — RAGAS evaluation

## Goal
Prove answer quality with numbers, not adjectives. Spec targets: faithfulness > 0.85,
answer relevancy > 0.80, context relevancy > 0.75 — plus the 100% citation-accuracy
manual check from Phase 02.

## Entry criteria
- Phase 02 RAG pipeline stable (frozen prompt version + threshold).
- A ground-truth set: the 10 test questions with expected section/clause references
  (built during Phase 02's failure log — reuse it, don't rebuild it).

## Steps
1. **Install RAGAS in `drlca-rag`** (`pip install ragas` — project env only).
   If RAGAS drags heavy deps that threaten the env, fall back to the documented custom
   metrics (faithfulness-as-citation-coverage is already computable from Phase 02 logs).
2. **Run the three spec metrics** on the 10-question set. Record per-question scores,
   not just means — a mean of 0.86 hiding two 0.5s is a finding, not a pass.
3. **Diagnose misses**: every sub-target score traces to retrieval (wrong chunk),
   prompt (right chunk, wrong use), or corpus (right answer not in corpus). Fix at the
   correct layer — do not prompt-engineer around a retrieval miss.
4. **Re-run after each fix** until targets hold across two consecutive runs (flakiness check
   against free-tier LLM variance).

## Exit criteria
- [ ] faithfulness > 0.85, answer relevancy > 0.80, context relevancy > 0.75, recorded.
- [ ] Manual citation check still 100% on the test set.
- [ ] Every miss has a diagnosed layer + fix (or a written reason it can't be fixed free-tier).

## Status (2026-09-09 — custom eval DONE, judge DEFERRED to quota reset; fixA2 COMPLETE 2026-09-10)
- 2026-09-10: COMPLETE post-fix transcript exists (`test_phase02_results_cite-strict-v2-fixA2_2026-09-10.json`, 12/12). Verdict table: manual cite-accuracy 11/12 claims clean EXCEPT Q10 3rd claim misattributes s.46 High-Court text to s.39 (TOC-trap class, mechanical blind — same as Q9 s.33 was); Q9 s.33 removed but s.34-body omission remains (recall 0.5). Offline eval on fixA2 (tmp, no overwrite): recall 0.800 PASS, faith_audited 1.000 mechanical (overstates — Q10 s.39 blind), reverse_rel 0.630 FAIL gated>0.80 (drivers Q3/Q8/Q10 short answers; proxy punishes concise-correct — recorded FAIL with reason,   RAGAS judge is arbiter, separate quota day). Pointer swapped to fixA2 transcript; flagged rerun `eval_phase06_results_fixA2-flagged_2026-09-10.json` (recall 0.800, faith 0.967 with Q10 s.39 flagged, reverse 0.630 FAIL). Remaining: RAGAS-judge run.
- Script: `scripts/eval_phase06.py` (zero-LLM proxies; design + trade-offs in
  docstring) + corpus-verified EXPECTED truth (s.33 / Act-cl.10 exclusions).
  Baseline `eval_phase06_results_2026-09-09.json`: recall 0.800 PASS,
  faith_audited 0.875 PASS, precision 0.333 diagnostic, coverage 0.723 +
  reverse_rel 0.667 both diagnosed metric artifacts (paraphrase / general-chunk
  blindness), kept visible.
- Fix A applied (TOC fragments → general in `const_ref`; 14 relabeled, ranking
  untouched, all suites green); post-fix `eval_phase06_results_fixA_2026-09-09.json`
  identical means, Q9 auto==audited. Answer-level confirmation needs LLM rerun.
- Pending (quota): RAGAS-judge run (~30+ calls) as answer-relevancy decider +
  fix-A answer confirmation + Q10 retry-once + two-run flakiness check.
  Misses by layer in journal; ragas NOT installed (env protection, playbook-sanctioned).
- Exit criteria: [x] recall>0.75 · [x] faithfulness>0.85 (audited) ·
  [~] answer relevancy (judge pending) · [ ] manual-100% re-confirm · [ ] two runs.
- 2026-09-09 fix-A run (`test_phase02_results_cite-strict-v2-fixA_...json`, 8/12 —
  429 names the limit: 20/day/model): Q10 VARIANCE RESOLVED (verbatim s.46 quotes,
  PASS); Q1-Q7 stable; Q5 correct-refusal x3; Q8/Q9/R1/R2 honest-pending (superseded
  by fixA2 12/12 above). Pointer swapped to fixA2-flagged
  (`eval_phase06_results_fixA2-flagged_2026-09-10.json`).

## Record results in
`LEARNING_JOURNAL.md` → full score tables, framework notes (RAGAS vs custom trade-offs —
the spec explicitly wants this comparison), variance observations.

## Traps
- RAGAS itself calls LLMs (cost/latency on free tier) — batch eval runs, cache everything.
- Don't tune the test set to the metrics (no editing questions to make scores pass).
  New questions may be added; existing ones are frozen once baselined.
