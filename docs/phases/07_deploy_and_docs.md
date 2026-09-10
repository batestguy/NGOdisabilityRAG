# Phase 07 — Deploy to Render + final docs (HF Spaces DROPPED 2026-09-10)

## Goal
Live, linkable, documented: the app runs on Render free tier and a stranger
can set up, run, and extend the project from the README alone.

## Entry criteria
- Phases 01–06 exit criteria met (or shortfalls explicitly documented — ship honestly).
- NGO contacts verified (Phase 03), citations at 100% on the test set (Phase 02/06).

## Steps
1. **Render app**: `app.py` at repo root (Streamlit), `requirements.txt` trimmed to runtime
   deps only (no RapidOCR/ONNX weight downloads at boot — keep the image lean; the corpus
   ships as prebuilt TXT/CSV, never re-OCRed at deploy time). Secrets via Render env vars
   (CLI `--env-var` or dashboard; never in repo). Start: `streamlit run app.py
   --server.port $PORT --server.address 0.0.0.0`, `PYTHON_VERSION=3.11.0`.
2. **Smoke test the deploy**: ask 3 legal + 2 help queries on the live link; helplines visible;
   citations present. Record the link.
3. **README.md**: setup (local + Render), usage, demo link, architecture summary.
   Audience: a stranger, not us.
4. **Architecture diagram**: retriever → router → LLM/lookup → UI boxes with file names
   (`src/*.py`, `data/*`). ASCII in-repo is fine; image optional.
5. **Demo GIF** (comprehensive captioned walkthrough per spec — owner amended 2026-09-10,
   video dropped) covering: legal query + cites, help query + helplines-first, accessibility
   controls. Save under `static/demo.gif`, embed in README + learning-journal final pass:
   what worked/didn't, benchmarks table, framework trade-offs — the research deliverable.
6. **Spec checklist audit**: walk `RAGNGO.txt` Quick Reference Checklist top to bottom,
   tick or explicitly defer each box in the journal.

## Exit criteria
- [x] Live Render link in README, smoke-tested (1 help query live + offline suites green;
  3-legal live smoke queued).
- [~] README sufficient for a fresh clone → run (Status section refreshed 2026-09-10 LIVE).
- [~] Spec checklist: all boxes current except LinkedIn + demo GIF (owner-side).

## Status (2026-09-09 — deploy prep DONE, push/smoke owner-side; LIVE 2026-09-10 Render)
- LIVE 2026-09-10: Render service `srv-dah26opt0dsc73e9a350` (free plan, python, Oregon) at https://ngodisabilityrag.onrender.com — created via Render CLI (`services create`, free), HTTP 200 + browser-verified (helplines banner both numbers, help query "blind Lagos" → NAB + fuzzy-confirm + contacts, routing note, read-aloud). HF Spaces path DROPPED (Streamlit SDK deprecated 2025-04 → Docker template = PRO only; Static can't run app.py) — spec's free alternative (Render/Streamlit Cloud) used instead.
- Exit criteria: [x] live link+smoke (Render; 1 help query live + full offline suites green; 3-legal live smoke queued — excerpts offline, AI expander needs quota day) · [x] README link in (Status refreshed 2026-09-10 LIVE) · [ ] demo GIF · [x] spec audit (deferrals written; LinkedIn owner-side) · [x] key audit.
- requirements.txt slimmed (faiss/onnx/ocr dropped, retired google-generativeai →
  google-genai) + clean-venv proven (install, imports 1.63.0/3.0.5/1.9.0, offline
  legal 6 excerpts + help 3 records, boot HTTP 200). Render `PYTHON_VERSION=3.11.0`, Oregon.
- README rewritten + ASCII architecture + data-verification section; spec audit in
  journal (deploys/docs boxes ticked except demo GIF, LinkedIn; Render link LIVE;
  video→GIF owner-amended).
  NAB/NNAD re-verified HIGH 2026-09-09 (contact pages byte-confirm CSV).
- Git: `main` pushed clean (key audit clean every commit).
- Owner-side left (need mic / voice / accounts): comprehensive demo GIF → NVDA/keyboard/mic
  gates → LinkedIn (+ optional Streamlit Cloud 2nd link). Done: push, Render create +
  env vars, live smoke (1 help), README link.

## Record results in
`README.md` (public face), `LEARNING_JOURNAL.md` (research face), this playbook's footer
(deploy date + link).

## Traps
- Render free sleeps after 15 min idle (~1 min wake): first load is slow — note it
  in the README so evaluators don't mistake cold start for breakage.
- Never ship the `_SAMPLE_DO_NOT_CITE.txt` or unverified NGO rows to the live app.
  The deploy corpus is a conscious selection, not "everything in data/".
- API keys: Render env vars only (dashboard or CLI `--env-var`). `git log` audit before
  every push — no key may ever have touched the repo history.
