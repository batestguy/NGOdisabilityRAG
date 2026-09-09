# Phase 07 — Deploy to Spaces + final docs

## Goal
Live, linkable, documented: the app runs on Hugging Face Spaces free tier and a stranger
can set up, run, and extend the project from the README alone.

## Entry criteria
- Phases 01–06 exit criteria met (or shortfalls explicitly documented — ship honestly).
- NGO contacts verified (Phase 03), citations at 100% on the test set (Phase 02/06).

## Steps
1. **Spaces app**: `app.py` at repo root (Streamlit), `requirements.txt` trimmed to runtime
   deps only (no RapidOCR/ONNX weight downloads at boot — keep the image lean; the corpus
   ships as prebuilt TXT/CSV, never re-OCRed at deploy time). Secrets via Spaces Secrets.
2. **Smoke test the deploy**: ask 3 legal + 2 help queries on the live link; helplines visible;
   citations present. Record the link.
3. **README.md**: setup (local + Spaces), usage, demo link, architecture summary.
   Audience: a stranger, not us.
4. **Architecture diagram**: retriever → router → LLM/lookup → UI boxes with file names
   (`src/*.py`, `data/*`). ASCII in-repo is fine; image optional.
5. **Demo video** (2–3 min per spec) + learning-journal final pass: what worked/didn't,
   benchmarks table, framework trade-offs — the research deliverable.
6. **Spec checklist audit**: walk `RAGNGO.txt` Quick Reference Checklist top to bottom,
   tick or explicitly defer each box in the journal.

## Exit criteria
- [ ] Live Spaces link in README, smoke-tested.
- [ ] README sufficient for a fresh clone → run (test by reading it as a stranger).
- [ ] Every spec checklist box ticked or deferred-with-reason. No silent gaps.

## Record results in
`README.md` (public face), `LEARNING_JOURNAL.md` (research face), this playbook's footer
(deploy date + link).

## Traps
- Spaces free tier sleeps: first load is slow — note it in the README so evaluators don't
  mistake cold start for breakage.
- Never ship the `_SAMPLE_DO_NOT_CITE.txt` or unverified NGO rows to the live app.
  The deploy corpus is a conscious selection, not "everything in data/".
- API keys: Spaces Secrets only. `git log` audit before first push — no key may ever
  have touched the repo history.
