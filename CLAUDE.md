# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

DRLCA — Nigerian disability-rights legal Q&A (Disability Act 2018 + 1999 Constitution)
plus a verified NGO/helpline connector. Free tier only ($0.00). **Live** on Render.

Spec (source of truth): `RAGNGO.txt` · Session entry: `HANDOFF.md` · Current snapshot:
`STATUS.md` · Phase playbooks: `docs/phases/` · Research log: `LEARNING_JOURNAL.md` ·
Repo conventions: `AGENTS.md` · Machine/env routing: `ENVIRONMENTS.md` · Archived history
(the pre-2026-10-22 CLAUDE/STATUS/HANDOFF, verbatim): `docs/history/`.

<!-- H8c (2026-10-22): split by lifecycle. Durable rules here; detail in .claude/rules/ (path-scoped);
     history in docs/history/. Before adding a note, ask which tier it belongs to. -->

## Environment

Everything runs in **`C:\conda-envs\drlca-rag`** (Python 3.11) and nowhere else. Never
pip-install into `ds-general`, `base`, or system Python — a past install broke
catboost/numba there. Scripts are invoked by absolute interpreter path from the repo
root (`D:\NGORAG`), not via `conda activate`:

```powershell
C:\conda-envs\drlca-rag\python.exe scripts\bench_phase01.py        # Phase 01 retrieval bench (PASS)
C:\conda-envs\drlca-rag\python.exe scripts\test_phase03.py         # NGO connector
C:\conda-envs\drlca-rag\python.exe scripts\test_phase04.py         # Intent router
C:\conda-envs\drlca-rag\python.exe scripts\test_phase05.py         # UI script-level + source-text asserts
C:\conda-envs\drlca-rag\python.exe scripts\test_phase09_ops.py     # ops/chat/telemetry invariants, zero network
C:\conda-envs\drlca-rag\python.exe scripts\audit_corpus.py         # corpus shape gate + v1 regression tripwire
C:\conda-envs\drlca-rag\python.exe scripts\eval_heldout.py         # held-out retrieval baseline (+ recall_strict, + test2 on v2)
C:\conda-envs\drlca-rag\python.exe scripts\eval_chat.py            # multi-turn set
C:\conda-envs\drlca-rag\python.exe scripts\calibrate_refusal.py    # refusal invariance, 212 probes, 0 disagreements
C:\conda-envs\drlca-rag\python.exe scripts\eval_phase06.py --out=scripts\eval_tmp.json
C:\conda-envs\drlca-rag\python.exe scripts\summarise_signal.py <file>   # H7 counts from pasted Render log lines
C:\conda-envs\drlca-rag\python.exe -c "import app"                 # boot-import smoke (must not start a server)
C:\conda-envs\drlca-rag\python.exe -m streamlit run app.py         # local UI → http://localhost:8501
```

Assert counts live in `STATUS.md`; measurement harnesses in `.claude/rules/retrieval.md`. **Three scripts spend Gemini quota only behind
`--i-understand-this-spends-quota`** (`probe_embed_quota.py`, `transcript_chat.py`,
`probe_gen_refusal.py`); never pass it without a quota plan.

Baselines and the GloVe file live in `runs\` (gitignored); read any older `D:\<run>\` as `D:\NGORAG\runs\<run>\`.

These are plain assert-and-print scripts, not pytest — there is no test runner and no
"single test" selector. To narrow a run, read the script and comment out or copy the
relevant `check(...)` block; each script exits nonzero on any failure. CI
(`.github/workflows/offline-suites.yml`) runs the zero-network suites on every PR and push.

`scripts/test_phase02.py` spends Gemini quota. Dry runs need `--no-llm` **and**
`--out=<temp path>` (the `--out=` equals form only — the space form is silently ignored), so a
dry run can never overwrite a versioned LLM transcript.

Rebuild the env from `requirements-rag.txt` (full dev stack: OCR/ONNX/FAISS/PyMuPDF).
`requirements.txt` is the deliberately slim **runtime** for Render — OCR/ONNX/FAISS, and any
translation or embedding model, must never be added to it; the corpus ships prebuilt as TXT and is
never re-OCRed at boot.

## Architecture

**DRLCA is a multi-turn chatbot** — `st.chat_input`, history in `st.session_state` only (never
written to disk), per-turn read-aloud.

```
app.py (Streamlit chat UI)
  │ run()            sidebar → title → banner → render_history() → voice draft → st.chat_input
  │ render_turn()    computes AND renders ONE NEW turn -> TurnPayload (fused on purpose, see below)
  │ replay_turn()    renders a STORED TurnPayload — no retrieval, no router, no network (asserted)
  │ render_* shared by both paths: src/ui_render.py (H8b, re-exported by app); banner leads page + every turn
  ▼
src/chat.py      contextualise() (ellipsis / unbound pronouns), merge_help_slots(), TurnPayload, cross_turn_drift()
src/router.py    keyword scorer, is_greeting(), clarify policy, extract_help_slots(), route(). STATELESS —
                 accumulated slots arrive as an argument, never stored
  ├─ legal ─► src/rag.py  ask(history=) → build_corpus() → PerDocRetriever → MIN_SCORE gate
  │             → optional Gemini (cite-strict-v3 / chat-cite-strict-v2) → refusal layer → cite check
  └─ help ──► src/ngo.py  load_ngo() → find_ngo_with_meta() → with_helplines()
src/telemetry.py counts-only DRLCA_SIGNAL stdout lines (H7; see docs/telemetry.md)
```

`app.py` imports its own `src/` via `sys.path.insert`; module names are flat (`rag`, `ngo`,
`retrieve`, not `src.rag`).

**`app.py` is import-safe by contract**: every Streamlit call lives inside `run()` or a render
helper, and the bottom guard only boots under `streamlit run`/`__main__`. `scripts/test_phase05.py`
imports `app` and also asserts on the **source text** of `app.py` — that `render_helpline_banner()`
appears before the legal/help/greeting branches inside `render_turn`'s body, and that every banner
call site sits at 4-space top level, never inside a `with col:`. **Renaming those functions or
reordering `run()` / `render_turn()` breaks the suite by design.**

## Editing retrieval, the corpus or the eval harnesses

Retrieval numbers move **silently**: a reordered dict, a widened `k`, an edited synonym or a
rebuilt artifact all produce plausible output and different published figures. **Read
`.claude/rules/retrieval.md` before touching `src/retrieve.py`, `src/rag.py`, `src/chunk.py`,
`src/load.py`, `data/processed/` or any eval script.** It loads automatically when you read one of
those files, but not after a `/compact`, and not if you create a new file there without reading an
existing one. The core rules, which must not be lost:

- **Three docs, three numbering schemes.** `doc_id ∈ {act2018, constitution1999, factsheet2020}`.
  Act clause N, Constitution section N and Factsheet Section N are different things and must never
  be conflated. `cite_tag()` is the only place tags are built.
- **Shipping budget `k=4/doc, top_n=12`, and `top_n == 3 × k` is load-bearing.** Widening `k`
  without holding it measured worse on all three sets. `top_n` is a ceiling, not a count.
- **`build_corpus()` dict insertion order breaks score ties.** Reordering it moves published numbers.
- **Context precision is low by design** (per-doc merging). Never gate or "fix" it.
- **Declined arms stay declined.** BM25/RRF re-rank (E2a), the auto synonym map (E3a), the static
  embedding arm (F0), the off-topic guard (H4) and the Pidgin-routed arm (H5a) live on archive
  branches only. **Do not re-implement them here**, and do not re-run them without a new reason.
- **`SYNONYMS` must not be edited casually**: touching it moves `calibrate_refusal` off its 212 runs
  and requires a fresh calibration. **The OOV-bridge code is the measured function verbatim** — do not
  "tidy" it (its PORT CHECK asserts it).

## Invariants (violating these is a spec break, not a style choice)

- **Helplines first, always.** DRAC Toll-Free `08000-3000-100`, DRAC WhatsApp
  `08000-3000-10` render above every answer and lead every NGO result. Any new NGO
  response shape must go through `ngo.with_helplines()`.
- **Every legal claim carries a citation tag**, copied verbatim from the chunk header —
  `[Act cl. N]`, `[Constitution s. N]`, `[Factsheet Section N]`. Never strip, renumber,
  or "clean up" OCR quirks in section numbers (fixes go only through the human-signed
  `data/processed/act2018_v2_corrections.json`).
- **Two refusal layers, both preserved.** `MIN_SCORE = 0.10` is a weak-overlap *floor*,
  not a semantic filter (the in-corpus/off-corpus cosine bands are inverted — see the
  calibration comment in `src/retrieve.py`); the strict-prompt `NO_ANSWER_SENTENCE` path
  in `src/rag.py` is the semantic one. **False refusals deny help to PWDs**, so the gate errs
  low on purpose. Do not nudge `MIN_SCORE` upward to fix a precision number. (The calibration
  comment in `src/retrieve.py` adds: it may move down on evidence and never up —
  `calibrate_refusal.py` gate 3 enforces that.)
- **The default user path is fully offline.** Retrieval, excerpts, NGO lookup, and the
  router make zero network calls. Gemini generation sits behind an opt-in expander that
  defaults OFF. `ask(use_llm=False)` returns `answer=None` meaning *pending*, never a
  fabricated answer.
- **Never fake an LLM row.** Quota/network failure records `llm_error` and leaves the row
  pending. LLM runs write to versioned files (`test_phase02_results_<prompt>_<date>.json`).
- **Verified contacts only.** `ngo.load_ngo()` hard-fails on placeholder/blank phones.
  Pruned orgs listed in the `src/ngo.py` docstring must not be re-added without fresh
  verification against the official site. Research fetch tools paraphrase pages, so re-verify every
  phone in a real browser (`tools/a11y_audit/verify_ngo_sources.mjs`).
- **`data/processed/oov_bridge.json` is corpus-keyed.** `rag.build_corpus("v2")` hard-fails on a
  missing or stale artifact (sha256 of the chunk stream). Any corpus change means rebuild
  (`scripts/build_oov_bridge.py`, needs the GloVe file in `D:\NGORAG\runs\e4_vectors\`, never
  committed) **and re-measure** — rebuilding does not re-validate it. `check_bridge=False` is for
  the generator only.
- **`data/processed/_SAMPLE_DO_NOT_CITE.txt` is a dev placeholder** — never loaded, never cited.
- **Telemetry is counts only** (`src/telemetry.py`, `docs/telemetry.md`): no question text unless
  the user ticks the sidebar opt-in (default OFF), no session id, no history, no IP. Any new field
  goes through the owner first.
- **Accessibility is a requirement, not polish**: linear screen-reader-safe layout,
  keyboard navigable, high contrast + font scaling, voice in/out.

## Quota and eval discipline

Gemini free tier is **20 calls/day/model AND 10/minute/model** (confirmed by 429).
`gemini-2.5-flash` and `gemini-2.5-flash-lite` draw from **separate pools**, so the real
budget is **40/day**; `ask(failover=True)` exploits it (opt-in, fires once, and **never** on a
per-minute 429 — those are retried with backoff, not dodged). 503s are transients — retry with
backoff. **Plan any multi-call run across days and pools before spending the first call** — a
half-finished run is wasted quota — and check `HANDOFF.md` for the day's spend first. Anchors: a
full Phase 02 run is 12 calls; a judge run ~30; Phase G took ~42 over two days. **Never
`--failover` on a generation or judge run** (a failed-over row breaks generator/judge model
separation — `docs/phases/14_generation_eval.md`).

The answer cache (`scripts/.answer_cache.json`, gitignored) is a quota saver, never evidence: keyed
on sha256(model + whole rendered prompt), fails open, every hit marked `cached=True`. A
flakiness/repeat check must pass `--no-cache` (`test_phase02.py`), or it measures replays.

**Held-out discipline.** `frozen-10` stays frozen and separate. Selection uses dev; blind sets
(`test2`, and any new one) are authored and committed **before** any arm touches them, read once,
and never tuned against. Whether `test` is still clean is an open owner decision (2026-10-21) — do
not read it. Every ship gate is written down before its number is seen.

`scripts/eval_phase06.py` is a custom zero-LLM proxy for the RAGAS metrics (RAGAS itself is not
installed — its langchain/openai tree would endanger the pinned env). Its expected refs are ground
truth read from the corpus, never copied from LLM answers. Known metric artifacts (reverse_rel,
coverage misses) stay **recorded as FAIL**; the judge arbitrated reverse_rel as an artifact. Don't
tune the yardstick to make them pass.

## UI, CSS and Streamlit

Streamlit/CSS changes **half-apply silently** and a11y regressions pass every string assert. **Read
`.claude/rules/ui.md` before editing `app.py`'s CSS/JS, `.streamlit/`, or `tools/a11y_audit/`.**
Two rules that must survive a `/compact`: brand colors live **only** in `.streamlit/config.toml`;
and a widget whose label or `key=` changes remounts and **drops keyboard focus** — test focus
behaviour in a browser, not just state.

## Working conventions

- **ACTIVE: `docs/phases/17_h8_corpus_expansion.md`, order H8c → H8b → H8a.** Other open items
  (H7 week-1 signal read on/after 2026-10-28, H5b, H6) are in `docs/phases/16_post_launch_roadmap.md`
  and `HANDOFF.md`. Work the active playbook in order; each step defines its own exit gate.
  All earlier phases (01–15, D, E, G, F) are closed; their records are in the playbooks and
  `docs/history/claude_md_2026-10-22.md`.
- **Doc hygiene is mandatory**: every build session ends by updating `STATUS.md` (current state
  only — replace lines, don't append history), `HANDOFF.md` (latest block on top; move superseded
  blocks to `docs/history/handoff_history.md`), the active playbook's Results section, and a dated
  `LEARNING_JOURNAL.md` entry. Progress must survive the session.
- **Branch per change, PR to `main`.** Declined code goes on an archive branch and is never merged
  (`phase10/retrieval-quality` `a6016e4`, `phase10/f0-static` `27ed13d`, `phase11/h4-offtopic`
  `e884f85`, `phase11/h5a-pidgin` `5b28c07`). Pushing a topic branch does not deploy.
- **Delegated work gets a reviewer pass** before it is reported; source-text asserts prove presence,
  never behaviour.
- No LangChain — orchestration is custom `src/`. Justify any framework change in the learning journal.
- **Deploy: Render free tier auto-deploys on every push to `main`**
  (https://ngodisabilityrag.onrender.com, service `srv-dah26opt0dsc73e9a350`). **Every merge or
  push to `main` deploys to real users and is the owner's call, every time — no authorisation
  carries forward**, including for docs-only merges. If auto mode blocks `gh pr merge` after the
  owner's yes, give them the exact `!` command. `GOOGLE_API_KEY` is a Render env var — never
  committed. Free instances sleep after 15 min idle (~1 min wake); a slow first load is normal.
  Smoke runs that ask a question write production telemetry: count attempts and record the ids
  to discount.
