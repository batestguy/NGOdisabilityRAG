---
name: project-table-docs
description: Document any DS/ML/RAG project as S/N, stage name, formal meaning/equations, layman translation table plus a separate app-numbers appendix with worked examples. Use when user says document project, explain pipeline stages, or needs stakeholder-friendly interpretation of scores and metrics.
---

# Project Table Docs

Turn any project into a table anyone can follow, from layman to technical, plus plain-English interpretation of every number the app shows.

## When to use me

Use when the user asks to document a project, explain pipeline stages, onboard a non-technical stakeholder, or interpret app/dashboard numbers. If the request is only "fix code" or "train model", do not load me.

## Discovery order (never invent stages)

1. `README.md`, `AGENTS.md`, `HANDOFF.md`, `STATUS.md` for intended stages.
2. `src/`, `app/`, `pages/`, `scripts/`, notebook headers for actual stages.
3. `tests/`, config files, `.streamlit/`, `requirements*.txt` for params and thresholds.
4. App UI files for displayed numbers (scores, forecasts, paybacks, CIs, p-values).

If a stage or number has no source, mark it `Unknown` — never guess equations or legal wording.

## Output shape (recommended: table + separate appendix)

### Part 1: Stages table (4 columns only)

| S/N | Stage name | Formal meaning / equations | Layman translation |
|-----|-----------|---------------------------|--------------------|

Rules per row:

- `Stage name` includes file/function in brackets, e.g. `TF-IDF retrieval (src/retrieve.py:11)`.
- `Formal` holds equation + params + thresholds inline, e.g. `cos(q,d) in [0,1], 1-2gram, top-k=3`.
- `Layman` is one ELI-10 sentence, no jargon.
- One row per real stage, ordered as data flows. Cite `path:line` in Stage name or Formal.
- Audience ladder: Layman cell for anyone, Formal cell for practitioners; add a parenthetical `(Do: ...)` in Formal when action matters, e.g. `(Do: if 0, corpus lacks topic)`.

### Part 2: Numbers you will see in the app (separate section, not a column)

One block per displayed number:

```text
- Number: <name, e.g. TF-IDF score 0.41>
- Where: <page/widget/file:line, e.g. answer panel <- src/retrieve.py:16>
- Range + direction: <e.g. 0-1, higher = closer>
- Good/bad cut: <e.g. >0.2 usable, 0 = missing topic>
- Example: <e.g. 0.41 strong match on "penalties"; 0.0 means add corpus coverage>
- What to do: <one action>
```

Cover metric families by project type:

- RAG: cosine similarity, chunk counts/sizes, RAGAS faithfulness (>0.85), answer relevancy (>0.80), context relevancy (>0.75).
- ML/price: forecast price, margin score, optimizer bounds, accuracy/RMSE.
- Finance/lead-gen: payback years, ROI, kW sizing.
- Stats/bio: p-value, 95% CI, bootstrap uncertainty, PyMC R-hat (~1.0) / ESS.

### Part 3: Validity note (3 lines max)

- Sources unreadable.
- Placeholders flagged (e.g. NGO `0803 000 0000` phones, `_SAMPLE_DO_NOT_CITE.txt`).
- Numbering traps (e.g. factsheet Section N vs Act clause N vs Constitution Section N — never conflate).

## Worked mini-example (DRLCA shape)

| S/N | Stage name | Formal meaning / equations | Layman translation |
|-----|-----------|---------------------------|--------------------|
| 1 | OCR ingest (scripts/ocr_local.py) | RapidOCR ONNX CPU, 27/27 pp, conf 0.95-0.97 | Scan paper law into text |
| 2 | Chunking (src/chunk.py:5) | recursive 500/50, section-aware 800, <=800 chars | Cut text into searchable cards |
| 3 | TF-IDF retrieval (src/retrieve.py:11) | cos(q,d), 1-2gram stop_words=english, top-k=3 (Do: if 0, topic missing) | Find 3 closest passages |
| 4 | NGO lookup (src/ngo.py:21) | substring + difflib cutoff 0.5, k=5 + helplines on top | Match disability/location to helpers |

Appendix block:

```text
- Number: TF-IDF score 0.41
- Where: answer panel <- src/retrieve.py:16
- Range + direction: 0-1, higher = closer
- Good/bad cut: >0.2 usable, 0 = missing
- Example: 0.41 strong on "penalties"; 0.0 on unseen topic
- What to do: if 0, check chunk coverage per docs/phases/01_corpus_and_chunking.md
```

## Guards

- One row per real stage; no invented pipeline steps.
- Every row cites at least one `path:line`.
- Wrongly repaired legal text or guessed numbers are blocking errors — when in doubt, leave artefact and note it.
- Keep it Colab/free-tier portable; no paid-service assumptions.
