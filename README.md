# DRLCA — Disability Rights Legal & Connection Assistant

Nigerian disability-rights legal Q&A (Disability Act 2018 + 1999 Constitution)
plus a verified NGO/helpline connector. Free tier only ($0.00). Accessibility is
mandatory: screen-reader-safe linear layout, voice input/output, keyboard
navigable, high contrast + font scaling.

National helplines (always displayed first): DRAC Toll-Free **08000-3000-100**,
DRAC WhatsApp **08000-3000-10**.

Live demo: **https://ngodisabilityrag.onrender.com** (Render free tier, live-verified
2026-09-10: helplines banner, help query end-to-end; first load slow after idle — normal)

## Setup (local)

- Env: `C:\conda-envs\drlca-rag` (Python 3.11). Rebuild: `conda create -p
  C:\conda-envs\drlca-rag python=3.11 pip -y` + `pip install -r requirements-rag.txt`.
  Never install into shared envs (`ds-general`, `base`, system Python).
- Optional (AI answers only): `GOOGLE_API_KEY` in env. Everything else —
  retrieval, excerpts, NGO lookup, router — runs fully offline.
- Run: `python -m streamlit run app.py` → http://localhost:8501

## Usage

**DRLCA is a multi-turn chatbot** (since 2026-09-16). Ask a question in the
`st.chat_input` box at the bottom; the conversation builds up the page and prior
turns stay on screen.

1. Ask in English. Routing is automatic (legal / help / greeting / clarify); each
   turn also offers an explicit **switch** control if it routed the wrong way.
2. **Follow-ups work without repeating yourself.** *"Can my employer refuse to hire
   me because I'm blind?"* → *"so can they fire me?"* resolves against the prior
   turn — ellipsis and unbound pronouns are handled in retrieval, not just in the UI
   (`src/chat.py`). Help slots carry too: *"I'm deaf"* … *"anywhere in Kano?"*.
3. Legal answers show retrieved excerpts with citation tags (`[Act cl. N]`,
   `[Constitution s. N]`, `[Factsheet Section N]`) — never stripped. 3 inline, the
   rest in one expander.
4. Help answers list verified organisations (helplines first, top-k, never top-1-only).
5. **Helplines render at the top of the page *and* leading every assistant turn.**
6. Optional extras: plain-language checkbox, **per-turn** read-aloud button, mic
   input (Chrome/Edge), high-contrast + text-size sidebar controls, **Clear
   conversation**. The AI expander is OFF by default (uses your Gemini quota when
   opened); with it off, everything above runs **fully offline**.

Conversation history lives in `st.session_state` only — it is never written to disk
and never leaves the process.

## Deploy (Render free tier — live; Streamlit Cloud optional 2nd link; HF Spaces dropped)

- `requirements.txt` is the slim runtime (verified 2026-09-09 in a clean venv:
  install + offline legal/help smoke + boot HTTP 200; re-verified live 2026-09-10).
  OCR/ONNX/FAISS are build-time only and must never be added — the corpus ships prebuilt.
- Live at https://ngodisabilityrag.onrender.com (Render `web_service`, Python 3.11.0,
  auto-deploys on push to `main`). `GOOGLE_API_KEY` via Render env vars
  (never commit keys — `git log` audited).
- HF Spaces path dropped: Streamlit SDK deprecated 2025-04 (now Docker template =
  PRO-only); Static can't run Python.
- Cold starts: Render free sleeps after 15 min idle (~1 min wake) — normal, not breakage.

## Status (2026-09-19)

**Live on Render since 2026-09-10** (Phase 07). Phases **01–09 done**; **Phase 10 B
(chat-core) and 10 C (chat UI) done 2026-09-15/16** — DRLCA is a multi-turn chatbot,
and contextualisation was measured *before* the UI shipped: strict recall **0.464 →
0.571** (chat_dev) and **0.435 → 0.565** (chat_test), ellipsis **0.000 → 0.333** /
**0.200 → 0.600**, false refusals *fell*. Offline suites green (`test_phase05.py`
at **137**).

**Phase D is COMPLETE and MERGED — corpus v2 is live** (`docs/phases/12_corpus_v2.md`). D0–D6 done
2026-09-19, merged to `main` and auto-deployed the same day (`8682869`). The Act corpus had a
citation-integrity defect: a page lost to a duplicate scan meant **clause 38 was absent from the
processed text**, and chunk boundaries let cl.38's tail be served under an `[Act cl. 39]` tag —
**that shipped to users from 2026-09-10 until 2026-09-19, and the merge is what ended it**.
Phase D re-OCRs the authoritative gazette and makes
clause-aligned chunking structural. Zero Gemini quota throughout. Held-out **test** strict recall
**0.338 → 0.471**, while the *fitted* frozen-10 set is the only one that got worse
(0.701 → 0.633) — the generalisation story, not a regression.

D6 also found the same defect **inside the eval set**: two `chat_test` turns expected `[Act cl. 8]`
for a provision that is actually clause **7(3)**, because they were authored from a v1 chunk that
carried clause 7's text under a cl.8 tag. Both are retired (never edited), and with them the
apparent "ellipsis regression" on the blind set turns out to be v1's number having been unearned
rather than v2 degrading. Baseline: `scripts/baseline_v2_2026-09-19.txt`, all five harnesses green.

**Now: Phase E — retrieval quality** (`docs/phases/13_retrieval_quality.md`). The legal Q&A
path is the app's weak half and the diagnosis is measured: the misses are **ranking, not
absence**. Clean test reads `r@6 = 0.426` shipping against `r@60 = 0.735` in the pool — a
**+0.309 gap**, against a hard ceiling of 0.824. Plan: widen the candidate pool, BM25 re-rank
*inside* the existing gate, replace the hand-tuned synonym map with a corpus-derived one, and
optionally blend a pure-numpy static-embedding signal. **$0, zero Gemini quota, no new runtime
dependency, default path stays fully offline.** Then **G** (judge + cross-turn drift, quota-paced)
and **F** (re-examine first — free GPU gives free *training*, not free *serving*).

Numbers to read with the caveats attached: frozen-10 recall **0.925** is measured on
the same 10 questions the synonym map was tuned on; **held-out recall is 0.420**
(n=25). Context precision **0.333 is by design** (per-doc merging trades it for
recall) and `reverse_rel 0.630` is a recorded **metric artifact**, arbitrated by a
judge run — neither is a bug to fix.

Details: `STATUS.md` (current snapshot), `HANDOFF.md` (session entry), per-phase
playbooks in `docs/phases/`, research notes in `LEARNING_JOURNAL.md`.
Spec: `RAGNGO.txt`. Env notes: `ENVIRONMENTS.md`.

## Architecture

```
User ── Streamlit chat UI (app.py)
         │  run(): sidebar → banner → render_history → st.chat_input
         │  render_turn(question, ..., history)  computes + renders a NEW turn → TurnPayload
         │  replay_turn(payload, ...)            re-renders a STORED turn
         │                                       (no retrieval, no router, no network)
         │  render_history()                     replays the thread on every rerun
         │  history lives in st.session_state only — never written to disk
         │  colors: .streamlit/config.toml (light+dark)   photo: static/watermark.jpg
         ▼
Contextualise (src/chat.py: resolve ellipsis / unbound pronouns against prior turns,
         │     carry help slots; CARRY_WINDOW=2)
         ▼
Intent router (src/router.py: LEGAL / HELP / greeting / clarify — stateless)
   ├─ legal ─► PerDocRetriever (src/retrieve.py: stemmed TF-IDF, k=3/doc merged,
   │             top_n=6, MIN_SCORE 0.10 gate) ─► excerpts + cite tags (src/rag.py)
   │             └─ opt-in Gemini (google-genai, cite-strict-v2 / chat-cite-strict-v1,
   │                refusal layer, answer cache). OFF by default.
   └─ help ──► NGO lookup (src/ngo.py: data/ngo.csv + fuzzy + helplines-first top-k)

Corpus (data/processed/): disability_act_2018_full.txt (Act, 800)
  + constitution_1999_NHRC.txt (chapter-aware 400) + disability_act_factsheet_PLAC.txt
Eval: scripts/bench_phase01.py · test_phase02.py · test_phase03/04/05.py ·
      eval_phase06.py · eval_heldout.py · eval_chat.py · audit_corpus.py ·
      test_phase09_ops.py · ablate_phase08.py · ablate_phase10.py
```

> **Caveat on the Act's chunk size.** It is described elsewhere as "section-aware
> 800", but `chunk.SECTION_RE` matches only **4 times** in the whole Act text — all
> of them in the Second Schedule and Forms — so for the entire operative body
> (clauses 1–58) the Act splitter is effectively plain `recursive_split(text, 800)`.
> This is not a bug to fix: it is part of the byte-identical v1 path every published
> baseline is measured against. It does mean Phase D's clause-aligned chunking is a
> **total replacement** of the Act splitter, not a refinement.

## Data & verification

- Legal corpus: Disability Act 2018 (local RapidOCR of a scanned PDF), 1999
  Constitution (NHRC text), PLAC factsheet. `_SAMPLE_DO_NOT_CITE.txt` is a dev
  placeholder and is never loaded or cited.
- **Corpus defect FIXED in Phase D, merged and deployed 2026-09-19** (`8682869`). Described in
  the past tense below because it is fixed, but it was **live in the deployed app for nine days**
  (2026-09-10 → 2026-09-19). The v1 source scan has one physical
  page recorded twice, so a page is missing: **clause 38's opening is absent** from
  `data/processed/disability_act_2018_full.txt` (the **v1** text, still reachable via
  `--corpus=v1`), its `(j)`–`(r)` tail lands in a chunk
  reffed `cl. 39`, and 25 of 62 Act chunks carry no citable ref at all.
  `scripts/audit_corpus.py` reports this rather than hiding it. Phase D re-OCRs the
  authoritative gazette (*Official Gazette No. 10, Vol. 106, 21 Jan 2019, Act No. 2,
  pages A97–A122*), which has no duplicate page; corpus **v2 locates 58/58 clauses with
  zero degradation flags**, and `--corpus=v1` still reproduces every published v1 number. **No clause is ever stubbed,
  paraphrased, or reconstructed from model knowledge** — a citation tag in front of a
  generation model is how a gap becomes a hallucinated provision.
- NGO directory (`data/ngo.csv`, 10 rows): all contacts verified against official
  sites 2026-09-08; NAB + NNAD re-verified 2026-09-09 (contact pages confirm
  phones/emails byte-exact). Re-verify every ~3 months; ship verified rows only.
