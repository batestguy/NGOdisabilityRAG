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

### C — The chat UI ✅ DONE 2026-09-16

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
- ~~Width, folded in honestly: pool **k=20/doc**, **12** chunks to the prompt (≤4 per doc).~~
  **SUPERSEDED 2026-09-16 — width moved to Phase E.** The display split (**3 excerpts inline
  + the rest in one `st.expander`**) lands here, because that is presentation. Pool depth
  does not: `offline_legal_hits`' own docstring forbids a display path that slices
  differently from `ask()` ("*showing the user a system nobody measures*"), and
  `eval_chat.py:106-108` and `eval_heldout.py` both measure `k=3/doc, top_n=6`. Changing the
  UI without the harnesses would have detached the shipped system from every number in this
  file. Phase B measured the width change at **test +0.000**, so there is nothing to lose by
  waiting; it moves in Phase E, in the same commit as the harnesses, where the dense arm
  actually needs the deeper pool.

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

### Step C — DONE 2026-09-16, zero Gemini calls, zero network

Phase B's gain was real and unreachable. This step spends it and measures nothing new: **no
retrieval parameter, no scoring parameter, no corpus file and no prompt string changed**, so
`eval_chat.py` and `eval_heldout.py` were required to reproduce `368f083` **exactly** — and
they did, byte-identical stdout. `eval_phase06.py` output still hashes
`CE716FB3C1EA139B5E3A6885D732C5EBBD3F1B57981635F7D97DA5911EDF5F19`.
`git diff --stat main -- requirements.txt` is empty.

**What shipped.** `app.py` splits into `render_turn` (computes + renders one new turn),
`replay_turn` (renders a stored `TurnPayload`), `render_history`, and a `run()` driven by
`st.chat_input`. `render_excerpts` / `render_ai_expander` / `render_help_records` /
`render_plain_caption` are shared by both paths, so a live turn and a replayed turn are the
same pixels. `src/router.py` gained exactly one defaulted argument
(`_help_payload(..., slots=None)`) and **stays stateless** — accumulated slots arrive as an
argument and are never stored.

**`test_phase05.py` 104 → 137 asserts, all green.** Six were rescoped with an inline note
saying what each used to assert and why it moved; the rest are new. The rescope was
necessary, not cosmetic: `:32-39` `.index()`-ed into the whole module, and in file order
`def render_helpline_banner` now sits *after* `def render_help`, so a module-wide
`i_banner < i_help` would have failed on source layout while the rendered order was
unchanged. They now scope to `render_turn`'s body — the same property, asserted where it is
true.

**Findings and decisions, recorded:**

1. **`replay_turn` must not recompute, and that is now asserted, not intended.** Streamlit
   re-executes the whole script on every interaction. A history loop that re-queried each
   turn would pay N retrievals per keystroke and several times that once the dense arm
   lands. `test_phase05.py` checks `replay_turn`'s body contains no `load_retriever`,
   `offline_legal_hits`, `resolve_mode`, `help_display` or `route_question`.
2. **A second defaulted `TurnPayload` field was added, against the plan's letter.** The plan
   said "`TurnPayload.drift`. Nothing else." Replaying a *help* turn without one forces a
   live `router._help_payload` call on every rerun — which is the thing `replay_turn` exists
   to prevent — so `help_payload: dict` was added alongside `drift: list`. Both are
   defaulted; neither is read by `eval_chat.py` or `eval_heldout.py` (which work on the raw
   conversation JSON and never construct a `TurnPayload`), so no measured number can move.
   Disclosed rather than quietly absorbed.
3. **A Phase 05 render was deleted, and the second retrieval with it.** `render_legal` used
   to call `answer_legal(..., use_llm=False)` purely to print the prompt-version string —
   a *whole second retrieval per turn*, affordable once per page, not once per turn per
   rerun. It is now `_prompt_id()`, which reads `PROMPT_VERSION` / `CHAT_PROMPT_VERSION`
   from `src/rag.py` and mirrors the one line in `ask()` that chooses between them. That the
   plain flag really threads through is still proven, in the place proof belongs:
   `test_phase05.py`'s `answer_legal` asserts, untouched.
4. **Per-turn read-aloud does not collide, confirmed in the browser.** `read_aloud_html()`
   is byte-identical (11 asserts ride on it) and still hardcodes the ids `drlca-speak` /
   `drlca-speech`. Each `components.html` is its own iframe document, so N turns give N
   independent buttons — verified by reading `#drlca-speech` out of each frame and seeing
   different text per turn. **The cost is recorded, not fixed:** every read-aloud iframe
   carries its own `setInterval(apply, 1000)` theme watch, so an N-turn conversation runs N
   pollers. `test_phase05.py:182` requires the watch to be present, so removing it is a
   separate, asserted decision — not a drive-by.
5. **Fixed-key controls render on the last turn only, which is also the only correct
   scope.** `switch-%s`, `clarify-legal` and `clarify-help` are page-global keys. Acting on
   one pops the last turn, sets `explicit`, re-queues the question and reruns
   (`_requeue_last`). Re-answering a *mid*-conversation turn would invalidate every turn
   after it, because each was contextualised against it.
6. **Voice keeps its review step, and a latent Streamlit bug was fixed on the way.**
   `st.chat_input` cannot be pre-filled programmatically, so the mic feeds an editable draft
   `st.text_input` with a Send button. `try_voice_input()` previously wrote
   `st.session_state["q"]` *after* the `q`-keyed widget had rendered in the same run, which
   Streamlit forbids; it now writes `voice_draft`, and `render_voice_draft()` copies it into
   `q` **before** instantiating the widget. Clearing works the same way, on the next run.
7. **Quota readout ships labelled honestly.** `scripts/.quota_log.json` holds
   `{"YYYY-MM-DD": {"model": 3}}` — a date, a model name and an integer, **never a word of
   any conversation** — and fails open like `rag._cache_write`. The sidebar says *"recorded
   by THIS INSTANCE SINCE RESTART"*, never *"today"*: on the free host the filesystem is
   ephemeral and the instance sleeps after 15 minutes idle, so the number is a floor. Cache
   replays are deliberately **not** counted; they spend no quota.

**Browser verification** (`streamlit run app.py`, Chrome via DevTools, no key spent): a
four-turn conversation covering an ellipsis (*"so can they fire me?"* → carried on
`unbound-pronoun:they`), a clarify turn, and a narrowing (*"I'm deaf"* … *"anywhere in
Kano?"* → answered NNAD from the accumulated `disability` slot two turns later). Full banner
at page top **and** a helpline line leading every assistant turn; three excerpts inline plus
a *"3 more excerpt(s)"* fold; citation tags on every turn; per-turn read-aloud reading only
its own turn; both AI toggles OFF by default; **Clear conversation** empties the thread;
360 px viewport with **no horizontal overflow**; dark theme (`body.drlca-dark` set by the
theme-watch iframe, excerpt cards opaque `#0d1117` on `#e6edf3`) and high contrast (black /
white, white-bordered buttons) both coherent. **After the whole session neither
`scripts/.answer_cache.json` nor `scripts/.quota_log.json` existed at all** — the offline
path wrote nothing, because it had nothing to write.

**The three AI-failure paths were proven headlessly, at zero quota** — no key, a daily-cap
429, and a dead network. In all three `_run_ai_turn` returns False, `payload.answer` stays
`None` (**pending, never faked**), no quota is recorded, and the user sees one
plain-language warning with no traceback. Proving these live would mean deliberately
exhausting a daily cap, the same argument `test_phase09_ops.py` makes for failover.

**Observed, not changed:** in **dark + high contrast together** the sidebar computes to
`#010409` rather than the forced `#000`, because `body.drlca-dark section[...]` and
`body:has(.drlca-hc-on) section[...]` have equal specificity and the dark rule is emitted
later. Contrast against white text is ~19:1, so this is cosmetic, it predates this phase,
and `accessibility_css()` was not touched by it. Logged for whoever next opens that CSS.

**Owner-gated, as in Phase 05:** NVDA, a physical keyboard run, a live mic, and the
AI-expander live smoke (which costs quota).

#### Review pass — no blocking issues, two fixes taken

A fresh-eyes review re-ran `test_phase05.py` / `test_phase03.py` / `test_phase04.py`, checked
`import app`, traced every `session_state[key] = …` write in `app.py` against every widget
`key=`, and followed `_cache_write` / `ask()` / `build_prompt()` to confirm history never
reaches disk. **Verdict: ship.** It independently confirmed the widget-ordering audit (the
only widget-keyed value written outside its own widget is `q`, and both writes happen strictly
*before* the `q` widget is instantiated), that no fixed key renders twice in one script run,
and that `src/router.py` acquired no module-level state.

Two findings were acted on, taking the suite to **137**:

1. **`_prompt_id()` claimed more than the code enforced.** It derived "is this a multi-turn
   prompt?" from `turn_index > 0`, while `ask()` branches on
   `rag._render_history(history)` being non-empty. Equivalent today, but only by caller
   discipline — `chat.history_for_prompt()` applies `CARRY_WINDOW` and drops blank turns, so
   a future turn type could have predecessors and still render a single-turn prompt, and the
   caption would have been silently wrong with nothing to catch it. Now
   `_multi_turn(prior)` calls the same two functions `ask()` calls, `render_plain_caption`
   takes `prior` rather than a boolean, and three asserts pin it.
2. **A pre-existing assert was tautological.** `test_phase05.py`'s
   `no-wide-columns-for-banner` ended in `or True`, so it passed unconditionally and had
   been inflating the count since Phase 05. Rewritten to check the property its name claims
   and can now fail: every `render_helpline_banner()` **call site** sits at 4-space function
   top level, never nested inside a `with col:` block — which is how a banner ends up
   squeezed into a narrow column at 360 px.

The review also flagged the quota log and the *"AI-answer every new turn"* switch as feature
work beyond "wire the engine in". Both were in the agreed Phase C scope (see the bullets
above) and are documented here, in `STATUS.md` and in `HANDOFF.md`; the reviewer was working
from the diff and did not have the plan text. Recorded so the question is not re-opened.

Both eval harnesses were re-run after these fixes and are **still byte-identical to
`368f083`**.
