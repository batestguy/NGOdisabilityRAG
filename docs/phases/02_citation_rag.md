# Phase 02 — Citation RAG (strict prompt + refusal threshold)

Locked decision: **strict with refusal** — answer only from retrieved chunks with section
cites; refuse when retrieval is weak.

## Goal
Wire the retriever to a free-tier Gemini LLM so legal answers always carry direct
citations (e.g. "Section 17 of the Act provides for free education..."). Spec target:
10 sample legal questions answered with citations; citation accuracy 100%.

## Entry criteria
- Phase 01 exit criteria met (clean corpus, Constitution queries healthy).
- `GOOGLE_API_KEY` in Windows env. `google-genai 2.22` already in `drlca-rag`.
  Model: `gemini-2.5-flash` (`gemini-2.0-flash` is retired — do not use).

## Steps
1. **Retrieval contract** in `src/retrieve.py`: return `(doc_id, section_ref, text, score)`
   triples. Add a `MIN_SCORE` threshold constant; below it the caller gets a refusal
   signal instead of chunks. Calibrate `MIN_SCORE` from the Phase 01 benchmark
   (between the weakest good hit and the strongest bad hit).
2. **Citation-forcing prompt**: system instruction requires every factual claim to cite
   `doc_id + section/clause` (e.g. `[Act cl. 31]`, `[Constitution s. 17]`, `[Factsheet §6]`);
   no citation → no claim; empty retrieval → fixed refusal message directing the user
   to the DRAC helplines. Plain-language toggle: same facts, simplified wording.
3. **Test set**: the 10 benchmark questions, answered end-to-end. Record prompt version,
   model name, and per-question pass/fail (correct cite? no hallucinated sections?).
4. **Failure log**: every refusal and every wrong cite goes in the journal with the
   retrieval scores that caused it — this is the data that justifies future tuning.

## Exit criteria
- [ ] 10/10 questions answered with at least one correct section/clause citation.
- [ ] 0 hallucinated section numbers across the test set (manual check).
- [ ] Refusal path demonstrated (feed a query with no supporting chunks, show refusal).

## Record results in
`LEARNING_JOURNAL.md` → prompt versions tried, threshold calibration, per-question table.

## Status (2026-09-09 — FULL v2 RE-RUN DONE, exit call below; fixA2 COMPLETE 2026-09-10)
- fixA2 2026-09-10 (`test_phase02_results_cite-strict-v2-fixA2_2026-09-10.json`, 12/12, reviewer SEND-BACK addressed here): Q9 hallucination REMOVED (s.17 x3+general, zero s.33) but s.34-body omission remains (recall 0.5) · Q3 recovered (cl.29,30 5%) · Q8 five-years · Q10 PARTIAL (2/3 claims s.46 correct; 3rd misattributes s.46 High-Court content to s.39 — same TOC-trap class as Q9 s.33, mechanical checks blind) · R1/R2 verbatim refusal · Q5 correct-refusal x4. Path: full 12-pass 10/12 (Q3+R2 transient 503) + targeted retry first-attempt OK (~13/20 quota, no judge same day).
- Run: `scripts/test_phase02_results_cite-strict-v2_2026-09-09.json` (12/12 LLM calls,
  0 errors, model gemini-2.5-flash re-confirmed via live list-models + QUOTA_OK probe).
- Verdicts: Q1 PASS (N100k chunk-quote proven) · Q2/Q3/Q4 PASS · Q6 PASS (cl.11 fix) ·
  Q7 PASS w/ note (merged-tag ban holds) · Q8 PASS · Q9 PARTIAL (s.17 equality genuine;
  dignity@[s.33] misattributes TOC-line chunk, correct is s.34 — the 1 miss) ·
  Q5 correct refusal (retrieval miss → Phase 06) · Q10 FALSE refusal (s.46 chunk holds
  legal-aid text at 0.219; LLM-variance, 2nd occurrence) · R1/R2 exact-refusal PASS.
- Mechanical: all cite_check True, 0 merged tags, 0 invented numbers, no key in transcript.
- Exit criteria: [~] 8/10 cited (Q5 correct-layer, Q10 logged false refusal) ·
  [ ] 0 hallucinations (1 misattribution: Q9 s.33 TOC-trap; fixA2 removes it but adds Q10 s.39 same-class — see fixA2 line) · [x] refusal demo (gate + LLM layers).
- History: pre-fix v1 run (8/10, Q6/Q7 FAILs → ref-extraction + prompt fixes);
  fixes verified mechanically (stemmer convergence, cl.11 label, tag regex).
  Phase 01 bench still PASS post-stem (mean 0.293, Q9 0.178).

## Traps
- Gemini model names retire without warning (2.0-flash died mid-project). Re-resolve the
  model name with a list-models call at the start of the session, don't hardcode blindly.
- Free-tier rate limits: space LLM calls with sleeps; batch the 10 questions, don't hammer.
- Never let the LLM "clean up" citations — cite the chunk text verbatim, even with OCR quirks.
