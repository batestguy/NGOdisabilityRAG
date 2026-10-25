# H9 — Deterministic follow-ups for the offline path (planned 2026-10-22)

**Status: PLANNED. Docs only: no code, zero quota.** Each step has its own branch, a gate written **in advance**, its
cost, what only the owner can do, and a "do not" list. Read `CLAUDE.md` first.

**Standing rule:** a push to `main` redeploys to real users on Render. That is the owner's call, every time.

## Why H9 exists, and what it is NOT

The owner asked (2026-10-22) whether to build a deterministic chatbot that handles follow-ups, in case Gemini quota is
exhausted. **Most of that already exists and needs no quota:**

| Already offline (zero quota) | Where |
|---|---|
| Follow-up questions resolved against earlier turns ("so can they fire me for that?") | `src/chat.py` `contextualise()`. Phase 10 B: chat_dev 0.464 → 0.571, chat_test 0.435 → 0.565 strict recall |
| Help details carried across turns ("I'm deaf" … "anywhere in Kano?") | `src/chat.py` `merge_help_slots()` |
| Clarifying question when legal vs help is unclear | `src/router.py` `CLARIFY_QUESTION`, clarify policy |
| Cited excerpts + helplines on every legal turn; AI prose is opt-in, default OFF | `app.render_turn()`, `ui_render.render_excerpts()` |
| Quota exhausted → `answer=None` (pending) + one plain-language note; nothing fabricated | `src/rag.py`, the "Never fake an LLM row" invariant |

**So H9 is not "make the bot work without quota". It already does.** H9 adds two things the offline path lacks, ordered
by risk:

* **H9a — suggested follow-up questions** (low risk): "You might also ask: …" buttons under a legal answer. They suggest
  questions, never answers, so they cannot misstate the law.
* **H9b — "key lines"** (moderate risk): one verbatim, cited sentence pulled from each of the top excerpts, so a user
  sees the most relevant words first. It is extractive only.

**Explicitly rejected:** a templated or rule-based *composed* answer (prose stitched from excerpts). Three reasons:
1. **`MIN_SCORE` is a weak floor, not a semantic filter.** Legal-sounding off-topic questions clear it, and the guard
   meant to catch them (H4) was declined. Mis-retrieved excerpts look like excerpts; a mis-composed answer looks like
   advice.
2. **Partial quotes drop exceptions.** "subject to", "provided that" and "notwithstanding" carry the law.
3. **The audience.** A confident wrong answer about rights costs a person with a disability more than a list of excerpts.

**Do not reopen this** without the H6 legal review and a new pre-declared gate. *(2026-10-25: H6 is now funded-phase
only, so this stays closed until then. H6-S is not a substitute for it here.)*

---

## Findings from the code (2026-10-22) that shape H9

| # | Fact | Consequence |
|---|---|---|
| G1 | `data/processed/gazette_arrangement.json` holds the Act's **58 clause titles** from the gazette Arrangement (e.g. `1: "Prohibition of discrimination and penalty."`, `3: "Right of access to public premises."`). | A deterministic, gazette-sourced vocabulary for suggestion labels. No text is invented: the title is the gazette's own words. After H8a, the Regulations add 172 more (their Arrangement, pp. 3–8). |
| G2 | `data/eval/conversations.json` has **23 conversations / 64 turns**, split `chat_dev` / `chat_test`, each turn with `expected` refs. | An **offline yardstick for suggestions**: did any suggestion point at the clause the user actually asked about next? Zero quota. `chat_test` is blind; it is read once, at the end. |
| G3 | `TurnPayload` (`src/chat.py:291`) is the stored turn; `replay_turn()` must never recompute. | Suggestions and key lines are computed **once** in `render_turn` and stored as new **defaulted** `TurnPayload` fields, which replay reads. Same pattern as the Phase C `help_payload` field. |
| G4 | Widget label or `key=` changes remount the widget and drop focus (`.claude/rules/ui.md`). | Suggestion buttons need stable keys of the form `sugg-<turn>-<i>`, native `st.button`, and a behavioural focus test. |
| G5 | `build_speech_text()` / `build_announcement()` (`app.py`) build read-aloud and the live-region text. | Both features must be **spoken** too, after the excerpts, or screen-reader users miss them. |
| G6 | H7 telemetry is counts-only and new fields need the owner first (invariant). | Measuring whether users *click* suggestions needs a new counts-only field (`via=suggestion`). **Owner decision**; H9a can ship without it. |
| G7 | The router is stateless and a clicked suggestion is just a typed question. | A suggestion click goes through the normal pipeline (router → `contextualise` → retrieval). No new answer path, so the refusal layers and citations apply unchanged. |

---

## H9a — suggested follow-up questions

**Branch** `phase11/h9a-suggest` from `main`. **Quota** zero. **Owner-only:** merge; the optional telemetry field (G6).
**Can start any time H8a is blocked** (e.g. waiting on H6). Never run it in the same branch as H8a.

### Design (fixed here, before measurement)
1. **Source of suggestions:** for a legal turn whose excerpts include Act clauses, candidates are:
   * the **neighbouring clauses within the same Part** of each retrieved Act clause (from the Arrangement; Parts as
     recorded in `act2018_v2_clauses.json`/the manifest);
   * **plus a fixed "next step" set:** the penalty clause (cl. 1 "…and penalty"), and the Commission/complaints clauses
     (read the exact numbers from the Arrangement, do not guess).
   * Exclude clauses already shown in this turn's excerpts.
   * Constitution and Factsheet are **not** suggestion sources in H9a (no curated title list).
2. **Wording:** a fixed template on the gazette title, e.g. `What does the Act say about <title, lower-cased, trailing
   "." removed>?`. The template is the only generated text, and it is asserted. No Pidgin templates in H9a.
3. **At most 3 suggestions per turn**, ordered by (same Part as the top Act excerpt, then clause number). Deterministic:
   the same turn always gives the same suggestions.
4. **Placement:** after the excerpts and the AI expander, under the heading "You might also ask". Helplines still lead.
   Not shown on help, greeting, clarify or refused turns.
5. **Click:** submits the suggestion text as the next user turn (via the existing `session_state["pending"]` path).

### Gates (all fixed before any number is seen)
1. **Self-consistency (the safety gate):** every templated question that *could* be suggested (one per Act clause, ≤ 58),
   asked on its own through the shipping path (`k=4/doc, top_n=12`, v2), must retrieve **its named clause** in the shown
   excerpts and must **not be refused**. A clause that fails is removed from the suggestable set, and the list of removed
   clauses is recorded. **Never suggest a question the system cannot answer.** Gate: ≥ 45 of 58 clauses remain suggestable;
   if fewer remain, H9a is declined (the suggestions would be too sparse to be worth the UI).
2. **Usefulness (dev):** on `chat_dev`, for each legal turn followed by a legal turn, a "hit" means some suggestion names a
   clause in the next turn's `expected` refs. Compare with a **random-neighbour baseline** (3 random clauses from the same
   Part, averaged over 100 seeds). Gate: hit rate ≥ 2× baseline **and** ≥ 0.20. Then `chat_test` is read **once** and
   reported, not gated.
3. **No regression:** `eval_chat` / `eval_heldout` stdout byte-identical (suggestions do not touch retrieval);
   `calibrate_refusal` 0/212; every suite green; axe matrix 0; a focus probe (Tab to the first suggestion, Enter, focus
   lands on the new turn's banner region or the chat input, never lost to `<body>`); read-aloud includes the suggestions.
4. **Replay:** a replayed turn shows the same suggestions without recomputing (assert, like `replay_turn`'s no-network
   assert).

**Do not:** suggest from model output; paraphrase a gazette title beyond the fixed template; show suggestions on refused
or help turns; change routing or retrieval.

---

## H9b — "key lines" (extractive, cited)

**Branch** `phase11/h9b-keylines` from `main`, after H9a ships. **Quota** zero. **Owner-only:** merge, and the decision
to ship before or after the H6 review. **Recommended (2026-10-25):** ship only after H6-S (`docs/phases/19_zero_cost_self_review.md`) and after the H7 week-1 read shows
excerpt-only answers rate poorly on "helpful". If they rate fine, H9b may not be worth its risk.

### Design (fixed here)
1. For each of the top **3** shown excerpts, pick **one** sentence by term overlap with `retrieval_query` (the same TF-IDF
   vocabulary as retrieval; no new model). Show it verbatim with the excerpt's own citation tag, labelled **"Quoted from
   [tag]"**, above the excerpt cards. It is never merged into prose.
2. **Sentence boundaries respect legal structure.** A sentence ending in a list lead-in (`—`, `-`, `:`, "shall—") brings
   its whole `(a)…(z)` list, or the excerpt is skipped. Never cut inside a sub-paragraph.
3. **Exception guard:** if the chunk contains `subject to|provided that|except|notwithstanding|unless` and the chosen
   sentence does not include that clause, **skip that excerpt's key line** rather than show a partial rule.
4. Not shown on refused, help, greeting or clarify turns. Stored on `TurnPayload` and replayed, like H9a.

### Gates (fixed in advance)
1. **On-target (dev + frozen-10):** for answerable questions, ≥ 70% of shown key lines come from a chunk whose ref is in
   `expected`, and ≥ 1 key line is on-target for ≥ 80% of questions.
2. **Exception guard:** 0 shown key lines that omit an exception present in their chunk (scripted check over dev +
   frozen-10 + test2 shown excerpts).
3. **Off-topic exposure (report, then decide):** on the five dev off-corpus questions H4 measured (landlord eviction,
   drink-driving penalty, trade mark, fertiliser/tomatoes, Android password; see the H4 box in
   `docs/phases/16_post_launch_roadmap.md`), never the unread blind `offtopic_h4.json`, report how many show key lines.
   Three of those five score full lexical coverage, so expect key lines to appear. **If any off-topic question would show a key line from a chunk the
   H6 reviewer would call irrelevant, H9b waits for a discriminative signal.** Do not add a display threshold on score;
   that is `MIN_SCORE` nudging by another name.
4. `test2` read once for gate 1 and reported. Suites, axe, focus, read-aloud as in H9a.
5. **Human gate:** the owner (plus an H6-S.3-style agent self-review; no paid reviewer, 2026-10-25) reads key lines for 15 dev questions and marks each
   "fair / misleading". 0 "misleading" to ship.

**Do not:** compose sentences; drop citation tags; show a key line without its excerpt below it; tune the selector on
`test2`.

---

## After H8a

When the Regulations enter the corpus, extend the H9a source to their Arrangement (172 titles; template "What do the
Accessibility Regulations say about …?") and **re-run H9a gate 1** for those titles. H9b needs no change beyond
re-running its gates on the new corpus.

## Owner decisions

1. Approve H9a (recommended) and whether H9b is queued at all.
2. Optional: allow a counts-only `via=suggestion` telemetry field, so suggestion use can be measured (G6).
3. Order relative to H8a: the recommendation is H9a while H8a waits on H6-S; H9b after H6-S + the H7 read (2026-10-25).

## Results

*(empty — no step started)*
