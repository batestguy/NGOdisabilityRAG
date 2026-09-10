# AGENTS.md — DRLCA (Disability Rights Legal & Connection Assistant)

Greenfield repo. Source of truth: `RAGNGO.txt` (project spec). Session entry: `HANDOFF.md`.
Phase playbooks: `docs/phases/`. Machine/env notes: `ENVIRONMENTS.md`.

## Non-negotiables (from spec — do not change)
- Core purpose: Nigerian disability-rights legal Q&A (Disability Act 2018 + 1999 Constitution) + NGO/helpline connector.
- Free tier only ($0.00): Colab/Kaggle dev, Render / Streamlit Cloud deploy (HF Spaces dropped 2026-09-10: Streamlit SDK → PRO-only), free-tier LLMs/embeddings/vector DB. No paid services.
- Every legal answer must include direct citations (e.g. "Section 17(2) of the Disability Act states..."). Citation accuracy target: 100%.
- NGO CSV schema (min 10 verified Nigerian orgs): `name, disability_focus, location, phone, email, website, description`.
- Always display national helplines on top: DRAC Toll-Free `08000-3000-100`, DRAC WhatsApp `08000-3000-10`.
- Accessibility is mandatory, not polish: screen-reader compatible, voice input/output, keyboard navigable, high contrast + font scaling, simple UI.

## Stack (pinned — don't improvise)
- Env: `C:\conda-envs\drlca-rag` ONLY (`requirements-rag.txt`). Never pip-install into
  `ds-general`, `base`, or system Python (a past install broke catboost/numba there).
- Orchestration: custom `src/` (no LangChain); retrieval: TF-IDF baseline, FAISS available;
  OCR: RapidOCR/ONNX local; LLM: Gemini free tier (`gemini-2.5-flash`, `google-genai` SDK);
  UI: Streamlit. Justify any framework change in the learning journal.

## Working conventions
- Work the active playbook in `docs/phases/` in order; each defines its exit criteria.
- Keep code rerunnable end-to-end and modular with comments.
- Required deliverables: `README.md` (setup, usage, demo link), learning journal (what worked/didn't, benchmarks), architecture diagram, live Spaces link.
- Eval targets: RAGAS faithfulness >0.85, answer relevancy >0.80, context relevancy >0.75.
- Doc hygiene (mandatory): every build session ends updating `STATUS.md` + the active playbook's
  results + dated `LEARNING_JOURNAL.md` entry. Progress must survive the session.
