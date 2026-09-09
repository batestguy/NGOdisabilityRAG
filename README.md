# DRLCA — Disability Rights Legal & Connection Assistant

Nigerian disability-rights legal Q&A (Disability Act 2018 + 1999 Constitution)
plus a verified NGO/helpline connector. Free tier only ($0.00). Accessibility is
mandatory: screen-reader-safe linear layout, voice input/output, keyboard
navigable, high contrast + font scaling.

National helplines (always displayed first): DRAC Toll-Free **08000-3000-100**,
DRAC WhatsApp **08000-3000-10**.

Live demo: *(pending — Hugging Face Spaces link lands here after Phase 07
smoke test; local run below works today)*

## Setup (local)

- Env: `C:\conda-envs\drlca-rag` (Python 3.11). Rebuild: `conda create -p
  C:\conda-envs\drlca-rag python=3.11 pip -y` + `pip install -r requirements-rag.txt`.
  Never install into shared envs (`ds-general`, `base`, system Python).
- Optional (AI answers only): `GOOGLE_API_KEY` in env. Everything else —
  retrieval, excerpts, NGO lookup, router — runs fully offline.
- Run: `python -m streamlit run app.py` → http://localhost:8501

## Usage

1. Type a question (English; explicit **Legal** / **Help** buttons or **Auto-route**).
2. Legal answers show retrieved excerpts with citation tags (`[Act cl. N]`,
   `[Constitution s. N]`, `[Factsheet Section N]`) — never stripped.
3. Help answers list verified organisations (helplines first, top-k, never top-1-only).
4. Optional extras: plain-language checkbox, read-aloud button, mic input
   (Chrome/Edge), high-contrast + text-size sidebar controls. The AI expander is
   OFF by default (uses your Gemini quota when opened).

## Deploy (Hugging Face Spaces, free tier)

- `requirements.txt` is the slim runtime (verified 2026-09-09 in a clean venv:
  install + offline legal/help smoke + boot HTTP 200). OCR/ONNX/FAISS are
  build-time only and must never be added — the corpus ships prebuilt.
- Push this repo to a Space (Streamlit SDK, Python ≥3.10), add `GOOGLE_API_KEY`
  under Space Settings → Secrets (never commit keys — `git log` audited),
  then smoke test: 3 legal + 2 help queries, helplines visible, citations present.
- Cold starts are slow on free tier (sleep/wake) — that is normal, not breakage.

## Status

Phases 01–05 done (all suites green), Phase 02 re-run done (8/10 cited, misses
logged by layer), Phase 06 custom eval done (recall 0.800, audited faithfulness
0.875; RAGAS-judge queued for quota reset), Phase 07 in progress. Details:
`STATUS.md`, per-phase playbooks in `docs/phases/`, research notes in
`LEARNING_JOURNAL.md`. Spec: `RAGNGO.txt`. Env notes: `ENVIRONMENTS.md`.

## Architecture

```
User ── Streamlit UI (app.py: banner, buttons, voice, a11y CSS)
         │  colors: .streamlit/config.toml (light+dark)   photo: static/watermark.jpg
         ▼
Intent router (src/router.py: LEGAL / HELP / clarify)
   ├─ legal ─► PerDocRetriever (src/retrieve.py: stemmed TF-IDF, k/doc merged,
   │             MIN_SCORE 0.10 gate) ─► excerpts + cite tags (src/rag.py)
   │             └─ opt-in Gemini (google-genai, cite-strict-v2 prompt, refusal layer)
   └─ help ──► NGO lookup (src/ngo.py: data/ngo.csv + fuzzy + helplines-first top-k)

Corpus (data/processed/): disability_act_2018_full.txt (Act, §-aware 800)
  + constitution_1999_NHRC.txt (chapter-aware 400) + disability_act_factsheet_PLAC.txt
Eval: scripts/bench_phase01.py · test_phase02.py · test_phase03/04/05.py · eval_phase06.py
```

## Data & verification

- Legal corpus: Disability Act 2018 (clauses 1–58 continuous, local RapidOCR),
  1999 Constitution (NHRC text), PLAC factsheet. `_SAMPLE_DO_NOT_CITE.txt` is a
  dev placeholder and is never loaded or cited.
- NGO directory (`data/ngo.csv`, 10 rows): all contacts verified against official
  sites 2026-09-08; NAB + NNAD re-verified 2026-09-09 (contact pages confirm
  phones/emails byte-exact). Re-verify every ~3 months; ship verified rows only.
