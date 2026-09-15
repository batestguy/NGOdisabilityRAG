# Phase 11 — Conversational legal assistant (chat) — started 2026-09-15

## Goal

Make DRLCA a **chatbot as well as a legal assistant**, still `$0.00`, on the free tier.
One code path — chat replaces the single-turn form — so there is never a second refusal
path or a second citation path to keep measured.

This playbook owns the chat work. `docs/phases/10_corpus_rebuild_and_dense.md` keeps the
corpus-v2 and dense-retrieval work; the two interleave, and the ordering argument below is
the reason this one goes first.

## Why chat changes the engineering, not just the UI

A follow-up like *"so can they fire me?"* is **unanswerable by retrieval in isolation** — it
contains no disability term and no statutory term. No re-ranker, no encoder and no corpus
rebuild can retrieve an answer to a query that does not contain the question.

`src/router.py` is fully stateless (verified 2026-09-15: every routing decision depends only
on the current string), which is correct and stays that way — it is what makes each turn
independently testable and what lets `test_phase04.py` assert on 10 fixed inputs. But it
means **nothing in the stack resolves ellipsis today.** That is a *retrieval* problem.

The consequence for sequencing is the whole point: if the corpus and dense phases tune
retrieval against single-turn questions only, they optimise a query distribution the chatbot
never issues, and chat inherits none of the gains. So **the multi-turn eval set is built and
measured before the chat UI, and before the corpus and dense work.** Measure first — this
project's own style.

## Free-tier reality (corrected)

`CLAUDE.md` says 20 calls/day. **It is stale**, and fixing it is a Phase G deliverable.
`HANDOFF.md:20-22,148-161` and `STATUS.md` record the measured truth: **20/day/model AND
10/minute/model**, with `gemini-2.5-flash` and `gemini-2.5-flash-lite` drawing from
**separate pools** — so the real budget is **40/day**, and `ask(failover=True)` already
exploits it.

At 40/day a chat session of 5 AI-generated turns costs 5 calls → ~8 conversations/day
site-wide. That is acceptable for a prototype **only because the default path is offline**:
every turn returns cited excerpts with zero network calls, unlimited. AI prose stays opt-in,
default OFF.

## Design decisions (owner, 2026-09-15)

1. **Chat replaces the single-turn form.** One code path.
2. **Helplines: full banner at page top, compact one-line helpline leading every assistant
   turn.** NGO results keep the full banner rows via `ngo.with_helplines()`, untouched.
3. Dense arm: static embeddings by default, Gemini embeddings opt-in. The default path stays
   offline, so `CLAUDE.md`'s offline invariant needs **no amendment**.
4. Corpus v2 lands before the dense arm.
5. One targeted attempt at the missing clauses (NCPWD's own copy), then a gap manifest.

## Scope

**Rebuild:** the UI shell (form → chat). **Add:** conversation contextualisation.

**Keep, and do not "improve" while passing through:**

- `scripts/eval_heldout.py`, `scripts/evalset.py`, `data/eval/questions.json`, the
  frozen/dev/test discipline. The most valuable asset in the repo.
- Citation grammar: `cite_tag()`, `CITE_TAG_RE`, `verify_citations()`.
- Both refusal layers: `MIN_SCORE = 0.10` and the calibration block at
  `src/retrieve.py:26-44`; the `NO_ANSWER_SENTENCE` semantic path in `src/rag.py`.
- `src/ngo.py`, `src/router.py` (**stateless — do not make it stateful**),
  `accessibility_css()`, `theme_watch_html()`, Render deploy.

---

## Steps

### B — Multi-turn eval set + contextualisation, headless ✅ DONE 2026-09-15

Branch `phase10/chat-core`. Zero quota, zero Streamlit, zero network.

- `data/eval/conversations.json` + `scripts/chatset.py` (new loader, mirroring
  `evalset.py`'s validate-on-every-load discipline; a separate file so `questions.json`'s
  loader stays byte-stable).
- `src/chat.py`: `contextualise()`, `merge_help_slots()`, `TurnPayload`,
  `history_for_prompt()`, `cross_turn_drift()`.
- `history=` on `ask()` and `build_prompt()`, byte-identical when absent.
- `scripts/eval_chat.py`: naive vs contextualised, by turn class.

**Exit criteria and what they measured — see Results below.**

### C — The chat UI

Branch `phase10/chat-ui`. Zero quota. Consumes `src/chat.py`; adds no new packages.

- The answer-flow body of `run()` moves into `render_turn(...)`, **keeping the lines
  `test_phase05.py:32-39` asserts on as source text verbatim** (`render_helpline_banner()`,
  the `# Single routing seam` comment, `resolve_mode`, the greeting/legal/help branches).
- **Replay, don't recompute.** Streamlit re-executes the script on every interaction; a loop
  that re-queried every turn would cost N retrievals per rerun, and N× that once the dense
  arm lands. Completed turns render from their stored `TurnPayload`.
- Linear order: banner → *"Conversation so far (N turns)"* → turns oldest first →
  `st.chat_input` at the bottom. Compact helpline opens every assistant turn.
  **Read-aloud becomes per assistant turn** — one global button would read the whole history.
- Mode buttons move to the sidebar as overrides; all six required labels stay.
- **Clarify becomes a turn** rather than a button pair. `resolve_mode`, `render_clarify` and
  the `clarify-legal`/`clarify-help` keys are kept.
- **Privacy:** history lives in `st.session_state` only, never on disk; a **Clear
  conversation** control, always visible.
- **Quota made visible:** `scripts/.quota_log.json` (counts only) + a sidebar readout.
  An *"AI-answer every new turn"* toggle, **default OFF**.
- Width, folded in honestly: pool **k=20/doc**, **12** chunks to the prompt (≤4 per doc),
  **3 excerpts inline + rest in one `st.expander`**. Claimed as *plumbing for the dense arm*:
  **test +0.000, dev +0.100, frozen-10 strict +0.048.** Not a recall win.

### D — Corpus v2 · E — Dense arm · F — Fine-tune · G — Re-baseline

Owned by `docs/phases/10_corpus_rebuild_and_dense.md`, with these chat-driven additions:

- **E** adds the multi-turn off-corpus-after-legal probes to
  `ablate_phase10.py --refusal-battery`.
- **F** generates **follow-up turns** as ~20% of synthetic pairs, so the encoder learns the
  contextualised query distribution the product actually issues; decontamination drops
  collisions against **chat turns** as well as eval questions.
- **G** re-verifies **all chat turns** against corpus v2, publishes cross-turn citation
  drift, and adds a small multi-turn transcript (3 conversations × 3 turns ≈ 9 calls) — the
  only way to measure drift on real generations.

---

## Verification

```powershell
C:\conda-envs\drlca-rag\python.exe scripts\eval_chat.py          # multi-turn, by class
C:\conda-envs\drlca-rag\python.exe scripts\eval_chat.py --reveal-test   # spends chat_test
C:\conda-envs\drlca-rag\python.exe scripts\test_phase09_ops.py   # incl. chat prompt invariants
C:\conda-envs\drlca-rag\python.exe scripts\eval_heldout.py       # single-turn, must not move
C:\conda-envs\drlca-rag\python.exe scripts\eval_phase06.py --out=scripts\eval_tmp.json
```

`--out=` **equals form only** — the space form is silently ignored and would overwrite a
versioned transcript.

## Traps

- **Do not make `src/router.py` stateful.** Conversation state lives in `src/chat.py` and the UI.
- **`history=None` must render a byte-identical prompt.** Asserted in `test_phase09_ops.py`
  section 7. Without it every transcript and every cache entry silently loses meaning.
- **History must stay before the final `"Question: "` line**, or `src/rag.py`'s `_cache_write`
  starts writing whole conversations — including disclosures of abuse — to disk.
- **Contextualisation can manufacture false answers.** Carrying prior turns lets a topic shift
  inherit legal vocabulary and clear `MIN_SCORE`. Measure it; never assume it.
- **`chat_test` is read once, never tuned against.** A disappointing number is the finding.
- **Never select a contextualisation threshold on `chat_test`.** `chat_dev` only.
- Every harness uses `select_top`, never its own `[:TOP_N]`.

---

## Results

### Step B — DONE 2026-09-15, zero Gemini calls, zero network

Artifacts: `data/eval/conversations.json`, `scripts/chatset.py`, `src/chat.py`,
`scripts/eval_chat.py`, `scripts/baseline_chat_2026-09-15.txt` (full run, committed).

**The sets.** `chat_dev` 12 conversations / 35 turns; `chat_test` 10 conversations / 27
turns (the plan said ~30 — 27 is what the blind authoring produced and it was not topped up
afterwards, because adding turns once behaviour is visible is how a blind set stops being
blind). **`chat_test` was authored before `src/chat.py` existed.** All 51 expected refs
verify against the v1 corpus.

**The headline (shipping arm, k=3/doc → `select_top(6)`, corpus v1):**

| set | naive | contextualised | delta | n |
|---|---|---|---|---|
| chat_dev | 0.464 | 0.571 | **+0.107** | 28 |
| chat_test (blind) | 0.435 | 0.565 | **+0.130** | 23 |

**By turn class — this is the number that says whether it works:**

| class | dev naive | dev ctx | dev Δ | test naive | test ctx | test Δ |
|---|---|---|---|---|---|---|
| direct (control) | 0.583 | 0.583 | +0.000 | 0.700 | 0.700 | +0.000 |
| ellipsis | 0.000 | 0.333 | **+0.333** | 0.200 | 0.600 | **+0.400** |
| pronoun | 0.571 | 0.714 | **+0.143** | 0.400 | 0.400 | **+0.000** |
| topic-shift | 0.667 | 0.667 | +0.000 | 0.000 | 0.333 | +0.333 |

**recall@k, one wide pool (k=20/doc → 60 candidates):**

| set / arm | r@3 | r@6 | r@10 | r@20 | r@60 | MRR | med-rank | found |
|---|---|---|---|---|---|---|---|---|
| dev naive | 0.179 | 0.429 | 0.500 | 0.571 | 0.714 | 0.191 | 6 | 20/28 |
| dev ctx | 0.250 | 0.607 | 0.643 | 0.750 | **0.929** | 0.271 | 5 | 26/28 |
| test naive | 0.261 | 0.435 | 0.478 | 0.565 | 0.783 | 0.290 | 6 | 18/23 |
| test ctx | 0.391 | 0.565 | 0.652 | 0.696 | **0.913** | 0.354 | 5 | 21/23 |

**Help slots** (`"I'm deaf"` … `"anywhere in Kano?"`): dev **3/5 → 5/5**, test **1/2 → 2/2**.
The stateless scan drops the disability filter on every narrowing turn;
`merge_help_slots()` recovers all of them.

**False refusals fell — they did not rise.** dev **1/28 → 0/28**, test **3/23 → 1/23**.
**Contextualisation-induced false refusals: 0 on both sets** — the one retrieval number
`eval_chat.py` is allowed to fail on.

**Gates:** ellipsis PASS · pronoun PASS (on dev, which is the tuning set) · topic-shift not
worse PASS · false refusals 0 induced PASS · `history=None` byte-identical PASS (13 asserts,
`test_phase09_ops.py` §7) · all existing suites green, `eval_phase06.py` output still
`CE716FB3…5F19`.

#### Four findings, including the ones that did not go our way

1. **The inherited-context false-answer trap did not fire — and the measurement is what says
   so.** Off-corpus-after-legal turns clear `MIN_SCORE` **2/2 in both arms, on both sets**:
   identical, delta **0.000**. That matches the published single-turn rate of 5/5 and is a
   property of the floor (bands inverted, `src/retrieve.py:26-44`), **not** something chat
   introduced. On `CD5.t3` contextualisation actually *lowered* the top score, 0.2755 →
   0.2434. `MIN_SCORE` was not touched.
2. **`chat_test`'s pronoun class did not improve (0.400 → 0.400)** while dev's did (+0.143).
   Recorded as measured. It is **not** being tuned away — `chat_test` is read once, and a
   threshold moved to fix it would convert the only clean multi-turn yardstick into a dev
   set, which is exactly how the 30 single-turn held-out questions were spent.
3. **A blind prediction in the test set was wrong, and the note stays wrong.** `CT6.t3`'s
   authored note predicted the carry-rule would not fire on *"how do I renew my driver's
   licence?"*; it fires via `thin:3<=3`. The note was written before `chat.py` existed, so it
   records what was predicted, not what happens — editing it after the fact is the failure
   mode this discipline exists to prevent. The behaviour is recorded here instead.
4. **The self-sufficiency bound is doing real work.** *"and what does the law say about
   maritime shipping insurance?"* opens with a discourse marker and still does **not** carry,
   because five content stems is a question that stands on its own feet. That bound is what
   protects the topic-shift and off-corpus classes; `MARKER_MAX` is not a free parameter.
5. **One `chat_test` turn is UNSCOREABLE, not missed — and it is a second named instance of
   the Phase D case.** Found in review. `CT7.t2` ("are guide canes on that list?") expects
   `act2018:[5]`, but the chunk actually carrying the First Schedule list is reffed
   **`general`**, and `ref_nums("general")` is empty. Both arms **do** retrieve that exact
   chunk, at ranks 5-6, and still score 0.000. `chatset.verify_expected()` passes it because
   an unrelated `cl. 3,4,5` header chunk carries a 5 — so the check proves the number exists
   somewhere, not that the right text is reachable under it. This is the same uncitable-chunk
   class as the recorded **"Act cl.19 is uncitable"** gap, and it joins the 25-of-62
   uncitable Act chunks as evidence for **Phase D**, whose audit gate (`ref=="general"` ≤1%
   per doc) is what removes it. **The expectation was NOT edited** — editing a blind test
   turn to recover a point is the move this discipline exists to stop. A dated addendum was
   added to its `note`, and `chatset.verify_expected()` now documents both limits it does not
   prove (this one, and the Constitution's cross-chapter section-number collisions).

**Thresholds** (`CARRY_WINDOW=2`, `THIN_MAX=3`, `MARKER_MAX=4`, `QUESTION_WEIGHT=2`) were
selected on `chat_dev` and nothing else.

**Not measured, deliberately:** cross-turn citation drift. Detecting a tag re-cited from an
earlier turn needs a generated answer to read, so it costs quota. `chat.cross_turn_drift()`
is written and wired but **unmeasured**; Phase G's multi-turn transcript is what runs it.
Omitted rather than approximated, exactly as `eval_heldout.py` omits faithfulness.
