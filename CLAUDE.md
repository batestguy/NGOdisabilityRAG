# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

DRLCA — Nigerian disability-rights legal Q&A (Disability Act 2018 + 1999 Constitution)
plus a verified NGO/helpline connector. Free tier only ($0.00).

Spec (source of truth): `RAGNGO.txt` · Session entry: `HANDOFF.md` · Current snapshot:
`STATUS.md` · Phase playbooks: `docs/phases/` · Research log: `LEARNING_JOURNAL.md` ·
Repo conventions: `AGENTS.md` · Machine/env routing: `ENVIRONMENTS.md`.

## Environment

Everything runs in **`C:\conda-envs\drlca-rag`** (Python 3.11) and nowhere else. Never
pip-install into `ds-general`, `base`, or system Python — a past install broke
catboost/numba there. Scripts are invoked by absolute interpreter path from the repo
root (`D:\NGORAG`), not via `conda activate`:

```powershell
C:\conda-envs\drlca-rag\python.exe scripts\bench_phase01.py        # Phase 01 retrieval bench (PASS)
C:\conda-envs\drlca-rag\python.exe scripts\test_phase03.py         # NGO connector, 16/16 matrix + 7/7 statics
C:\conda-envs\drlca-rag\python.exe scripts\test_phase04.py         # Intent router, 10/10
C:\conda-envs\drlca-rag\python.exe scripts\test_phase05.py         # UI script-level asserts, 104/104
C:\conda-envs\drlca-rag\python.exe scripts\eval_phase06.py --out=scripts\eval_tmp.json
C:\conda-envs\drlca-rag\python.exe -c "import app"                 # boot-import smoke (must not start a server)
C:\conda-envs\drlca-rag\python.exe -m streamlit run app.py         # local UI → http://localhost:8501
```

These are plain assert-and-print scripts, not pytest — there is no test runner and no
"single test" selector. To narrow a run, read the script and comment out or copy the
relevant `check(...)` block; each script exits nonzero on any failure.

`scripts/test_phase02.py` is the only suite that spends Gemini quota. Dry runs need
`--no-llm` **and** `--out=<temp path>` (the `--out=` equals form only — the space form
is silently ignored), so a dry run can never overwrite a versioned LLM transcript.

Rebuild the env from `requirements-rag.txt` (full dev stack: OCR/ONNX/FAISS/PyMuPDF).
`requirements.txt` is the deliberately slim **runtime** for Render — OCR/ONNX/FAISS must
never be added to it; the corpus ships prebuilt as TXT and is never re-OCRed at boot.

## Architecture

```
app.py (Streamlit UI)  ──► resolve_mode()  ──► greeting | legal | help | clarify
  │ helplines banner (top + above every answer), a11y CSS, voice, read-aloud
  │ theme colors live ONLY in .streamlit/config.toml
  ▼
src/router.py   keyword scorer (legal vs help cues), is_greeting(), clarify policy,
                extract_help_slots(), route() = wired offline dispatch
  ├─ legal ─► src/rag.py  ask() → build_corpus() → PerDocRetriever → MIN_SCORE gate
  │             → optional Gemini (cite-strict-v2 prompt) → refusal layer → cite check
  │             corpus built from src/load.py (OCR repair) + src/chunk.py (splitters)
  └─ help ──► src/ngo.py  load_ngo() → find_ngo_with_meta() → with_helplines()
```

`app.py` imports its own `src/` via `sys.path.insert`; `src/router.py` does the same so
`import rag` / `import ngo` work either way. Module names are flat (`rag`, `ngo`,
`retrieve`, not `src.rag`).

`app.py` is **import-safe by contract**: every Streamlit call lives inside `run()` or a
render helper, and the bottom guard only boots under `streamlit run`/`__main__`.
`scripts/test_phase05.py` imports `app` directly and also asserts on the *source text* of
`app.py` (e.g. that `render_helpline_banner()` appears before the legal/help/greeting
branches) — renaming those functions or reordering `run()` will break the suite by
design.

### Three-doc corpus, three numbering schemes

`doc_id ∈ {act2018, constitution1999, factsheet2020}`. Act clause N, Constitution
section N, and Factsheet Section N are different things and must never be conflated;
every `Chunk`/`Hit` carries `(doc_id, ref)` and `cite_tag()` is the only place tags are
built. Chunk sizes are pinned by Phase 01 measurement: Act section-aware 800,
Constitution chapter-aware 400, Factsheet recursive 500/50.

`PerDocRetriever` merges top-k from *each* doc rather than one joint index, because the
Constitution is ~95% of the joint index and floods Act-specific queries. Consequence:
context **precision 0.333 is by design** — never gate or "fix" it.

## Invariants (violating these is a spec break, not a style choice)

- **Helplines first, always.** DRAC Toll-Free `08000-3000-100`, DRAC WhatsApp
  `08000-3000-10` render above every answer and lead every NGO result. Any new NGO
  response shape must go through `ngo.with_helplines()`.
- **Every legal claim carries a citation tag**, copied verbatim from the chunk header —
  `[Act cl. N]`, `[Constitution s. N]`, `[Factsheet Section N]`. Never strip, renumber,
  or "clean up" OCR quirks in section numbers.
- **Two refusal layers, both preserved.** `MIN_SCORE = 0.10` is a weak-overlap *floor*,
  not a semantic filter (the in-corpus/off-corpus cosine bands are inverted — see the
  calibration comment in `src/retrieve.py`); the strict-prompt `NO_ANSWER_SENTENCE` path
  in `src/rag.py` is the semantic one. False refusals deny help to PWDs, so the gate errs
  low on purpose. Do not nudge `MIN_SCORE` upward to fix a precision number.
- **The default user path is fully offline.** Retrieval, excerpts, NGO lookup, and the
  router make zero network calls. Gemini generation sits behind an opt-in expander that
  defaults OFF. `ask(use_llm=False)` returns `answer=None` meaning *pending*, never a
  fabricated answer.
- **Never fake an LLM row.** Quota/network failure records `llm_error` and leaves the row
  pending. LLM runs write to versioned files (`test_phase02_results_<prompt>_<date>.json`).
- **Verified contacts only.** `ngo.load_ngo()` hard-fails on placeholder/blank phones.
  Pruned orgs listed in the `src/ngo.py` docstring must not be re-added without fresh
  verification against the official site.
- **`data/processed/_SAMPLE_DO_NOT_CITE.txt` is a dev placeholder** — never loaded, never
  cited.
- **Accessibility is a requirement, not polish**: linear screen-reader-safe layout,
  keyboard navigable, high contrast + font scaling, voice in/out.

## Quota and eval discipline

Gemini free tier is **20 calls/day/model** (`gemini-2.5-flash`, confirmed by 429). A full
Phase 02 run is 12 calls; the deferred RAGAS-judge run is ~30. Check `HANDOFF.md` for the
day's spend before starting anything LLM-backed. 503s are transients — retry with backoff.

`scripts/eval_phase06.py` is a custom zero-LLM proxy for the RAGAS metrics (RAGAS itself
is not installed — its langchain/openai tree would endanger the pinned env). Its expected
refs are ground truth read from the corpus, never copied from LLM answers. Known metric
artifacts (reverse_rel 0.630, coverage misses) stay **recorded as FAIL** pending the judge
— don't tune the yardstick to make them pass.

## CSS / Streamlit gotchas (learned the hard way)

- Brand colors live **only** in `.streamlit/config.toml`. `accessibility_css()` in
  `app.py` handles spacing/typography/watermark/overrides — and dark-mode surfaces, which
  needs the `body.drlca-dark` class set by the `theme_watch_html()` iframe (Streamlit
  exposes no server-side theme hook).
- The watermark div sits inside `stMainBlockContainer` at z-1, so the sidebar needs
  z-index 2. Streamlit's own section rules beat un-`!important` ones.
- `components.html(..., height=0)` never mounts — use `height=1`. `srcdoc` scripts race
  `<body>`, so wrap them in a DOMContentLoaded-ready guard.
- Restart the Streamlit server after CSS edits; browser reload alone is not enough.

## Working conventions

- Work the active playbook in `docs/phases/` in order; each defines its own exit criteria.
  Next up: `docs/phases/08_retrieval_upgrades.md` (synonyms → cite-constrain → judge →
  rerank → hybrid, in that order, each ablated on the frozen 10Q set).
- **Doc hygiene is mandatory**: every build session ends by updating `STATUS.md`, the
  active playbook's results section, and a dated `LEARNING_JOURNAL.md` entry. Progress
  must survive the session.
- No LangChain — orchestration is custom `src/`. Justify any framework change in the
  learning journal.
- Deploy: Render free tier auto-deploys on push to `main`
  (https://ngodisabilityrag.onrender.com). `GOOGLE_API_KEY` is a Render env var — never
  committed. Free instances sleep after 15 min idle (~1 min wake); a slow first load is
  normal, not breakage.
