# HANDOFF — start here (60 seconds, updated 2026-09-16)

> **Latest (2026-09-16): Phase 10 C (chat UI) DONE. Zero Gemini calls spent.**
> Branch `phase10/chat-ui`, off `phase10/chat-core`. Playbook: `docs/phases/11_chat.md`
> (Step C results). **DRLCA is a chatbot now** — `streamlit run app.py` gives you a
> multi-turn conversation, not the single-turn form.
>
> **This phase spent Phase B's gain and measured nothing new.** No retrieval, scoring, corpus
> or prompt change — so `eval_chat.py` and `eval_heldout.py` were *required* to reproduce
> `368f083` exactly, and did: **byte-identical stdout**. `eval_phase06.py` still hashes
> `CE716FB3…5F19`. `git diff --stat main -- requirements.txt` **empty**. Baselines were
> captured **before** the first edit, which is the only reason that can be claimed.
>
> `app.py` → **`render_turn`** (computes + renders one new turn; compute and render stay
> fused because the banner invariant is asserted on literal source adjacency inside it) ·
> **`replay_turn`** (renders a stored `TurnPayload` — **no retrieval, no router, no
> network**, now asserted) · `render_history` · a `st.chat_input`-driven `run()`.
> `src/router.py` gained **one defaulted arg** and **stays stateless**.
> **`test_phase05.py` 104 → 137, all green**, 6 rescoped with an inline note each.
>
> **Two deviations from the plan, disclosed not absorbed:** (1) a **second** defaulted
> `TurnPayload` field, `help_payload` — without it, replaying a help turn forces a live
> router call every rerun, the exact thing `replay_turn` exists to prevent; neither new field
> is read by any eval. (2) the per-turn `answer_legal(..., use_llm=False)` **probe was
> deleted** — it existed only to print the prompt-version string and cost **a whole second
> retrieval per turn per rerun**; now `_prompt_id()`, reading the constants from `src/rag.py`.
>
> **Width/pool depth did NOT land here** (the older plan had it in this phase). `k=3/doc,
> top_n=6` is what both harnesses measure; Phase B measured the change at **test +0.000**. It
> moves in **Phase E**, in the same commit as the harnesses. The **display** split (3
> excerpts inline + rest in one fold) did land — that is presentation, not retrieval.
>
> **Privacy: history is `st.session_state` only.** After a full four-turn conversation
> **neither `scripts/.answer_cache.json` nor `scripts/.quota_log.json` existed at all** — the
> offline path wrote nothing. The new quota log (gitignored) holds counts only,
> `{"YYYY-MM-DD": {"model": 3}}`, and the sidebar says *"THIS INSTANCE SINCE RESTART"*, never
> *"today"* — the free host's filesystem is ephemeral and it sleeps after 15 min.
>
> **Browser-verified** (Chrome/DevTools, no key spent): ellipsis *"so can they fire me?"*
> carried on `unbound-pronoun:they`; *"I'm deaf"* → clarify, then *"anywhere in Kano?"* two
> turns later still answers **NNAD** from the carried slot; banner at page top **and** leading
> every assistant turn; per-turn read-aloud genuinely isolated (each `components.html` is its
> own iframe document); both AI toggles OFF; Clear conversation works; 360 px no overflow;
> dark + HC coherent. The three AI-failure paths (no key / 429 daily cap / network down) were
> proven **headlessly at zero quota** — `answer` stays `None`, **pending, never faked**.
>
> **Latent bug fixed in passing:** `try_voice_input()` wrote `session_state["q"]` *after* the
> `q`-keyed widget had rendered, which Streamlit forbids. It never fired because the mic path
> is owner-gated. It now writes `voice_draft`, copied into `q` before instantiation.
>
> **Fresh-eyes review: no blocking issues, verdict ship.** Two fixes taken (→ **137** asserts):
> `_prompt_id()` decided multi-turn from `turn_index > 0` while `ask()` branches on
> `rag._render_history()` being non-empty — equivalent today only by caller discipline, now
> `_multi_turn(prior)` calls the same two functions `ask()` calls; and a **pre-existing
> tautological assert** (`no-wide-columns-for-banner` ended in `or True`, padding every count
> published since Phase 05) was rewritten so it can fail. Both evals re-run after: still
> byte-identical to `368f083`.
>
> **Next: Phase D — corpus v2** (`docs/phases/10_corpus_rebuild_and_dense.md`). See the
> **PHASE D — START HERE** section below.

> **Previous (2026-09-15): Phase 10 B (chat-core) DONE. Zero Gemini calls spent.**
> Branch `phase10/chat-core`. Playbook: `docs/phases/11_chat.md`. Full run:
> `scripts/baseline_chat_2026-09-15.txt`.
>
> **DRLCA is becoming a chatbot, and the reason it is a RETRIEVAL phase, not a UI phase:**
> *"so can they fire me?"* contains no disability term and no statutory term, so no
> re-ranker, no encoder and no corpus rebuild can answer it — the query does not contain the
> question. `src/router.py` is stateless (correctly, and it stays that way), so **nothing in
> the stack resolved ellipsis before this.** The multi-turn set was therefore built and
> measured **before** the chat UI and before corpus-v2/dense: tuning those on single-turn
> questions only would optimise a query distribution the chatbot never issues.
>
> New: `data/eval/conversations.json` (22 conversations / 62 turns / 51 corpus-verified refs)
> · `scripts/chatset.py` · `src/chat.py` · `history=` on `ask()`/`build_prompt()` ·
> `scripts/eval_chat.py`. **`chat_test` was authored BLIND before `src/chat.py` existed.**
>
> **Numbers (corpus v1, shipping arm, naive → contextualised):** chat_dev **0.464 → 0.571**,
> chat_test **0.435 → 0.565**. Ellipsis **0.000 → 0.333** (dev) / **0.200 → 0.600** (test);
> the `direct` control moves **+0.000** on both. recall@60 **0.714 → 0.929** / **0.783 →
> 0.913**. Help slots **3/5 → 5/5** and **1/2 → 2/2**. **False refusals FELL** (1/28 → 0/28,
> 3/23 → 1/23), **0 contextualisation-induced**.
>
> **The new chat-only trap did NOT fire.** Off-corpus-after-legal clears `MIN_SCORE` **2/2 in
> both arms, both sets, delta 0.000** — same as the published single-turn 5/5, a property of
> the inverted-band floor, **not** something chat introduced. **`MIN_SCORE` untouched.**
>
> **Two things recorded rather than fixed** (read this before "improving" them):
> chat_test's **pronoun class did not improve at all** (0.400 → 0.400), and a blind test-set
> note (`CT6.t3`) predicted a carry decision that behaves otherwise. Both stay as measured —
> tuning either against `chat_test` is exactly how the 30 held-out questions were spent on
> 2026-09-13. Thresholds were chosen on **chat_dev only**.
>
> **Two new hard invariants, now asserts** (`test_phase09_ops.py` 38 → **51**):
> `history=None` renders a **byte-identical** prompt (the cache keys on the whole rendered
> prompt), and history renders **BEFORE** the final `"Question: "` line — that one is
> **privacy**: `_cache_write` stores only that line, and this population discloses abuse and
> coercion. Chat has its own `CHAT_PROMPT_VERSION = "chat-cite-strict-v1"`.
>
> **Unmeasured on purpose:** cross-turn citation drift needs a generated answer to read, so it
> costs quota. `chat.cross_turn_drift()` is wired and runs in Phase G.
>
> ~~**Next: Phase C — the chat UI.**~~ **DONE 2026-09-16** — see the banner at the top.

## Session close 2026-09-16 — what is done, what is NOT

**Done this session:** Phase 10 **C only**, on `phase10/chat-ui` (branched off
`phase10/chat-core`). **Gemini spend this session: ZERO.** Nothing is pushed.

**Not started:** Phases **D, E, F, G**. Phase C touched no retrieval parameter, no corpus
file and no prompt string — the chat UI is a surface for Phase B's engine and nothing more.

Three of the remaining phases have hard external dependencies the next session should know
about before planning:

- **D** needs a >10MB download (`ncpwd.gov.ng/pdfs/6document.pdf`, the one untested lead for
  the missing Act cl.38/40) fetched locally, not via a fetch tool.
- **F** needs **Colab or Kaggle GPU**. `torch`/`sentence-transformers` must **never** be
  installed into `drlca-rag` — `CLAUDE.md` records an env break from exactly that.
- **G** needs **~42 Gemini calls across 2 days** (40/day budget, two pools). That is an owner
  decision to spend, not something to start unprompted.

Working tree is clean apart from the known stray `D:NGORAG_review_judge.diff` (0 bytes,
U+F03A in the name, in no commit, deletion permission-blocked — still needs removing by hand).

## PHASE D — START HERE (corpus v2, `docs/phases/10_corpus_rebuild_and_dense.md`)

The Phase C reconnaissance that used to live here is **spent** — the chat UI is built, and
the `app.py` line numbers it quoted are gone. What Phase C actually shipped is in
`docs/phases/11_chat.md` (Step C results) and the 2026-09-16 journal entry; read those, not a
reconstruction.

**What `app.py` looks like now**, so the next session does not have to re-derive it:

- `render_turn(question, explicit, plain, history, turn_index) -> TurnPayload` — computes AND
  renders one new turn. Fused on purpose: `test_phase05.py` asserts the banner invariant on
  the *literal adjacency* of `render_helpline_banner()` and the `# Single routing seam`
  comment inside this function's body. Splitting compute from render makes that unassertable.
- `replay_turn(payload, turn_index, live)` — renders a stored turn. **No retrieval, no
  router, no network** — asserted, because Streamlit reruns the whole script on every
  interaction.
- `render_history(live_last)` · `render_excerpts` · `render_ai_expander` · `render_defects` ·
  `render_help_records` · `render_plain_caption` — the last five are shared by both paths.
- `run()` — sidebar → title → banner → history → voice draft → `st.chat_input`. A submitted
  question goes into `st.session_state["pending"]` and reruns, so the new turn paints in
  position at the end of the thread.
- Fixed-key controls (`switch-%s`, `clarify-legal`, `clarify-help`) render on the **last turn
  only**; acting on one pops that turn and re-queues it (`_requeue_last`).

**Three things Phase C recorded and deliberately did NOT fix.** Do not "tidy" them without
reading why:

1. **N read-aloud iframes means N `setInterval` theme pollers.** Each `components.html` is
   its own iframe carrying `theme_watch_html()`. `test_phase05.py:182` requires the watch to
   be present, so centralising it is a deliberate, asserted change — not a drive-by.
2. **Dark + high contrast together leaves the sidebar `#010409`, not `#000`** (equal
   specificity, dark rule emitted later in `accessibility_css()`). ~19:1 contrast, predates
   Phase C, `accessibility_css()` was not opened.
3. **Width / pool depth is Phase E, not a UI change.** `k=3/doc, top_n=6` is what
   `eval_chat.py:106-108` and `eval_heldout.py` measure, and `offline_legal_hits`' docstring
   forbids a display path that slices differently from `ask()`. Move the harnesses in the
   same commit or the shipped system detaches from every published number.

**Phase D's own dependency, unchanged:** it needs a >10 MB download
(`ncpwd.gov.ng/pdfs/6document.pdf`, the one untested lead for the missing Act cl.38/40)
fetched locally, not via a fetch tool. Its audit gate is `ref == "general"` **≤1% per doc** —
the gate that removes the uncitable-chunk class named three separate times now (Act cl.19,
`CT7.t2`, and the 25-of-62 uncitable Act chunks).

## Next, in this order (full plan: `docs/phases/09_evidence_and_generation.md`)

Phase 08 steps 1 (synonym map), 2 (cite-constrain fix-B), 3 (judge) and 6a (answer cache)
are **DONE 2026-09-11 and live**. A planning pass on 2026-09-11 then found three code facts
that **change what should come next** — read `docs/phases/09_evidence_and_generation.md`
before picking anything up. In short:

- **Phase 08 steps 4/5 as written cannot reach a real user.** Both need a model at *query*
  time (step 4 a cross-encoder; step 5 to embed the incoming query — prebuilt chunk vectors
  do not solve that half), and `requirements.txt` forbids ONNX/FAISS. Flag-gated = flag OFF
  in production. **Superseded by Phase 09 step 3**, which delivers both wins with zero
  query-time deps.
- **Retrieval is no longer the bottleneck; generation is.** recall 0.925 vs a 0.75 gate,
  while the judge confirmed Q3 thinness is a REAL prompt defect (Q3 recall 1.000).
- **The synonym map is fitted to the set that scores it** (n=10, entries kept/deleted by
  their effect on Q5/Q7/Q8/Q9). 0.925 cannot distinguish generalization from memorization.

Order (owner-confirmed 2026-09-11, all four, under a **runtime-shippable-only** constraint):

1. ~~**Ops hardening (zero quota, small).**~~ **DONE 2026-09-13, PR #9.** `--no-cache` +
   `--failover` on `test_phase02.py`; opt-in daily-cap-only failover in `src/rag.py`.
2. ~~**Widen the evidence base (zero quota).**~~ **DONE 2026-09-13, PR #10.** 30 held-out
   questions; **held-out recall 0.420 vs frozen-10 0.925** (see the banner at the top).
   False-refusal 0/25; gate-level false-answer 5/5.
3. **Shippable retrieval (zero quota) — NEXT.** BM25 re-rank *inside* the existing cosine gate
   (step 4's win, no ONNX) + an offline-computed `synonyms_auto.json` (step 5's win, no
   query-time model).
4. **Generation fix (quota-paced).** Q3 answer-shape floor + the named `reverse_rel` fix in
   its own commit + a fresh 12-call generation pass.
5. **Owner-side:** frames → GIF encode + README embed (`docs/demo/` + storyboard are
   ready) → NVDA/keyboard/mic gates → LinkedIn (+ optional Streamlit 2nd link).

## Standing facts (don't re-derive)

- ~~Q5 penalties = correct refusal ×4 runs~~ **SUPERSEDED 2026-09-11.** The synonym map
  closed the vocabulary gap (corpus says *offence/fine/imprisonment*, query says
  *penalties*): Q5 recall **0.000 → 0.250**, live-verified returning `[Act cl. 2]` /
  `[Act cl. 1]`. Still misses cl.8,9,10,13,29,30 — rerank/hybrid remain the real fix.
  On the old "NO synonym hack" warning: the map is not that hack — entries are
  corpus-verified legal vocabulary and the full matrix was re-run on every change — but
  the map IS a score-sensitive surface, so the warning still applies to new entries.
  **Expansion is not symmetric**: an `education` key cost Q7 recall 1.000 → 0.500 and was
  deleted; only `school → education` (user→corpus direction) survives.
- **Q5 faithfulness now reads 0.000 and that is CORRECT, not a regression.**
  `eval_phase06.py:176-182` scores a refusal 1.0 only if no expected ref was retrieved.
  The transcript answer is frozen pre-M1 (it refuses); retrieval is recomputed live and
  now finds `act2018:1,2`, so the refusal is no longer justified. Net effect:
  **faith_audited 0.867 UNDERSTATES the system** — a fresh generation pass would likely
  answer Q5. Don't "fix" this in the eval; it needs 12 generator calls.
- Synonym expansion is **two-side gated** (`src/retrieve.py`). Entry gate: expand only if
  the user's own words already clear `MIN_SCORE` (otherwise expansion manufactures corpus
  overlap and turns a refusal into an answer). Exit gate: keep the expansion only if it
  still clears the floor (otherwise appending absent terms dilutes the query-vector norm
  and creates a FALSE REFUSAL). Guaranteed property is narrow and exact: *expansion never
  turns a refusal into an answer, and never turns an answer into a refusal; it only
  re-ranks within the answered set.* It does NOT always raise the top score.
- Q10: v2 false refusal → fixA variance resolved (s.46 quotes) → fixA2 PARTIAL
  (s.39 3rd-claim misattr). Q9: v2 s.33 trap → fixA2 removed, s.34 still missing.
- Precision 0.333 is BY DESIGN (per-doc merging trades it for recall) — never gate it.
- Coverage/reverse_rel custom misses are metric artifacts (documented) — don't tune
  yardsticks; reverse_rel stays recorded FAIL until the judge rules.
- Fix A: 14 Constitution TOC fragments → `general` in `const_ref`; ranking untouched.
  **Fix B landed 2026-09-11: `MANUAL_FLAGS` is now `[]`.** `_is_toc_fragment` widened to
  orphan list-entries and `verify_citations` checks cited numbers against the chunk's own
  `ref` instead of pooled chunk text (pooled matching is exactly what let Q10 cite s.39 for
  High-Court text sitting in the same pool). Q10 `faithfulness_auto` 1.000 → 0.667,
  mechanically. **Trap for anyone widening it further:** `verify_ground_truth` asserts every
  EXPECTED number appears in some chunk's `ref`, and demoting a ref to `general` removes its
  numbers — an over-eager rule hard-crashes the eval before it prints anything. Measure the
  blast radius in isolation first (2026-09-11: 12/2,104 chunks relabelled, s.17/34/46 kept
  17/6/6, no section number lost).
- Eval script points at fixA2 transcript now. Never fake LLM rows.
  LLM runs → versioned files; dry runs → `--out=<temp path>` (space form ignored!).
- Test commands (all via project python): `bench_phase01` (PASS) · `test_phase03`
  (16/16+7/7) · `test_phase04` (PASS) · `test_phase05` (104) · `eval_phase06.py --out=...` ·
  `test_phase09_ops` (38/38, zero network) · `eval_heldout` (held-out retrieval baseline) ·
  `ablate_phase08` (PASS). `eval_heldout.py` exits nonzero **only** on ground-truth failure or
  a **frozen-10** regression — never on a held-out number, by design.
- Eval ground truth lives in **`data/eval/questions.json`** (10 `frozen10` + 30 `heldout`),
  loaded via `scripts/evalset.py`. `eval_phase06.EXPECTED` is now derived from it, and
  `judge_phase06.py` / `ablate_phase08.py` still import `EXPECTED` unchanged.
  `bench_phase01.load_questions()` is **KEPT, not retired**: `assert_frozen10_matches_notebook()`
  requires it and the JSON to agree in order on all ten texts, so a reworded frozen question
  fails loudly instead of silently moving the yardstick. **Frozen questions are frozen** — add
  new ones, never edit these, never merge held-out into the frozen 10.
- Quota: **TWO limits, not one** (corrected 2026-09-11 — the missing one cost 9 calls).
  20/day/model **and 10 requests/MINUTE/model**. The per-minute 429 is
  `GenerateRequestsPerMinutePerProjectPerModel-FreeTier` and carries its own `retryDelay`
  (~37s) — it is NOT terminal and must be retried, not treated as the daily cap. A daily-cap
  429 stays pending and unfaked. `scripts/judge_phase06.py` has the working pattern (7s
  pacing, `_is_per_minute()`, bounded backoff, checkpoint after EVERY call).
  503-transients retry with backoff, same day OK. Models draw from **separate pools**:
  the judge run spent `gemini-2.5-flash-lite` and touched `gemini-2.5-flash` zero times.
  **Lever now WIRED (2026-09-13, was "unused"):** the real daily budget is **40, not 20**.
  `rag.FALLBACK_MODEL = gemini-2.5-flash-lite`; `ask(failover=True)` / `generate(failover=True)`
  fail over **once**, on a **daily-cap** 429 only, and record `model_used` (top level and in
  `route`; `route["model"]` still means the model *requested*). Off by default — a flash-lite
  answer is not a flash answer. A per-minute 429 **re-raises** so the caller retries it.
  `is_per_minute_429()` / `retry_delay()` now live in `src/rag.py`, not the judge script.
- Answer cache live (`src/rag.py`, gitignored at `scripts/.answer_cache.json`): keyed by
  sha256(model + NUL + **whole rendered prompt**), so context and prompt version are in the
  key. Fails OPEN. Every hit sets `cached=True` and `test_phase02.py` persists it — a replay
  can never be written up as a fresh call.
  **Corollary found 2026-09-11, FIXED 2026-09-13:** the cache defeated the pending two-run
  flakiness check — `test_phase02.py` never passed `use_cache`, which defaults `True`, so run
  two would have been 12 cache hits measuring nothing. `test_phase02.py --no-cache` now exists
  and threads `use_cache=False` through. **Use it for the flakiness check** (still unrun).
  *(A prompt-version bump does NOT need the flag — the key covers the whole rendered prompt,
  so a new `PROMPT_VERSION` misses the cache automatically.)*
- **Phase 08 steps 4/5 are SUPERSEDED, not just deferred (2026-09-11).** Both need a model at
  *query* time — step 4 a cross-encoder, step 5 to embed the incoming query (prebuilt chunk
  vectors do not solve that half) — and `requirements.txt` bans ONNX/FAISS. "Flag-gated"
  therefore means OFF in production: local eval numbers move, users see nothing. Replacements
  in `docs/phases/09_evidence_and_generation.md` step 3: BM25 re-rank *inside* the cosine gate
  (zero new packages) and an offline-computed `synonyms_auto.json`. **Never re-rank by
  replacing the cosine scorer** — BM25 scores are unbounded and would silently invalidate the
  `MIN_SCORE` calibration at `src/retrieve.py:26-44` and change refusal behaviour.
- **recall 0.925 is measured on the same 10 questions the synonym map was tuned on.** Entries
  were kept or deleted by their effect on Q5/Q7/Q8/Q9, so the number cannot distinguish
  generalization from memorization. Treat it as an upper bound until the Phase 09 held-out set
  exists. The frozen 10Q must stay frozen AND separate — never merge held-out questions into
  it, or every historical artifact from Phase 01 onward loses comparability.
- CSS rules of the road (learned 2026-09-09): watermark div lives INSIDE
  stMainBlockContainer (z-1), so sidebar needs z-index 2; Streamlit's own section
  rules beat un-`!important` ones; height=0 iframes never mount (use 1); srcdoc
  scripts race `<body>` (DOMContentLoaded-ready wrapper); restart server after
  edits; HC mode trips the luminance gate (bodyDark=true — harmless).
- Render notes: create via `render services create --name ... --type web_service
  --repo ... --branch main --runtime python --plan free --build-command
  "pip install -r requirements.txt" --start-command 'streamlit run app.py
  --server.port $PORT --server.address 0.0.0.0' --env-var PYTHON_VERSION=3.11.0`
  (+ `GOOGLE_API_KEY` from env, never printed). Free sleeps 15 min idle (~1 min
  wake); ephemeral FS fine (corpus prebuilt). Token expired once → user `render login`.

**Pending owner inputs:** frames→GIF encode + README embed (`docs/demo/` 5 frames +
`docs/demo_storyboard.md` are ready) + NVDA/keyboard/mic gates + LinkedIn (+ optional
Streamlit link).
**Pending quota:** two-run flakiness check (24 calls with failover, or 2 days) — **UNBLOCKED
2026-09-13, not run.** Use `test_phase02.py --no-cache --failover --out=<versioned path>`;
+ AI-expander live smoke. **Nothing has been spent on Gemini since 2026-09-11.**
**Pending code:** `docs/phases/09_evidence_and_generation.md` steps **3** (BM25 re-rank inside
the gate + offline `synonyms_auto.json`) and **4** (Q3 answer-shape floor + named reverse_rel
fix). Steps 1 and 2 are DONE (2026-09-13). Phase 08 steps 4/5 are superseded by (3). Step 3 now
has a real target — vocab-mismatch is the weakest held-out class at 0.312 — and, for the first
time, an uncontaminated set to be judged on. Ablate on frozen-10 **and** held-out, always both.
Nothing is blocked.
**Housekeeping:** a 0-byte stray file `D:NGORAG_review_judge.diff` (U+F03A in the name, from a
bad shell redirect) sits untracked in the repo root; deletion was permission-blocked twice, so
it needs removing by hand. It is in no commit.
