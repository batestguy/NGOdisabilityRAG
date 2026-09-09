# HANDOFF — start here (60 seconds, updated 2026-09-09 late session)

**Env:** `C:\conda-envs\drlca-rag\python.exe` (py 3.11). Rebuild: `requirements-rag.txt`.
Never install into `ds-general` / `base` / system Python. Full machine notes: `ENVIRONMENTS.md`.
Local app: http://localhost:8501 (server restarted 2026-09-09 with current code; reboot if down:
`python -m streamlit run app.py` from `D:\NGORAG`).
Git: https://github.com/batestguy/NGOdisabilityRAG (`main`, pushed, tree clean —
latest `17de7ef` readability fix).

**State:** Phases 01–05 DONE (all suites green: bench, 03 16/16+7/7, 04, 05 **94/94**).
Phase 06 custom eval DONE (recall 0.800, audited faithfulness 0.875; fix A applied).
Phase 07 deploy prep DONE (slim requirements clean-venv proven, README, 10/10 NGO
re-verified HIGH, key audit clean, repo pushed).
**Latest (this session):** Brave readability report FIXED + verified + pushed —
opaque sidebar (z-index 2 over main context), 0.88 main sheet, opaque excerpt cards,
top-of-run theme watcher (height=1), srcdoc race fix. Light/dark/HC all screenshot-
verified. Font deliberately unchanged (system sans; contrast was the defect).
Details: `STATUS.md`. Spec: `RAGNGO.txt`.
Helplines always on top: DRAC Toll-Free `08000-3000-100`, DRAC WhatsApp `08000-3000-10`.

## Tomorrow, in this order

1. **Full post-fix LLM re-run (FIRST, needs quota reset).** Yesterday's fix-A run died
    at 8/12 — the 429 names the limit verbatim: 20/day/model (`gemini-2.5-flash`).
    Run the whole 12-call pass, not a targeted retry: it completes Q8/Q9/R1/R2 AND
    gives the complete post-fix transcript the eval can point at AND the two-run pair.
    Command:
    `C:\conda-envs\drlca-rag\python.exe scripts\test_phase02.py --out=scripts/test_phase02_results_cite-strict-v2-fixA2_<date>.json`
    (probe first: 1-token QUOTA_OK check; probe + pass ≈ 13/20 — do NOT start the
    judge the same day.) Watch: **Q9 dignity re-cite** (fix-A confirmation: s.33 trap
    neutralized, expect s.17 or dropped) · Q8 · R1/R2 exact text · Q10 stays PASS?
    Then verdict table → journal + playbooks + commit.
2. **RAGAS-judge day (separate quota day, ~30 calls).** Custom proxies are floors with
    diagnosed artifacts (paraphrase / general-chunk blindness — see 06 playbook);
    the judge decides answer-relevancy. `ragas` is NOT installed (env protection);
    install only in `drlca-rag`, or use the Gemini-judge-by-hand pattern. Then:
    two-run check, manual-100% re-confirm → close Phase 06.
3. **Owner-side (needs your accounts/voice, no quota):** HF Space (Streamlit
  SDK) → `GOOGLE_API_KEY` in Space Secrets → smoke (3 legal + 2 help, helplines,
    cites) → paste link in README → 2–3 min demo video → NVDA / keyboard-only /
    live-mic gates → LinkedIn post.

## Standing facts (don't re-derive)

- Q5 penalties = correct refusal ×3 runs (retrieval miss; penalty clauses verified in
  corpus at Act cl.1/2/8/9,10/13/29,30 — dense/hybrid queued, NO synonym hack).
- Q10 false-refusal variance RESOLVED (refuse,refuse→answer; verbatim s.46 quotes).
- Precision 0.333 is BY DESIGN (per-doc merging trades it for recall) — never gate it.
- Coverage/reverse_rel custom misses are metric artifacts (documented) — don't tune
  yardsticks; escalate to the judge.
- Fix A: 14 Constitution TOC fragments → `general` in `const_ref`; ranking untouched;
  all suites green. Answer-level proof = Q9 in step 1.
- Eval script stays pointed at `test_phase02_results_cite-strict-v2_2026-09-09.json`
  (complete) until a COMPLETE post-fix transcript exists. Never fake LLM rows —
  429-pending stays pending. LLM runs → versioned files; dry runs → `--out`.
- Test commands (all via project python): `bench_phase01` (PASS) · `test_phase03`
  (16/16+7/7) · `test_phase04` (PASS) · `test_phase05` (94) · `eval_phase06.py`.
- CSS rules of the road (learned 2026-09-09): watermark div lives INSIDE
  stMainBlockContainer (z-1), so sidebar needs z-index 2; Streamlit's own section
  rules beat un-`!important` ones; height=0 iframes never mount (use 1); srcdoc
  scripts race `<body>` (DOMContentLoaded-ready wrapper); restarted server after
  edits (auto-reload once served mixed CSS); HC mode trips the luminance gate
  (bodyDark=true — harmless, palettes compose to AAA).

**Pending owner inputs:** HF Space + video + human gates + LinkedIn (GitHub push DONE).
**Pending quota:** everything in steps 1–2. Nothing else is blocked.
