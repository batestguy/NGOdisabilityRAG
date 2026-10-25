# H8 — Corpus expansion and maintainability (planned 2026-10-22)

**Status: PLANNED. Docs only: no code, zero quota.** This expands the H8 stub in
`docs/phases/16_post_launch_roadmap.md` (H8a / H8b / H8c) into runnable steps. Each step has its own
branch, a gate written **in advance**, its quota cost, what only the owner can do, and a "do not" list.
A fresh session should be able to run any step from this file plus `CLAUDE.md` alone.

**Standing rule:** a push to `main` redeploys to real users on Render. That is the owner's call, every
time. Every H8 step ends at "PR open, CI green, reviewer passed" at most, unless the owner says otherwise
in that session.

---

## Findings that shape H8 (read from the code 2026-10-22, before any step was written)

The roadmap stub treated H8a as "add a `doc_id`, a citation scheme, rebuild, re-measure". Reading the
code shows a fourth document touches far more than that. **The three-document assumption is hard-coded
in at least ten places, and three of them change shipped behaviour or spend quota.**

| # | Where | What assumes three docs | Consequence for H8a |
|---|---|---|---|
| F1 | `src/rag.py:1075` (`ask()` docstring), `app.py:331` `offline_legal_hits(k=4)`, every harness (`eval_heldout.py:134`, `eval_chat.py`, `eval_phase06.py:329`, `calibrate_refusal.py`, `probe_gen_refusal.py:43`, `build_h6_review.py`) | **`top_n == 3 × k` is load-bearing** (E1b): at 3 docs × k=4 = 12 candidates and `top_n=12`, `select_top` never cuts. | With 4 docs, k=4 yields **16** candidates. Keeping `top_n=12` reintroduces the cross-doc cosine cut that **measured worse on all three sets** in E1. Moving to `top_n=16` raises the display ceiling by a third (an accessibility cost: more cards, longer read-aloud). Either way **every published number moves**. The budget is a measured arm, decided by the gate below, not by "keep it the same". |
| F2 | `src/rag.py:45` `PROMPT_VERSION`, `:756` `CHAT_PROMPT_VERSION`, `SYSTEM_PROMPT` rule 1 | Rule 1 lists exactly three tag shapes. | A new tag shape means **`cite-strict-v4` / `chat-cite-strict-v3`**. The Phase G evidence (judge 23/23, G4 0 drift, G6 0 refusals) was earned by the v3/v2 prompts, so **the AI expander's "recommendable" status lapses until a fresh G-style run. That costs quota** (see H8a.6). |
| F3 | `src/rag.py:822` `CITE_TAG_RE`, `:858` `verify_citations` `doc_of`, `scripts/test_phase05.py:76` `tag_re`, `src/chat.py:373` (tag shape for drift), `scripts/eval_phase06.py:168,197` (`DOC_OF` + prefix regex; missed at H8a.2, fixed after review) | Three tag regexes, three prefixes. | If a new-doc chunk reaches the LLM before these are extended, its tags are **invisible to `verify_citations`**, so a fabricated number there would pass silently. **These change in the same commit as the corpus, never later.** |
| F4 | `src/retrieve.py:109` `DOC_IDS`, `scripts/evalset.py:72` `DOC_IDS` (a **separate copy**; `chatset.py:71` imports it) | Two independent tuples. | Both change, and an assert should pin them equal. |
| F5 | `src/retrieve.py:747` `cite_tag()` | The only place tags are built (invariant). | The new scheme goes **only** here. Its prefix must not be a prefix of, or match, an existing one (`[Lagos s. 3]` vs `[Constitution s. 3]` is fine; a bare `[s. 3]` is not). |
| F6 | `src/rag.py:704-708` `build_corpus()` | Dict insertion order breaks ties. | **Append the new doc last.** Ties among the existing three then resolve exactly as now, so any number that moves does so because of the new doc's scores, not because of reordering. Recorded as a decision, not an accident. |
| F7 | `src/retrieve.py:399,418` | The OOV bridge is **one artifact at one path, loaded at import**, keyed on one corpus sha. | Rebuilding it for a 4-doc corpus makes `build_corpus("v2")` **hard-fail**, so v2 can no longer reproduce its published numbers from the same commit (the Phase D rule). H8a needs a **version-keyed bridge** (`oov_bridge_v3.json`, chosen by corpus version) before anything else. That is a code change with its own PORT CHECK (`ablate_oov_bridge.py`) still passing on v2. |
| F8 | `scripts/audit_corpus.py:151` `V2_CORPUS_SHA256` + per-doc shape integers | v2 pin. | Add a `V3_CORPUS_SHA256` and v3 shape rows. **Never edit the v2 pin.** |
| F9 | `MIN_SCORE = 0.10` (`src/retrieve.py`) | Calibrated on the three-doc index. | A fourth doc gives every query more chances to clear the floor. **Off-corpus false-answer can only rise.** `calibrate_refusal.py` re-runs; `MIN_SCORE` may move **down** on evidence, never up (its own gate 3). |
| F10 | H6 review pack (`docs/review/h6_review_sheet.*`, built from the shipping 3-doc display) | A lawyer is about to read 3-doc answers. | Do not ship H8a while the H6 review is out, or the review describes a system that no longer exists. **H8a ships after H6 returns, or H6 is re-generated.** *2026-10-25: H6 is replaced by the H6-S self-audit (`docs/phases/19_zero_cost_self_review.md`); the v3 sheet was regenerated at H8a.5 and stays ready for F1.* |

**Reading.** H8a is a corpus rebuild on the scale of Phase D, plus a prompt version bump, plus a quota
spend. It is not a data-entry task. H8b and H8c are low-risk and zero-quota. **Recommended order:
H8c → H8b → H8a.0 → (H7 week-1 read and H6 return) → H8a.1–H8a.7.**

---

## H8c — slim `CLAUDE.md`, `STATUS.md`, `HANDOFF.md` (first: cheapest, pays back every session)

**Why first.** `CLAUDE.md` is 369 lines and is loaded into every turn of every session; its "Working
conventions" bullet alone is a phase-by-phase history. `STATUS.md` is 75 lines but ~50K tokens (single
lines carrying whole phase reports). `HANDOFF.md` is 1,530 lines of stacked dated blocks. All three
cost context on every session and bury the current state.

**Branch** `phase11/h8c-docs`. **Quota** zero. **Owner-only:** the merge (docs-only merges still
redeploy).

1. Load the `claude-md-lifecycle` skill and follow it.
2. **`CLAUDE.md` ≤ ~200 lines**: environment, commands, architecture, invariants, quota rules, CSS
   gotchas, deploy rule. Dated phase history moves out (it already exists in the playbooks and the
   journal; move only what is not already there). Path-scoped detail may go to `.claude/rules/*.md`.
3. **`STATUS.md` = current state only**: one line per live capability, the current numbers
   (`baseline_phaseE_2026-09-24.txt` + H-step deltas), open items. History moves to
   `docs/history/status_history.md` verbatim (moved, not rewritten).
4. **`HANDOFF.md` = the latest end-of-session block + standing facts.** Older blocks move verbatim to
   `docs/history/handoff_history.md`.
5. **Invariant checklist (the gate).** Before deleting any line from `CLAUDE.md`, list every invariant,
   number and "do not" in the old file in `runs\h8c\invariants.txt`, and tick each one off against its new
   home (new `CLAUDE.md`, a rule file, a playbook, or the journal). **Zero unticked lines.**

**Exit gate:** `CLAUDE.md` ≤ 210 lines; checklist 100% ticked; every suite still passes (nothing reads
these files, but CI must stay green); reviewer confirms no invariant was dropped.

**Do not:** reword an invariant while moving it; drop a "do not re-implement" note about the declined
arms (E2a, E3a, F0, H4, H5a); delete history (it moves, it is never removed).

---

## H8b — move `app.py`'s render helpers into `src/ui_render.py`

**Why.** `app.py` is 1,748 lines. The render helpers (`render_routing_trap` 911, `render_greeting` 934,
`render_clarify` 939, `dedupe_excerpts` 977, `render_excerpts` 996, `render_plain_caption` 1063,
`render_context_note` 1070, `render_defects` 1085, `render_ai_expander` 1147, `render_legal` 1168,
`render_help_records` 1205, `render_helpful` 1295, `render_help` 1311, `render_voice_draft` 1402) are
shared by the live and replay paths and are the bulk of the file. Doing this **before** H8a means H8a's
UI step (a jurisdiction/status note per doc) lands in a smaller, clearer module.

**Branch** `phase11/h8b-split`. **Quota** zero. **Owner-only:** merge.

1. **Stay in `app.py`:** `run()`, `render_turn()`, `replay_turn()`, `render_history()`,
   `render_helpline_banner()`, `offline_legal_hits()`, `accessibility_css()`, `A11Y_BRIDGE_JS`. These are
   what `test_phase05.py`'s source-text asserts read (banner adjacency inside `render_turn`'s body; call
   sites at 4-space top level). Leaving them means those asserts need no change.
2. Move the helpers listed above to `src/ui_render.py`, imported flat (`import ui_render`) like the other
   `src/` modules. Keep `app.dedupe_excerpts` etc. reachable as `app.<name>` re-exports where a test or
   script calls them (grep `app\.` across `scripts/` first and list every hit).
3. `import app` and `import ui_render` must stay import-safe (no Streamlit call at module level).
4. If any source-text assert has to change, change it **in the same commit**, with a comment saying why
   and what it still guarantees.

**Exit gate:** `test_phase05` passes with **the same assert count** (or every change explained);
`test_phase03/04/09_ops`, `audit_corpus`, `import app` pass; `eval_heldout.py` and `eval_chat.py` stdout
**byte-identical** to the pre-split run except timestamps; the axe matrix
(`tools/a11y_audit/audit.mjs`) shows the same counts; a keyboard focus check on the route radio and the
skip link (the 2026-10-21 lesson: test behaviour, not presence). Reviewer passes.

**Do not:** change any rendered text, order, key or widget while moving (a moved widget whose `key=`
changes remounts and loses focus); combine this with the Streamlit 1.66 bump (do that in its own branch,
after or before, never together).

---

## H8a — new legal sources

### H8a.0 — source dossier (docs only; can start now)

**Branch** `phase11/h8a-sources` (docs). **Quota** zero. **Owner-only:** the licence sign-off and the
choice of document.

For each candidate, write one section in `docs/h8a_source_dossier.md`: official source URL, publisher,
date, gazette citation if any, file hash once downloaded, text layer or scan, **licence/reuse position
in writing**, legal status (binding where, on whom), and the citation unit (section / regulation /
article). Nothing is parsed or indexed in this step.

**Candidates, as found 2026-10-22 (none verified yet; this list is a starting point, not a decision):**

| Candidate | Status found | Why | Open questions |
|---|---|---|---|
| **Persons with Disabilities (Accessibility) Regulations, 2023** (NCPWD) | Reported as made by the NCPWD under the 2018 Act, with a 2024 RoLAC-supported rollout workshop (idea.int). No official full text found by search. | Federal, made under the Act already in the corpus, directly about the accessibility duties users ask about. **First choice if an official text exists.** | Official gazette copy? Which Act clause empowers it (verify against `act2018_v2_clauses.json`, do not trust the secondary source's numbering)? Licence. |
| **UN Convention on the Rights of Persons with Disabilities** | UN treaty text is freely available from the UN/OHCHR. | Stable, authoritative, article-structured, a clean citation unit. | **Not directly enforceable in Nigeria unless domesticated** (Constitution s. 12(1), which is already in the corpus). Every answer citing it needs that note, and ratification facts must be verified from the UN treaty collection, not from memory. Risk: users read treaty rights as enforceable rights. |
| **Lagos State Special People's Law, 2011** | No free official text found. Law Nigeria sells a PDF (₦2,000); `data/raw/SOURCES.md` already says not to pay that site. Leads: the Lagos State Office for Disability Affairs (LASODA), the Lagos House of Assembly. | Lagos is Nigeria's largest state by population, and the law created a dedicated office (LASODA). | State law: binds only in Lagos, so every answer needs a jurisdiction note, and the router has no "where are you" signal for legal turns (only help slots). A free official source must be found first. |
| NCPWD enforcement guideline | Reported in the press (NAN). | Practical. | A guideline, not law. Lowest priority; probably out of scope for a *legal* corpus. |
| Other states' disability laws | Not surveyed. | — | Defer until one state law has been done end to end. |

**Exit gate:** the owner picks **one** document (one per round; never two at once, or the measurement
cannot attribute a change) and signs the licence line in the dossier.

**Do not:** download from a paid or unofficial source; ingest anything in this step; trust a secondary
source's section numbers (the Phase D lesson: the authoritative copy wins).

### H8a.1 — author the new doc's eval questions BEFORE parsing it

**Branch** `phase11/h8a-<doc>` (all later steps). **Quota** zero.

* Write ~20 questions about the new document from its **official text**, split before any measurement:
  **dev (~8)** and a blind **test3 (~12)**, committed in a separate commit before any code exists (the
  E5.2 `test2` procedure). Include lay-register and Pidgin phrasings (the registers G6 and H5a probed).
* Write ~6 **jurisdiction/status probes** (for a state law: a question from outside the state; for the
  CRPD: "can I sue under the CRPD?") whose correct answer needs the status note.
* Expected refs use the new doc's citation unit and are ground truth read from the document, never from
  an answer.

### H8a.2 — parse and pin, behind a new corpus version

* A new `doc_id` (e.g. `accessregs2023`, `crpd2006`, `lagos2011`) and its loader in `src/rag.py`.
  Scanned text follows the Phase D route (OCR in the dev env, a human-signed corrections file for any
  fix, never "cleaned up" by hand).
* **`CORPUS_VERSION` stays `"v2"`.** The new doc enters only under `build_corpus("v3")`, appended **last**
  (F6). v2 must reproduce every published number from the same commit.
* **Version-keyed OOV bridge first (F7):** load the bridge by corpus version; build
  `oov_bridge_v3.json`; `ablate_oov_bridge.py`'s PORT CHECK must still pass on v2 unchanged.
* `audit_corpus.py`: `V3_CORPUS_SHA256` + v3 shape rows; v2 pin untouched (F8).
* `DOC_IDS` in both places + an assert they are equal (F4); `cite_tag()` (F5); `CITE_TAG_RE`,
  `verify_citations`' `doc_of`, `test_phase05.tag_re`, `chat.py` drift shape (F3), all in this commit.

### H8a.3 — measure (zero quota). Gate fixed here, before any number is seen

**Arms:** `v2 k=4 top_n=12` (control, the shipping system) · `v3 k=4 top_n=12` · `v3 k=4 top_n=16`.
Dev and the existing selection sets are read first; **`test2` and `test3` are read once, at the end,
for the chosen arm only.**

**Ship gate (all must hold for one v3 arm, else H8a is declined like E2a/E3a/F0):**
1. **No regression on existing law:** strict recall on frozen-10, dev, `test2` each **≥ control**, and
   **no existing question loses its correct chunk** (per-question diff, not just the mean). The new doc
   must not displace the Act or the Constitution.
2. **False refusals 0** on every set (frozen-10, dev, test2, test3).
3. **New-doc reach:** strict recall on the new doc's dev ≥ 0.60, then test3 reported once.
4. **Refusal calibration:** `calibrate_refusal.py` 0 disagreements. If its probe count changes (new
   corpus terms), record why. Off-corpus false-answer rate reported against control. `MIN_SCORE`
   may only move down.
5. **Status probes:** every jurisdiction/status probe retrieves the status source (e.g. Constitution
   s. 12 for the CRPD) in its top 12/16, so the note has evidence to stand on.
6. If both v3 arms pass, prefer `top_n=12` (smaller display); `top_n=16` only if 12 fails gate 1.

**Do not:** read `test` (its cleanliness is an open owner decision as of 2026-10-21); tune anything after
reading `test2`/`test3`; change `SYNONYMS` (it moves `calibrate_refusal` off its 212 probes).

### H8a-R — reopened measurement (owner reopened H8a on 2026-10-23). Gate fixed here, before any number

H8a.3 declined both v3 arms. v3-16 held existing law exactly but failed reach (0.583) and status evidence (G5). A rank
diagnostic on the **already-read** dev set split the misses into two kinds: just below the k=4 cut (ranks 4–9), and
vocabulary gap (ranks 17–30, scores ≤ 0.04). Because these ideas came from reading dev, selection moves to a **fresh
`accessregs-dev2`** (10 q, `a41606b`, committed before any arm existed). `accessregs-dev` is reported, never gated.
`test2` and `test3` are still unread.

**Arms** (MIN_SCORE unchanged; `scripts/eval_h8aR.py`):
* `control` v2 k=4 top_n=12.
* `R-a` v3 k=4 top_n=16 plus the fixed status note.
* `R-b` = R-a, but the Regulations index uses k=6 and top_n=18 (`PerDocRetriever.query(k_by_doc=)`, unused by any
  shipping caller). It is 18 candidates against 18 slots, so there is no cut.
* The vocabulary gap gets **no** lever: that is the E2/E3/F0 family, and `SYNONYMS` stays frozen.

**Status note.** `rag.DOC_STATUS_NOTES["accessregs2023"]` is fixed, hand-verified text (S.I. 51; made under s. 56
[Act cl. 56]; commenced 22 May 2023; administrative penalties [Regs reg. 168]; sealing [Regs reg. 169]; complaint without
prejudice to court [Act cl. 8]). It renders in H8a.4, and the H6 legal reviewer reads it before any ship.

**Gate:**
* **G1–G4 are unchanged from H8a.3.** G2 adds dev2. G3 is now ≥ 0.60 on **dev2**.
* **G5′ replaces G5:** the note states the five facts; every tag in it matches `CITE_TAG_RE` and names a ref present in v3;
  every status probe is answered. Status-probe recall is **reported, no longer gated**. This change is deliberate and is
  made before any reopened number, because the note now carries the status facts.
* **G6:** prefer R-a; take R-b only if R-a fails nothing but G3 and R-b passes everything.
* The blind stage (test2 + test3) runs once, for the chosen arm only, using the same marker file as H8a.3.

**Display cost of R-b:** up to 18 cards instead of 12. `INLINE_EXCERPTS` stays 3, so the fold grows. Record it if R-b
wins.

### H8a.4 — UI: per-document status note (zero quota)

* Each excerpt card from the new doc carries a short plain-language status line (e.g. "Lagos State law:
  applies in Lagos only", or "International treaty: not directly enforceable in Nigerian courts unless
  made law by the National Assembly [Constitution s. 12]"). The note is fixed text tied to the `doc_id`,
  never generated.
* The read-aloud speaks the note with the card. Helplines still lead every turn.
* `test_phase05` asserts the note renders for that `doc_id` and nowhere else; axe matrix and keyboard check
  re-run (the card count may rise if `top_n=16` won).

### H8a.5 — offline cut-over (zero quota)

Flip `CORPUS_VERSION` to `"v3"`, re-run every suite and harness, write
`scripts/baseline_v3_<date>.txt`. **Until H8a.6 passes, new-doc chunks are excluded from the LLM context**
(the offline excerpt path shows them; the opt-in AI expander does not see them), so the G-validated
prompt is never asked to cite a tag shape it was not evaluated on.

### H8a.6 — prompt v4 and a fresh generation check (QUOTA)

* `cite-strict-v4` / `chat-cite-strict-v3`: rule 1 gains the new tag shape, nothing else changes.
* Quota plan written **before the first call**: G2-style 12 + G6-style 10 + ~8 new-doc questions ≈ 30
  calls, which fits one day across both pools (40/day) only if nothing else spends that day. Check
  `HANDOFF.md`'s day spend first. Never `--failover` on these runs. Never fake a row.
* **Gate:** 0 unretrieved tags, 0 fabricated tags, 0 refusals on answerable questions, the status note's
  fact present in every answer citing the new doc. Then the LLM-context exclusion from H8a.5 is lifted.

### H8a.7 — merge (owner)

Only after **H6-S** has passed (2026-10-25: it replaces "H6 returned"; `docs/phases/19_zero_cost_self_review.md`). Reviewer pass on the whole branch, CI green,
then the owner's word. Live smoke: helplines first, one new-doc question shows its status note, one old
question shows the same tags as the local measurement.

---

## Owner decisions this playbook needs

1. Approve the order H8c → H8b → H8a.
2. H8a.0: pick one document and sign its licence line.
3. ~~Whether H8a waits for the H6 review to return or H6 is re-generated on v3.~~ Decided 2026-10-25: neither. H6-S
   gates it, and H6 waits for funding (`docs/phases/19_zero_cost_self_review.md`).
4. The quota days for H8a.6.

## Results

> **H8a.5 — 2026-10-23, DONE (zero quota; executor, then reviewer 2026-10-25: "ship to next step", nothing blocking).**
> `5595763`, `09e38c1`, `8d56ba0`, `aeb317f` + a review-fix commit. `CORPUS_VERSION = "v3"`, budget 16; v3 baseline
> `scripts/baseline_v3_2026-10-23.txt` (now with an ERRATA block); H6 pack regenerated on v3, v2 copy byte-identical.
> * **The reviewer re-ran everything** (zero network): 03/04/09_ops ALL PASS, 05 193/193, audit v3/v2/v1 PASS, calibrate
>   0/212, bench PASS, `eval_heldout --no-test` = baseline, v2 outputs identical to a `git archive` of `5595763`,
>   `eval_phase06` digests reproduce, PORT CHECK 72/72.
> * **Review fixes:**
>   * "not loaded" was too strong: `test`/`chat_test` rows are parsed (schema only), then dropped before any scoring.
>     The scripts and the baseline errata now say so.
>   * "Existing law identical" holds **at the shipping budget**. The recall_strict@k curve falls on v3 (frozen-10
>     k=10 0.684 → 0.636).
>   * The H6 sheet said "three documents"; it now says four (one line).
>   * CI now runs `audit_corpus --corpus=v1`, so the v1 tripwire actually runs.
>   * The stale note comment in `src/rag.py` now points to H6-S.
> * **Open, user-visible, undiagnosed:** on v3 the nonsense probe OFF12 is *answered* (Constitution s. 44, Regs reg. 4),
>   and junk like "sourdough bread" now ranks Regs regs. 118/57 at 0.34. `test_phase05`
>   `off12-v3-characterised-answered` pins the current state so it cannot change silently. **Next diagnostic (zero
>   quota):** which v3 OOV-bridge terms fire. Never raise `MIN_SCORE` for it.
> * After the fixes: 05 **194/194**, 03/04/09_ops ALL PASS, audit v3/v1 PASS, `eval_heldout --no-test` frozen-10 0.734 PASS.

> **H8a.4 — 2026-10-23, DONE (zero quota; executor, then reviewer: "ship to next step"). `fb6ad40` + a review-fix commit.**
> Under v2 everything is byte-identical: fingerprint, `eval_h8aR` dev stage, calibrate 0/212, all suites. `test_phase05`
> went 181 → 192 and `test_phase09_ops` 81 → 95.
> * **Budget:** `rag.TOP_N_BY_VERSION` = {v1: 12, v2: 12, v3: 16} with k = 4, and `top_n == k × n_docs` asserted.
>   `rag.ask` / `app.offline_legal_hits` default to the budget of the retriever's own docs.
>   * Harnesses that pin 12 were left alone and must be re-run at H8a.5: `eval_heldout`, `eval_chat`, `ablate_phase08`,
>     `ablate_oov_bridge`, `eval_phase06`, `judge_phase06`, `probe_gen_refusal`.
>   * `probe_gen_refusal` must also apply `llm_context_hits`.
> * **LLM exclusion:** `rag.LLM_EXCLUDED_DOCS = {"accessregs2023"}` through `llm_context_hits()`, applied to the prompt,
>   `verify_citations`, chat, failover and `_run_ai_turn`. The status note never reaches a prompt.
>   * When only Regs hits remain, the turn makes no model call; it stays pending with an `llm_error`, never faked.
>   * The reviewer found no leak path (history carries no excerpts; the cache key is the Regs-free prompt).
>   * After review, the AI expander now **says** it does not use the Regs excerpts. This is a caption with a behavioural
>     test, and a no-op on v2.
> * **Status note:**
>   * It renders once per turn, immediately before the first `accessregs2023` card, inline or in the fold, through the
>     shared helper, so live and replay are identical.
>   * **Deviation from "on each card" (decided):** the note is about 110 words, and repeating it on up to 4 cards would
>     burden a screen reader.
>   * The displayed text is verbatim ("N 500,000"); read-aloud speaks it once at the same point with "500,000 naira".
> * **Browser check on a local temporary v3** (reverted, never committed):
>   * axe matrix 0 violations over 33 scans;
>   * keyboard stops the same as v2, and the note adds no tab stop;
>   * focus returns to the chat input;
>   * screenshots are in `runs\h8a4\note_check_v3\`.
>
>   The note inside the fold was unit-tested only.
> * **Product finding, for H6:** on v3, 36 of 42 dev/frozen turns retrieve a Regs card, so the note shows on about 86% of
>   turns. It is visible without a click on about 40%, and read-aloud speaks it on about 86%.
>   * Even an employment question puts a Regs card at the top, which is a retrieval-precision matter.
>   * The reviewer recommends keeping the note next to the card as built, and asking H6 explicitly: is a 110-word note
>     acceptable on most turns, or is a short lead plus a folded full text wanted?

> **H8a-R — 2026-10-23, SHIP GATE MET for arm R-a (zero quota; reviewer: SOUND-WITH-CAVEATS, nothing blocking).**
> The order is in git: dev2 `a41606b`, then gate + harness `95bc165`, then the dev stage, then the one blind read.
> Outputs: `scripts/h8aR_dev_stage_2026-10-23.txt`, `scripts/h8aR_blind_2026-10-23.txt`. The marker `runs\h8a3\BLIND_READ`
> now blocks a second read.
>
> | recall_strict | control (v2, 12) | R-a (v3, 16) | R-b (v3, 16 + Regs k=6) |
> |---|---|---|---|
> | frozen-10 / dev | 0.734 / 0.613 | 0.734 / 0.613 | 0.734 / 0.613 |
> | accessregs-dev2 (fresh, n=10, **gated**) | 0.000 | 0.800 | 0.800 |
> | accessregs-dev (read at H8a.3, reported) | 0.042 | 0.583 | 0.625 |
> | status (reported) | 0.100 | 0.400 | 0.400 |
> | **test2** (blind comparator) | 0.629 | **0.629** | — |
> | **test3** (blind, n=12, reported) | — | **0.875** | — |
>
> **How to read this.**
> * **R-a is the same retrieval as the declined v3-16.** Nothing about retrieval improved; R-b's extra Regs depth added
>   nothing on dev2, so G6 took R-a. Two things changed between the decline and the pass:
>   * The reach sample moved to a fresh set: dev2 scored 8/10 (misses reg. 30 and reg. 83, both vocabulary gap).
>   * The status gate was **substituted**. G5 required status-probe retrieval, and R-a had failed it. G5′ checks a fixed
>     note instead. The substitution was written before any dev2 or blind number, but **after** the H8a.3 numbers were
>     seen, and status recall is unchanged at 0.400. Read G5′ as a lint (facts, tags, no refusals), not a retrieval test.
>     A user asking about penalties may see the note cite reg. 168 with no reg. 168 card shown (AR_S06).
> * **Reach figures to quote together:** dev2 0.800 (n=10); dev + dev2 pooled ≈ 0.70 (n=18); **test3 0.875 (n=12, blind)**.
>   test3 is the strongest evidence.
> * **No regression on existing law:** frozen-10, dev and test2 are identical to control, no question moved, and there are
>   0 false refusals on every set. Correction to earlier wording: `test2` was **not** "unread"; it was read in E5.3. Here
>   it served only as a no-regression comparator, never for selection. test3 has now been spent.
> * **Off-corpus false answers: 13 → 14 of 17**, as F9 predicted. The new one is OFF12 "quantum teleportation zebra
>   unleaded gasoline": under v3 it surfaces Constitution s. 44 at 0.135 and reg. 4 at 0.101, where control refuses it.
>   Not diagnosed; the v3-keyed bridge is the suspect. Reported, not gated.
> * The blind-stage string "SHIP GATE MET" in `eval_h8aR.py` covers only G1/G2 on the blind sets. **R-a is not
>   shippable yet** (see below).
>
> **Status note (`rag.DOC_STATUS_NOTES`).** All its numbers and citations were verified against the gazette (p. 9, regs.
> 168–169) and the Act (cl. 8, 56). It was reworded after review to be more conservative: no imposer is named for
> reg. 168, the relevant authority is included for reg. 169, and "regardless of" any Act penalty is stated. **It needs H6
> legal sign-off before it renders.** Open for H6: the commencement date (22 May 2023) precedes gazette publication
> (7 July 2023). Read-aloud must say "naira" for "N".
>
> **Before R-a can ship (H8a.4 → H8a.7):**
> * **Budget:** `rag.ask` / `app.offline_legal_hits` → top_n=16 for v3, keeping `top_n == Σk`. Re-run every harness that
>   hard-codes 12, then write a v3 baseline file.
> * **Render the note** on `accessregs2023` cards only, in the shared render helper. `test_phase05` asserts it renders
>   for that doc and nowhere else. Re-run the axe and keyboard checks.
> * **Read-aloud:** say "naira", and note the 16-card speech length.
> * **LLM context:** exclude Regs chunks and the note from the prompt and from `verify_citations` until H8a.6 (quota).
> * **Code cleanup:** decide whether `k_by_doc` (R-b only) is removed or kept as documented measurement-only code.
> * **Legal review (F10):** merge waits for H6, which must also read the note. *(2026-10-25: now H6-S, playbook 19.)* Then `CORPUS_VERSION = "v3"` (H8a.5).

> **H8a.3 — 2026-10-23, DECLINED at the dev stage (zero quota).** The harness `scripts/eval_h8a3.py` (gates G1–G6
> copied from this playbook) was committed as `9345a86` **before** any v3 number existed. Its `--self-test` proves G3/G5
> fire. Output: `scripts/h8a3_dev_stage_2026-10-23.txt`.
>
> | recall_strict | control (v2, 12) | v3-12 | v3-16 |
> |---|---|---|---|
> | frozen-10 | 0.734 | 0.695 | 0.734 |
> | dev | 0.613 | 0.593 | 0.613 |
> | accessregs-dev | 0.042 | 0.542 | 0.583 |
> | status | 0.100 | 0.400 | 0.400 |
>
> * **v3-12 fails G1** (the F1 displacement): frozen-10 and dev fall, and Q2 (Factsheet 7), Q8 (Act cl. 7) and H2
>   (Factsheet 16) lose a chunk control had. It also fails G3 and G5.
> * **v3-16 passes G1, G2 and G4**: existing law is identical to control, with 0 lost pairs, 0 false refusals on any dev
>   set, and refusal invariance 0/100 probes. It **fails G3** (0.583 < 0.60) and **G5**.
>   * G3: AR_D02 (reg. 151), D07 (reg. 2) and D08 (reg. 59) get 0; D03 misses reg. 112.
>   * G5: AR_S01 misses Act cl. 56 (control misses it too); S05 misses Act cl. 6 + reg. 165; S06 misses Act cl. 8 +
>     reg. 168. S02, S03 and S04 pass; S04 passes because the `[Regs general]` preamble chunk is shown.
> * **G6 choice: none. The blind stage was NOT run, so `test2` and `test3` stay unread.** The gate is not loosened after
>   the fact. Per this playbook, H8a is declined as built. Branch `phase11/h8a-accessregs` is its archive and is never
>   merged. The live system is untouched.
> * G4's probe count is 100, not calibrate_refusal's 106: the `test` rows are left out (not to be read) and the 14
>   accessregs-dev + status rows are added. Off-corpus answered: control 13/17, both v3 arms 14/17 (F9, as predicted).
>   `MIN_SCORE` is unchanged.
> * **What a reopening would need** (owner's call; a new reason and a new gate written before any number, dev only):
>   v3-16's failures are reach and status evidence, not displacement. The candidates are (a) H8a.4's fixed status note
>   carrying the status facts (enabling power, commencement, administrative-only penalties) so G5 no longer depends on
>   retrieval, and (b) a reach lever for the Regs, e.g. title-weighted headers for short regulations. Either is a new arm
>   with a fresh pre-declared gate. Since dev has now been read once, it is no longer a clean selection set for a v3
>   rescue; an honest reopening authors a fresh `accessregs-dev2` before measuring.

> **H8a.2 — 2026-10-23, DONE (zero quota; reviewer: ship to H8a.3).** Branch `phase11/h8a-accessregs`: `44f5a7b` (F7),
> `0ef9b9e` (parser), `fbfe5a2` (v3 wiring), plus a review-fix commit. `CORPUS_VERSION` is still `"v2"`.
> * **F7.** The bridge is chosen by corpus content: `PerDocRetriever` picks the registered artifact whose `corpus_sha256`
>   matches its chunk stream, and otherwise falls back to v2's, as v1 always did. v1/v2 keep the exact one-argument
>   `expand_query(q)` call, so the ablation harnesses that monkeypatch it still work on v2. **On v3 they raise a TypeError
>   (loudly), and `ablate_handmap`/`ablate_surface` call `oov_bridge_terms(q)` bridge-less, so do not point them at v3.**
>   v2 is proven bit-identical:
>   * a 54-question retrieval fingerprint is byte-identical on base, HEAD and the pre-change capture (the reviewer reran it
>     from `git archive de8c1f8`);
>   * `oov_bridge.json` is unchanged;
>   * the default `audit_corpus` output is identical;
>   * `calibrate_refusal` 0/212; PORT CHECK 72/72.
> * **Parser** `scripts/parse_accessregs.py` → `data/processed/accessregs2023_regs.json`. It is deterministic and asserts
>   the source PDF's sha.
>   * The margin column is split by font size (notes 8 pt, body 10.4–11 pt) and by x band. Notes are assigned one-to-one
>     to the nearest regulation start within 3 pt above to 15 pt below.
>   * **172/172 located.** The only flag is reg. 133 `ARRANGEMENT_NUMBER_MISMATCH`.
>   * Reviewer's independent check: the font-split token multisets of pp. 9–68 equal the artifact exactly, in both
>     directions (23,595 body / 568 note tokens). 171/172 titles equal the Arrangement's.
>   * The text is verbatim, with no de-hyphenation (same policy as `parse_act_v2`). Three headers keep a split word
>     (regs. 29, 87, 167); they stay verbatim unless H8a.3 misses trace back to them, and any fix goes through a signed
>     corrections file.
> * **Corpus v3** is v2 unchanged plus `accessregs2023` appended last:
>   * 221 chunks (1 `general` preamble first, then 220 regulation chunks; 40 regulations span more than one chunk);
>   * tags `[Regs reg. N]` / `[Regs general]`;
>   * `V3_CORPUS_SHA256 = f13b9678…3513`;
>   * `oov_bridge_v3.json` with 14,787 keys.
>   * F3/F4/F5 were done in the same commit, and `test_phase05` went 179 → 181. The reviewer then found a **fourth copy of
>     the prefix scheme in `eval_phase06.py`** (`DOC_OF`, prefix regex) that would have crashed a v3 LLM row; it is now
>     fixed and added to the F3 row.
>   * The `audit_corpus --corpus=v3` gate fails on each of the 172 single-regulation removals, on a missing preamble and on
>     a moved preamble.
> * **Watch in H8a.3** (the reviewer's displacement preview, not a gate; no recall computed):
>   * Of 40 existing-law dev/frozen questions under v3 at k=4/top_n=12, 39 show a Regs hit and 38 lose a v2 hit from the
>     top 12, which is F1/F9 displacement.
>   * `[Regs general]`, the preamble chunk that carries the full Act title, appears for 11 of 40.
>   * Gate 1's per-question diff decides. A `top_n=16` arm is already in the plan.
> * Also noted: sub-chunk splits sometimes cut mid-word (the same `recursive_split` idiom as the Act), which affects
>   display only. `audit_corpus --corpus=v3` is not yet in CI (optional).

> **H8a.1 — 2026-10-23, EXIT GATE MET.** `data/eval/questions_accessregs.json` was committed alone as `af3129e` on branch
> `phase11/h8a-accessregs`, before any parser code (zero quota). It holds 26 questions: **dev 8** (`accessregs-dev`),
> **blind `test3` 12**, and **status 6**. Classes cover direct, vocab-mismatch, odd-wording (Pidgin) and cross-document, plus
> `status`. The register mix is 5 Pidgin, the rest plain or lay. Expected refs are regulation numbers read from the gazette
> text extracted to `runs\h8a1\` (gitignored), and every quoted phrase was checked against that text.
> **Do not read `test3` again.**
> Findings for H8a.2 onward:
> * **Commencement resolved.** p. 9 prints "[22nd day of May, 2023]" beside the marginal note "Commencement.". That date is
>   the commencement, so the dossier's "not verified" line is answered (amendments are still unverified).
> * **The enacting formula is unnumbered** (power under Act s. 56, made by the Governing Council). AR_S01, S03 and S04 need it
>   as status-note evidence. H8a.2 must decide how it is ingested or carried. **AR_S04 has empty `expected`**, so the
>   harness must handle that without a divide-by-zero, and `verify_ground_truth` must skip it.
> * **Arrangement typo:** the manifest (p. 6) lists "132. Braille", but the body numbers it **133**. A manifest-anchored parser
>   must not trust the Arrangement number there.
> * **Two near-identical certificates:** the *National Accessibility* Compliance Certificate (reg. 165(4), 5 years, for
>   buildings) and the *National Disability* Compliance Certificate (reg. 166, 1 year, for persons/bidders). They are a
>   designed confusion trap (AR_D06, AR_T06).
> * The gazette prints the naira sign as "N" ("N 500,000"). Copy it verbatim and do not normalise it.

> **H8a.0 — 2026-10-22, EXIT GATE MET.** The owner chose **A (Accessibility Regulations 2023)** and signed the reuse line
> in session ("go with the Accessibility Regulations, I sign off"). The PDF is filed at
> `data/raw/accessibility_regulations_2023_gazette_FGP.pdf` (sha256 matches) with a `SOURCES.md` row. The owner then
> confirmed the signature also covers the live Act gazette ("yes it covers the Act gazette too"). **Next: H8a.1.** Dossier:
> `docs/h8a_source_dossier.md` (branch `phase11/h8a-sources`; zero quota).
> * **A, Accessibility Regulations 2023 (recommended).** S.I. No. 51 of 2023, Gazette No. 122 Vol. 110 (7 July 2023), from
>   https://ncpwd.gov.ng/pdfs/44document.pdf (the same NCPWD folder as the Act gazette). 173 pp, sha256 `04bb8bec…8b05`.
>   Born-digital text: 172 regulations on pp. 9–68; the First Schedule is figures (images, to exclude). Made under s. 56 of
>   the Act, which is cross-checked against `act2018_v2_clauses.json` cl. 56.
> * **B, CRPD.** Ratified 24 Sep 2010 (UN Treaty Collection). un.org's terms bar redistribution and derivative works, so
>   it needs a legal answer, and it is not domestically enforceable (Constitution s. 12).
> * **C, Lagos law 2011.** No free official text found. Blocked on LASODA.
> * **Found on the way:** the project has never recorded a reuse position for the Act gazette already in the corpus.
>   The owner sign-off is drafted to cover both.
> * Also 2026-10-22: **PR #20 (H8 playbook + H8c + H8b) MERGED on the owner's word → `main` = `94db479`, deployed** (Render
>   `dep-dbcrr8k9v7es73bse4u0`, live 07:41 UTC). CI green on both runs. The live smoke `live_smoke_a11y.mjs` (asks no question,
>   so no telemetry) PASSED: helplines on the page, slider has a single name, landmarks present, skip link on top and focusing
>   H1, route radio keeps focus, 0 page errors. `/_stcore/health` returns `ok`.

> **H8c — 2026-10-22, EXIT GATE MET (branch `phase11/h8c-docs`, not merged; zero quota).**
> * `CLAUDE.md` 369 → **210 lines**. Retrieval/corpus/eval detail is in `.claude/rules/retrieval.md` (paths: `src/`
>   retrieval modules, `data/processed/**`, `data/eval/**`, `scripts/**/*.py`). UI/CSS/a11y detail is in
>   `.claude/rules/ui.md` (paths: `app.py`, `.streamlit/**`, `static/**`, `tools/a11y_audit/**`). Root keeps a stub per
>   file that names the danger. The original is verbatim at `docs/history/claude_md_2026-10-22.md`.
> * `STATUS.md` → current state only (38 lines); the old lines are verbatim in `docs/history/status_history.md`.
> * `HANDOFF.md` 1,530 → 78 lines: the latest blocks plus a "Standing facts (still true)" section; original line 62
>   onward is verbatim in `docs/history/handoff_history.md`.
> * **Invariant checklist:** 76 phrases (`runs\h8c\invariants.txt`), **76/76** present in root + rules.
> * **Reviewer: SHIP WITH CAVEATS, no blocking findings.** It confirmed the archives are byte-verbatim, the hashes and
>   `main` are right, and the suites reproduce. Its fixes were applied:
>   * "two" quota-flag scripts → three (`probe_gen_refusal.py`);
>   * the `SYNONYMS` rule restored to "not casually … requires a fresh calibration" (it had hardened to "frozen");
>   * `MIN_SCORE` "never up" now attributed to its source (the `src/retrieve.py` calibration comment and
>     `calibrate_refusal` gate 3) instead of reading as a new invariant;
>   * `--failover` scoped back to generation/judge runs, with the reason;
>   * call-count anchors and the answer-cache rule restored to the quota section;
>   * NVDA kill hazard and the `offline_legal_hits` ↔ `ask()` parity rule moved to `ui.md`; the ref-based citation-check
>     crash trap moved to `retrieval.md`;
>   * the `verify_ngo_sources.mjs` pointer added to the verified-contacts invariant;
>   * E4a no longer miscounted as a failure;
>   * this playbook's history paths corrected.
> * Not done by design: `/context` verification that the rules files defer. That needs a fresh session, so the next
>   session should run `/context` once and confirm neither rules file loads at startup.
> * Suites: `test_phase03` 24/24 + 16/16 · `test_phase04` · `test_phase05` 179/179 · `test_phase09_ops` · `import app`,
>   all PASS (nothing reads these files).

> **H8b — 2026-10-22, EXIT GATE MET (branch `phase11/h8b-split`, not merged; zero quota). Reviewer pending.**
> * **Moved to `src/ui_render.py`** (verbatim, 437 lines): `render_routing_trap` (+ `_requeue_last`, `_switch_label`),
>   `render_greeting` + `GREETING_TEXT`, `render_clarify`, `dedupe_excerpts`, `render_excerpts` (+ `_render_excerpt`,
>   `INLINE_EXCERPTS`), `render_plain_caption` (+ `_multi_turn`, `_prompt_id`), `render_context_note`, `render_defects`,
>   `render_help_records` (+ `NGO_ANY_TYPE`, `NGO_ANY_STATE`, `NGO_SORTS`), `render_helpful` (+ `_helpful_changed`,
>   `HELPFUL_PRIVACY_NOTE`), `render_voice_draft` (+ `try_voice_input`, `_import_mic_recorder`). `app.py` re-exports
>   every moved name, so `app.<name>` and `inspect.getsource(app.<name>)` still work. `ui_render` never imports `app`.
> * **Deviation: three listed helpers stayed in `app.py`**, because each computes as well as renders and calls app-level
>   state: `render_legal` (`load_retriever`, `offline_legal_hits`), `render_help` (`load_ngo_df`, `help_display`,
>   `help_directory`; `test_phase05` monkeypatches `app.help_display`), and `render_ai_expander` (its button calls
>   `_run_ai_turn`, which needs `answer_legal`, `load_retriever` and `quota_log_record`). Moving them would need a
>   callback or an `import app`, which is a design change and not a move.
> * One expression changed: `_import_mic_recorder`'s src entry is now `Path(__file__).resolve().parent` (the file is
>   inside `src/`). It resolves to the same directory; `mic-import-keeps-repo-chunk` passes.
> * `_st`: `ui_render` has its own `_st()`. It returns the same `streamlit` module object as `app._st()` (checked), so
>   session state written through either is read by both. **Patching `app._st` alone does NOT reach the moved helpers**
>   (checked: a fake on `app._st` left `render_help_records` reading real state; a fake on `ui_render._st` reached it).
>   The suite's one fake (around `quota_log_record`) now patches both.
> * Lines: `app.py` 1,748 → **1,352**; `src/ui_render.py` **437** (total 1,789: re-export block + module docstring).
> * **`test_phase05` 179/179, the same 179 check names in the same order** (diffed against HEAD). Changed asserts, each
>   commented in place:
>   * content now in `ui_render`, so it reads `ui_src`: `clarify-render-fn` (button keys; the `render_clarify` call is
>     still checked in `app.py`), `greeting-render-fn` (the `def`), `help-badge-text-in-src`, `routing-trap-text`,
>     `mic-fallback-text`, `drift-surfaced-not-absorbed`, `plain-caption-takes-prior-not-index` (the
>     `_render_history` import; the call sites are still checked in `app.py`);
>   * negatives widened to `src + ui_src` (stricter): `llm-quota-explained`, `no-top-level-generate`,
>     `no-form-widget`, `only-writer-is-quota-log`;
>   * no PLACEMENT assert changed: banner order in `render_turn` / `replay_turn` / `run`, and 4-space banner call sites,
>     still read `app.py`.
>   * `help-confirm-prompt-rendered` is unchanged and still passes through its pre-existing loose `or` clause
>     (`"confirm_prompt" in src`, now satisfied by `build_speech_text`).
> * **Break tests** (`ui_render` mutated, then restored and checked byte-identical): badge text removed →
>   `help-badge-text-in-src` FAIL; filter state ignored → `minor-help-returns-filtered-records` FAIL; a `write_text(`
>   added → `only-writer-is-quota-log` FAIL.
> * `eval_heldout.py` and `eval_chat.py` stdout, before vs after (`runs\h8b\before|after\`): `eval_chat` **byte-identical**;
>   `eval_heldout` differs only on one line, a timestamped Streamlit bare-mode warning.
> * `test_phase03` 24/24 + 16/16 · `test_phase04` ALL PASS · `test_phase09_ops` ALL PASS · `audit_corpus` PASS ·
>   `bench_phase01` PASS · `calibrate_refusal` PASS 0/212 · `import app` OK · `import ui_render` OK (it does not
>   import streamlit at import time).
> * **Browser, local only** (HEAD in a detached worktree on :8503 vs the branch on :8502; nothing ran against the live site):
>   * `audit.mjs --mode=matrix`: 33 cells, **0 critical / 0 serious / 0 moderate / 0 minor, before and after,
>     line-identical** (WCAG tags). The Streamlit-internal `aria-allowed-attr` node did not appear in either run.
>   * `minor_check.mjs`: identical before/after except a React-generated id. Skip link is the first Tab stop and moves
>     focus to H1, and is topmost at 1280, at 390 and in HC. Route radio keeps focus on ArrowUp. The NGO filter read-aloud
>     follows the filter. The routing trap re-answers on legal. WCAG axe `[]`; best-practice only the known `heading-order`.
>   * Scratch probe (ArrowDown ×2, ArrowUp ×3): focus stays on the checked radio on 5/5 presses, before and after.
>   * Scratch probe: a legal turn (banner before "Your rights", valid tags, fold, AI expander) and a help turn (banner
>     before "Help near you", 3 Lagos orgs, filter, routing trap). The replayed legal turn keeps its banner and the same
>     tags. JSON is identical before/after.
> * Also: `.claude/rules/ui.md` now path-scopes `src/ui_render.py` too, because the focus/widget-key rules apply to the
>   moved widgets. `CLAUDE.md` architecture line updated (still 210 lines).
