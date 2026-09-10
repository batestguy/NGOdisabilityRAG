# Phase 08 — Retrieval upgrades ($0 free-tier path, planned 2026-09-10)

## Goal
Close the measured gaps (fixA2-flagged: recall 0.800, faith 0.967 with Q10
flagged, reverse_rel 0.630 FAIL) using only free-tier means: `drlca-rag` env,
Gemini free 20/day, Render free, local CPU/ONNX, Colab/Kaggle. No paid APIs
(Cohere/Voyage), no Pinecone/GPU, no fine-tuning on 10 labels.

## Background (why this order)
2026 industry consensus (researched 2026-09-10): RAG quality comes from
retrieval engineering in this leverage order — chunking → hybrid retrieval →
rerank → query transformation → eval-gated iteration. Our 10Q evidence maps
cleanly: Q5 recall 0.0 = vocabulary mismatch (needs hybrid/synonyms); Q10 s.39
+ Q9 s.33 = TOC-trap misattribution (needs cite-constrain); Q3/Q8 thin answers
= relevancy-proxy failure (needs judge arbitration, then answer-shape floor).
Each step below is validated against the FROZEN 10Q set + `eval_phase06.py`
unchanged (apples-to-apples) before the next begins. Quota cost before the
judge: **zero**.

## Steps

### 1. Legal synonym map (FIRST — zero quota, ~1 session)
- **What:** curated query-expansion map in `src/retrieve.py` applied before
  TF-IDF scoring (~30 entries: penalty→offence/fine/imprison/prison,
  sack→dismiss/terminat/fired, house→building/premises, ...).
- **Why first:** attacks Q5 (recall 0.0) with no dependencies, no quota, no
  new packages. Frozen-set = deterministic, reviewable.
- **Validate:** 10Q bench — Q5 nonzero, Q1–Q4 stable (watch Q4 +padding note),
  03/04 suites green.
- **Trap:** a synonym map is NOT a license to hack scores — entries must be
  genuine legal vocabulary, logged in the journal; never add a term to fix one
  question that misroutes another (run full matrix every change).

### 2. Cite-constrain fix-B (zero quota, ~1 session)
- **What:** citation numbers must come from the chunk's own `ref` field, never
  from numbers appearing in chunk *text*; extend `_is_toc_fragment` (fix-A) to
  numbered-list chunks.
- **Why:** kills the TOC-trap class mechanically (Q9 s.33, Q10 s.39) instead of
  by hand audit. Mechanical checks are currently blind to it.
- **Validate:** re-score fixA2 transcript — Q10 claim-3 flips to flagged WITHOUT
  the `MANUAL_FLAGS` entry; faith_audited stays honest; all suites green.

### 3. RAGAS-judge run (needs FRESH quota day, ~30 calls)
- **Why here (not earlier):** the judge arbitrates what is real vs artifact
  (reverse_rel 0.630, Q3/Q8 thinness, s.39/s.34 dispositions) BEFORE we build
  fix-B/rerank on top. `ragas` installs only into `drlca-rag`, or
  Gemini-judge-by-hand pattern.
- **Then:** two-run check + manual-100% re-confirm → fix-B scope locked
  (prompt floor? cite-constrain enough?) → close Phase 06.

### 4. Local cross-encoder rerank (zero quota, ~1 weekend)
- **What:** rerank top-20 → top-5 with a small local model (MiniLM-class via
  ONNX CPU — same path as the RapidOCR win). Flag-gated; TF-IDF path intact
  for ablation. Fallback: FlashRank (tiny, CPU-first).
- **Why:** industry's highest-ROI add (+10–30pp typical); our corpus (2,214
  chunks) makes CPU rerank milliseconds-cheap.
- **Validate:** recall on 10Q + latency <50ms budget (Phase 04 pattern);
  skip paid reranker APIs (Cohere/Voyage) — out of budget by design.
- **Trap:** ONNX export friction is the known risk; time-box it, keep the
  flag so the pipeline ships with or without it.

### 5. Dense leg of hybrid (Colab/Kaggle afternoon, runtime stays offline)
- **What:** off-the-shelf MiniLM embeddings for 2,214 chunks (embed ONCE on
  free Colab/Kaggle GPU, ship vectors as a prebuilt file like the corpus) +
  RRF fusion (k=60, no normalization) with TF-IDF.
- **Why:** pretrained transfer learning closes paraphrase gaps TF-IDF cannot;
  NO fine-tuning (10 labels = overfit). Do NOT replace TF-IDF — hybrid
  preserves citations + per-doc design and gives a sparse/dense/hybrid
  ablation story for the journal.
- **Validate:** unchanged `eval_phase06.py`; dense must earn its place on
  numbers, especially Q5-class queries.
- **Trap:** dense trades exactness for plausibility (confident-but-wrong
  chunks) — pair with fix-B's cite-constrain, never instead of it.

### 6. Free pipeline wins (anytime, zero quota)
- **Answer cache** keyed by (question, prompt version, transcript hash) — kills
  repeat Gemini spend; effective quota grows.
- **Rule-based contextual TOC prefixes** ("this fragment lists Chapter IV
  headings") — the LLM-generated variant costs 2,214 calls ≈ 110 days at
  20/day. Rules are free and deterministic.
- **Minimum answer shape** in prompt (2+ claims, 2+ distinct cites) ONLY if the
  judge confirms Q3/Q8 thinness is real, not proxy artifact.

## Exit criteria
- [ ] Q5-class queries retrieve (synonym map or hybrid proves it on 10Q).
- [ ] Zero TOC-trap misattributions mechanically (fix-B, no hand flags needed).
- [ ] Rerank + hybrid each ablated with numbers in the journal.
- [ ] RAGAS-judge verdict recorded; Phase 06 closed.
- [ ] Answer cache live; quota spend per regression run documented.

## Record results in
`LEARNING_JOURNAL.md` → per-step ablation tables (sparse vs dense vs hybrid,
pre/post rerank), quota ledger per run, framework trade-offs (custom vs RAGAS).

## Traps
- Never tune the frozen 10Q set to the metrics (no editing questions to pass).
  New questions may be added; existing ones are frozen once baselined.
- Every new dependency must install cleanly into `drlca-rag` ONLY and must not
  bloat the Render runtime (`requirements.txt` stays slim; heavy deps live in
  `requirements-rag.txt` or prebuilt artifacts).
- Free-tier quota is a budget, not a blocker: batch LLM work, cache everything,
  prefer Colab/Kaggle for one-shot heavy compute.
