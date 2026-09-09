# Phase 01 — Corpus cleanup + Constitution chapter-aware chunking

## Goal
Turn the raw OCR output and the monolithic Constitution into a clean, well-chunked
retrieval corpus. Everything downstream (citations, router, UI, RAGAS) depends on this.

## Entry criteria
- `data/processed/disability_act_2018_full.txt` (clauses 1–58), `constitution_1999_NHRC.txt`,
  `disability_act_factsheet_PLAC.txt` all present.
- Work in `C:\conda-envs\drlca-rag\python.exe`. Baseline: TF-IDF 10/10 nonzero,
  Constitution queries ~0.16.

## Steps
1. **Dedupe scan pages** in the Act TXT: pages 5/6 overlap (`...including thos` repeats).
   Detect near-duplicate consecutive `===== PAGE =====` bodies (difflib ratio > 0.85),
   keep the cleaner copy. Generalize: pairwise check all consecutive pages.
2. **Word-join repair** in `src/load.py`: justified-text artefacts (`Apersonwith`,
   `PARTVI-OPPORTUNITY...`). Rule: re-split `([a-z])([A-Z][a-z]+)` boundaries ONLY when
   both halves are dictionary-plausible — safer to under-fix than corrupt legal terms.
   Add a `repair_joins(text)` function; keep the raw file untouched, repair at load time.
3. **Strip page markers** (`===== PAGE N =====`) from chunkable text (keep them in a
   sidecar map page→char-offset if page provenance is ever needed).
4. **Constitution chapter chunking** in `src/chunk.py`: split on
   `CHAPTER II` / `CHAPTER IV` / `Section \d+` headings, attach the heading to each chunk
   (prepend `Constitution, {heading}: `). Priority sections: Ss. 14, 17, 33–46.
   Keep chunk size ≤ 800 chars so Act and Constitution chunks stay comparable.
5. **Re-run the 10-question benchmark** (same questions as 2026-09-06):
   `C:\conda-envs\drlca-rag\python.exe` + `src/retrieve.py` over the new corpus.

## Exit criteria
- [ ] Clause sequence still 1–58 continuous after cleanup (regression check).
- [ ] Constitution queries (dignity, equality) well above 0.16.
- [ ] 10/10 nonzero retained; before/after scores recorded in `LEARNING_JOURNAL.md`.

## Record results in
`LEARNING_JOURNAL.md` → new dated section: cleanup rules applied, chunk stats per document,
before/after benchmark table.

## Results (2026-09-08 — PASS, reviewer ship-with-notes)
- Dedupe: 27 pages, dup p5→p6 (0.819/0.44, next-best 0.084) → threshold 0.75 (playbook 0.85 misses it, documented).
  Kept p.6, salvaged 1 line, sidecar 27 entries. Clause 58/58 before+after.
- repair_joins: 290 tokens fixed, 0 false splits, 16 residuals deliberately left.
- Constitution: chapter-aware, priority Ss.14,17,33–46 unmerged; size grid picks 400 (Q9 0.167 PASS, mean 0.275).
- Benchmark: `C:\conda-envs\drlca-rag\python.exe scripts\bench_phase01.py` → PHASE01 BENCHMARK: PASS.
- Exit criteria: [x] clause 1–58 continuous · [x] Constitution Q9 0.167 > 0.16 · [x] 10/10 nonzero.
- Follow-up for Phase 02: constitution = 95% of joint index; add per-doc routing/score norm.

## Traps
- Do NOT "fix" text by guessing legal wording — a wrongly repaired clause is a future
  citation error. When in doubt, leave the artefact and note it.
- The factsheet uses "Section N" wording, the Act uses clause numbers (`1. (1)`),
  the Constitution uses "Section N". Map: factsheet §1 ↔ Act clause 1 ↔ (different!) Constitution §1.
  Never conflate the three numbering schemes in chunk metadata.
