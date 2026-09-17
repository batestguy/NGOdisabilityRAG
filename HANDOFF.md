# HANDOFF — start here (60 seconds, updated 2026-09-17)

> **LATEST (2026-09-17): the chat work SHIPPED, and Phase D's gate answers GO.**
> Zero Gemini calls spent. Branch **`phase10/corpus-v2`**, off a merged `main`.
>
> **Both open owner decisions below are now CLOSED.** Push+PR happened first: PR #12
> (Phase 10 A+B+C + D-planning) merged, `main` `bb6f931` → **`6b10f62`**, and Render
> auto-deployed — **users now get the multi-turn chatbot, not the single-turn form.**
> The branch stack is unwound; `phase10/chat-core` and `phase10/chat-ui` are pushed.
> The orphaned 740-line doc pass was committed before anything else.
>
> **D2's GO/NO-GO GATE: GO.** The gazette's Arrangement yields a clean **`1..58`** — no
> holes, no duplicates, nothing out of range. The manifest-anchored parser is unblocked;
> the marginal-note fallback was **not needed and not used**; **no title was authored.**
> Manifest is on disk at **`data/processed/gazette_arrangement.json`** (58 entries,
> `"title_source": "arrangement"`) — **do not re-derive it.**
>
> **Read this before writing an OCR parser.** The first parse returned **23 of 58** and
> looked exactly like the truncated source Finding 1c predicted. It was not. RapidOCR emits
> the clause number and its title as **separate boxes**, and their vertical centres differ
> enough that the title often sorts *before its own number* — so a line-at-a-time regex
> anchored on `^\d+\.` can never match. Group boxes into **visual rows by vertical overlap**,
> then order left-to-right. Same failure class as v1's 25/62 uncitable Act chunks. The tell
> that it was a parser bug and not a finding: OCR confidence was **0.978–0.984**.
>
> **`scripts/ocr_local.py` was a live hazard and is now fixed.** It had a bare `main()` at
> module scope with no `__main__` guard, and `main()` unconditionally overwrites
> `data/processed/disability_act_2018_full.txt` — the v1 Act corpus every published baseline
> is measured against. Guard + `--force` added, both verified. Shared helpers now live in
> **`scripts/ocrlib.py`** (keeps box geometry; pymupdf/rapidocr imports are function-local).
> Keep running the `git diff main -- data/processed/disability_act_2018_full.txt` guard.
>
> **D1 landed:** `Chunk.path` defaulted · `build_corpus(version=)` as **pure relocation** ·
> `--corpus=` (equals form only) on 6 harnesses. Two prose claims are now **negative-tested**
> gates: `corpus_sha256()` (`25650238…e89a`) catches text moving *between* chunks at constant
> count, which the nine shape integers cannot see; `eval_phase06` asserts `ce716fb3…5f19` and
> is **Windows/CRLF-specific on purpose**, reading the file back from disk as bytes.
> Stdout gained 2 lines in `audit_corpus` + one ` sha256=…` in `eval_phase06` — **re-baselined
> here, not broken silently.** Everything else reproduces byte-identically.
>
> **NEXT: D2's clause locator + the 27-page body OCR**, then `_act_chunks_v2()` / `ACT_V2_SIZE`.
> `ACT_KNOWN_ABSENT = {38, 40}` **stays** — cl.38's *title* being in the Arrangement says
> nothing about its *body*. D6 deletes that constant, after the re-OCR.
>
> ---
>
> **Previous (2026-09-16): Phase 10 C (chat UI) DONE. Zero Gemini calls spent.**
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
> **Next: Phase D — corpus v2** (**`docs/phases/12_corpus_v2.md`**, written 2026-09-16; M3 of
> `10_corpus_rebuild_and_dense.md` is **superseded**). See **PHASE D — START HERE** below: the
> download is done, and **two of M3's premises turned out to be false** — Act cl.38/40 are
> **recoverable**, and the Constitution needs only the cheap fix.

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

- ~~**D** needs a >10MB download…~~ **DISCHARGED 2026-09-16.** `6document.pdf` is downloaded
  (14.1 MB, repo root, to be moved into `data/raw/` in D1) and verified as the authoritative
  gazette. It resolved the cl.38/40 question — **they were never missing**. See Finding 1.
- **F** needs **Colab or Kaggle GPU**. `torch`/`sentence-transformers` must **never** be
  installed into `drlca-rag` — `CLAUDE.md` records an env break from exactly that.
- **G** needs **~42 Gemini calls across 2 days** (40/day budget, two pools). That is an owner
  decision to spend, not something to start unprompted.

Working tree is clean apart from the known stray `D:NGORAG_review_judge.diff` (0 bytes,
U+F03A in the name, in no commit, deletion permission-blocked — still needs removing by hand).

## PHASE D — START HERE (corpus v2, **`docs/phases/12_corpus_v2.md`**)

> **The playbook moved.** Phase D is **`docs/phases/12_corpus_v2.md`**, written 2026-09-16, not
> M3 of `10_corpus_rebuild_and_dense.md`. **M3 is superseded and must not be executed** — two of
> its premises were measured on 2026-09-16 and are false. M3 is kept, with amendment boxes, so
> nobody re-picks up an invalidated step.
>
> **Branch:** `phase10/corpus-v2`, off `phase10/chat-ui`. **Zero quota. No new packages.**

**Phase D's download dependency is DISCHARGED.** `6document.pdf` (14.1 MB) is downloaded and sits
in the repo root awaiting a move into `data/raw/` (first task of D1).

### Finding 1 — the Act gap is a SOURCING failure, not an OCR failure. cl.38 and cl.40 are recoverable.

> **⚠ CORRECTED 2026-09-17 — the cl.38 row published in `4bcc763` was WRONG.** It claimed cl.38's
> body was in the v1 text at **L614**. **L614 is clause 48.** L612 reads `48.`; the Arrangement at
> **L74** says `48.Annual estimate and expenditure.`, which is exactly the marginal note wrapped
> around L614 at L613/L615; v1 continues `(a) cause tobekept accounts and records` (cl.48) where
> the gazette continues `(a) formulate and implement policies` (cl.38). `grep "formulate and
> implement"` returns **nothing** in v1. The match was made on string similarity to
> `38.TheCommissionshall-` **without reading the next line**.
>
> **cl.40's row is correct** — body at L545, bounded by `39.` (L524) and `41.` (L555), marginal
> note at L544/546/547/549/551 matching Arrangement L66.
>
> **The conclusion survives.** `ACT_KNOWN_ABSENT = {38, 40}` still retires — **cl.40 because it was
> never absent, cl.38 because the *gazette* recovers it (A109–A110)**, not because v1 had it. All
> 58 clauses still reachable in v2. 2026-09-13 was **right about cl.38's absence**, wrong only
> about its **irrecoverability**. Full detail + three new findings: `docs/phases/12_corpus_v2.md`.

The download is *Federal Republic of Nigeria Official Gazette No. **10**, Vol. 106, 21 January
2019, Act No. 2, pages **A97–A122*** — the authoritative gazette. 27 pages, 0 embedded text chars
(a scan, like the existing copy), but **no duplicate adjacent page pair**. Targeted OCR
(`rapidocr_onnxruntime`, dpi 200) of gazette pages **13, 14, 15** recovered both clauses in full.

**State of the v1 text, corrected 2026-09-17:**

| clause | gazette | `data/processed/disability_act_2018_full.txt` | verdict |
|---|---|---|---|
| 38 | `38.TheCommissionshall-` (A109) | opening + (a)–(i) **ABSENT**; its (j)–(r) tail is present at L501–522, misfiled | **absent from v1, recovered from the gazette** |
| 40 | `40.—(1) There shall be an Executive Secretary…` (A111) | `(1) There shall be an Executive Secretary for the Commission who shall-` (**L545**) | **never absent** — OCR dropped the numeral |

The duplicate page **is** real (adjacent-page cosine **0.978 p5–p6** vs a 0.794 runner-up, dpi 100,
16×16 mean-pooled, **mean-centred**) — and it **did** cost cl.38's opening. It did **not** cost cl.40.

**Three findings from the 2026-09-17 re-check, all strengthening the case for v2:**

1. **v1's clause 37 is silently corrupted.** A physical page is missing at the `===== PAGE 14 =====`
   boundary (**L500**): raw OCR p13 ends at cl.37(b), p14 opens mid-list at cl.38(j).
2. **A LIVE citation-integrity defect.** Act chunk 33 is reffed **`cl. 39`** and opens with cl.38's
   `(o)`–`(r)`, including *"procure assistive devices for all disability types"*. **The app can
   today serve cl.38's text under an `[Act cl. 39]` tag** — a wrong citation that passes
   `verify_citations()` mechanically. (Chunk 31 `cl. 36,37` is clean; chunk 32 is `general`.)
3. **v1 L542 reads `PARTVII`** where the Arrangement (L64) and the gazette say **PART VIII**; and
   **v1's Arrangement truncates at L77, `51.Power to acquire land.`** — so `audit_corpus.py:64-66`
   cites it as the source of `ACT_CLAUSES = range(1, 59)` when it does not contain 52–58. Right
   number, wrong source. **D2's Arrangement gate must therefore run on the gazette, whose
   Arrangement pages have not been OCRed yet.**

**Retires by name:** `ACT_KNOWN_ABSENT = {38, 40}` at **`scripts/audit_corpus.py:80`** (deleted,
**not emptied** — in **D6**, once the v2 corpus that recovers cl.38 exists) · `audit_corpus.py`'s
*"the pixels do not exist"* line · the **irrecoverability half** of the 2026-09-13
`LEARNING_JOURNAL.md` claim · the old standing fact below.

**All 58 clauses are reachable in v2 and the gap manifest may end up empty.** *Scope limit: only
pages 1, 13, 14, 15 of 27 were OCRed. "All 58 clauses present" is a D2 verification task, not a
finding.*

**D1 and D2 are designed, not just listed.** `docs/phases/12_corpus_v2.md` now carries
*"Implementation notes"* under both — the `Chunk`-field sweep, the three-tier caller policy, the
two prose-claims-become-gates, the three-layer OCR/parse/runtime split, the marginal-note geometry
measurements, the monotonic-cursor locator and the pre-written cross-check predictions. **Read
them before writing code; they exist so the next session executes rather than re-derives.**

### Finding 2 — the Constitution needs only the cheap fix to clear the gate

**All 99 uncitable Constitution chunks are Arrangement-of-Sections material** — 88 under 60 words,
and every one of the 11 at ≥60 words is *also* a numbered title listing (`"236 Practice and
procedure"`). **Zero substantive body text is uncitable.** Excluding the Arrangement pages takes
`general` 99 (4.7%) → ≈0 and deletes the `toc-trap` class **without touching `CONST_SIZE = 400`**.

M3's 2104 → ~500 section-unit re-extract — the riskiest change in the whole plan — **is not needed
for the gate** and defers to Phase E, where the dense arm actually wants it.

### Finding 3 — M3's milestone order is backwards

M3 runs M1 (width) → M2 (dense) → M3 (corpus). M2 ships `data/embed/chunks_gemini.f16.npy`, a
**per-chunk** artifact keyed on a corpus sha256 — rebuilding the corpus afterwards invalidates
every vector and forces a full re-embed. **Corpus first.** This is what `HANDOFF.md` already
assumed by putting D before E; the playbook never said why.

**Also measured:** the Act's **16 packed refs are all consecutive runs** (`cl. 3,4,5` … `cl. 56,57`)
— pure 800-char cutting, fixable mechanically. The Factsheet's 19 packed refs are **disordered**
(`Section 51,40`, `Section 50,45,54`) — `recursive_split(500/50)` cutting the S/N table mid-row.

**The audit gate is `ref == "general"` ≤1% per doc** — the gate that removes the uncitable-chunk
class named three separate times now (Act cl.19, `CT7.t2`, and the 25-of-62 uncitable Act chunks).

### What `app.py` looks like now (Phase C, so Phase D does not re-derive it)

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

**Housekeeping.** `phase10/chat-core` → `phase10/chat-ui` → (`phase10/corpus-v2`) is about to be
**three unpushed branches deep** off `main` — **still open**, worth deciding whether to push and
PR the chat work before Phase D starts. `CLAUDE.md`'s *"Next up:
`docs/phases/08_retrieval_upgrades.md`"* pointer is **stale** — fix it when `CLAUDE.md` is next
opened, in D6. **DECIDED 2026-09-16:** the 14 MB gazette PDF **gets committed** to `data/raw/`
(consistent with the already-tracked 5.2 MB Act and 8.5 MB Constitution; never read at boot, so
the Render runtime is untouched) — in its **own commit** in D1, so the blob is easy to find later.

## Next, in this order

**Updated 2026-09-16.** The phase ordering is now:

| phase | what | playbook | quota |
|---|---|---|---|
| **D — NEXT** | **corpus v2** (Act re-OCR + manifest parse, Factsheet table, Constitution Arrangement exclusion, refusal re-calibration, re-baseline) | **`docs/phases/12_corpus_v2.md`** | **0** |
| E | width / pool depth + dense retrieval + the Constitution section-unit re-extract | `10_corpus_rebuild_and_dense.md` **M1, M2** (reordered to here) | probe + embeddings |
| F | fine-tune on free GPU + distil the offline tier | `10_...md` M4 | 0–20 |
| G | fresh transcripts, judge, cross-turn citation drift | `10_...md` M5 + `11_chat.md` | ~42 over 2 days |

**Why D before E:** M2's `data/embed/chunks_gemini.f16.npy` is a **per-chunk** artifact keyed on a
corpus sha256. Embedding before the rebuild throws all of it away. See Finding 3 above.

The older Phase 08/09 backlog below is **still open but now sits behind D**, and part of it is
already overtaken — Phase 10 measured lexical retrieval as exhausted, and Phase D is the response.
Read `docs/phases/09_evidence_and_generation.md` before picking any of it up. In short:

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
3. **Shippable retrieval (zero quota).** ~~NEXT~~ — **BM25 was built and FALSIFIED 2026-09-13**
   (a coin flip: ranks the expected chunk higher on 15 of 91 pairs, lower on 16). The
   offline-computed `synonyms_auto.json` half is still open, but Phase 10 B/D supersede the
   motivation: the hand-written map's weakest class is the one it exists to fix, and the corpus,
   not the ranker, is the ceiling.
4. **Generation fix (quota-paced).** Q3 answer-shape floor + the named `reverse_rel` fix in
   its own commit + a fresh 12-call generation pass.
5. **Owner-side:** frames → GIF encode + README embed (`docs/demo/` + storyboard are
   ready) → NVDA/keyboard/mic gates → LinkedIn (+ optional Streamlit 2nd link).

## Standing facts (don't re-derive)

- ~~**Act cl.38 and cl.40 are absent from the source PDF; no OCR or VLM can recover them.**~~
  ~~**FALSIFIED 2026-09-16** — both clause bodies are in the v1 text right now, at L614 and L545.~~
  **RE-CORRECTED 2026-09-17 — the 2026-09-16 correction was itself half wrong. Read this version.**
  - **cl.40: never absent.** Body at **L545** (`(1) There shall be an Executive Secretary for the
    Commission who shall-`), numeral `40.—` OCR'd away. Bounded by `39.` (L524) and `41.` (L555).
  - **cl.38: genuinely absent from v1**, opening and (a)–(i). **L614 is clause 48, not 38** — L612
    reads `48.`, the Arrangement at L74 says `48.Annual estimate and expenditure.` (the marginal
    note wrapped at L613/L615), and v1 continues `(a) cause tobekept accounts and records` where
    the gazette continues `(a) formulate and implement policies`. `grep "formulate and implement"`
    → **nothing** in v1. cl.38 is recovered from the **gazette** (A109–A110), not from v1.
  - **cl.38's (j)–(r) tail IS in v1** (L501–522), and chunk 33 carries `(o)`–`(r)` under the ref
    **`cl. 39`** — so the app can serve cl.38's text with an `[Act cl. 39]` tag **today**.
  - The duplicate page 5–6 **is** real (adjacent-page cosine 0.978 vs a 0.794 runner-up) and it
    **did** cost a physical page — the one carrying cl.37's tail and cl.38's opening. It did not
    cost cl.40.
  - **`ACT_KNOWN_ABSENT = {38, 40}` at `scripts/audit_corpus.py:80` is still a false constant** and
    is deleted (not emptied) in **D6** — after the gazette re-OCR that recovers cl.38, not before.
  - **The no-stub / no-paraphrase / no-model-knowledge rule stands regardless** — it governs real
    gaps, and cl.38 was one until the gazette arrived.
  - **The lesson, twice over:** 2026-09-13 inferred *what* a measured duplicate cost without
    grepping the text. 2026-09-16 grepped the text but matched a line on string similarity
    **without reading the next one**. Both published. Check the neighbours, not just the match.
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
