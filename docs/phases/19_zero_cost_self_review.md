# Phase 19 — Zero-cost operation and self-review (owner rule, 2026-10-25)

## The rule

The owner, 2026-10-25: *build all of this at zero cost. Legal and language reviewers are expensive. They come only
after we have done our best and tested ourselves rigorously, perhaps after grants fund the project properly. Ask me to
evaluate when I can.*

This rule binds every phase, past and future:

1. **$0.00, always.** Free tiers only: Render free, the Gemini free quota (under its existing quota discipline), GitHub
   free CI, and local tools in `drlca-rag`. No paid API, model, host or service, and no usage credits spent on this
   project.
2. **No external human reviewer is a gate.** H6 (legal), H5b's native speakers and any panel of assistive-technology
   users are **deferred to the funded phase (F, below)**. No step waits on a person the project would have to pay or
   recruit.
3. **Self-review gates replace them.** Each one is reproducible, written down before its result is seen, checked against
   the primary text, and **honestly labelled**: *checked by the project against the official text, not reviewed by a
   lawyer*. Never claim or imply expert review anywhere: UI, docs, README or a grant application.
4. **The owner evaluates when they can.** Owner checks are short (about 15 minutes, 5 to 15 rows), optional, and never block
   a step. Only the existing owner-only acts stay blocking: every deploy or merge to `main`, signatures (licence lines,
   `act2018_v2_corrections.json`), and held-out or quota decisions.
5. **Honesty to users stands in for the missing sign-off.** The app must say plainly that it gives general information
   from the text of the law, that this is not legal advice, that no lawyer has checked it yet, and where to get help
   (DRAC). A grep on 2026-10-25 found **no such wording** in `app.py` or `src/`, which is why H6-S.1 is first.
6. **Stay ready for a grant.** Keep every review pack current (`docs/review/h6_review_sheet.*` on the shipping corpus,
   H6-S results, the open-questions list below), so a funded reviewer can start the day money arrives.

Unchanged: helplines first, citation tags, both refusal layers, offline default, held-out and quota discipline,
branch per change.

## H6-S — internal legal self-audit (zero $, replaces H6 as a ship gate)

Gates are fixed here, before any result.

### H6-S.1 — disclosure (UI, zero quota)

* Read `.claude/rules/ui.md` first. Add one short plain-language line, shown once near the top of the page **after the
  helpline banner** (helplines stay first), and once inside the AI expander. Draft text, which the owner may reword:
  *"This site gives general information from the text of Nigerian law. It is not legal advice, and no lawyer has
  checked it yet. For help with your own situation, call DRAC on the numbers above."*
* Read aloud with the page. No new widget key, so focus is unaffected.
* **Gate:** `test_phase05` asserts the line is present and sits after the banner; axe matrix 0; keyboard and skip link
  unchanged; existing source-text asserts are untouched.
* Branch `phase11/h6s-disclosure` from `main`. It can ship on its own (owner's word), because it protects live users
  now, independent of H8a.

### H6-S.2 — fixed-text traceability (script, offline)

* `scripts/audit_fixed_text.py`. Every hand-written text a user sees that states law (today
  `rag.DOC_STATUS_NOTES`; any future fixed text) is listed as claims. Each claim names its source tag and the phrases and
  numbers that must appear **verbatim** (whitespace-normalised) in that tag's chunk text: `S.I. No. 51 of 2023`,
  `section 56`, `22nd day of May, 2023`, `500,000`, `2,000,000`, `90`, and the "not giving up the right to go to court"
  wording of Act cl. 8, and so on.
* **Gate:** 100% of claims traced. An untraceable claim is reworded to the source's own words or removed, never kept on
  belief. The commencement date stays as the gazette prints it. "22 May vs 7 July 2023" goes on the open-questions
  list and is not decided by us.
* Join `scripts/test_phase09_ops.py` (zero network) so CI keeps the note honest when anyone edits it.
* The `DOC_STATUS_NOTES` comment in `src/rag.py` that says it waits for "the H6 legal reviewer" is updated to point here.

### H6-S.3 — self-review of the H6 sheet (fresh-eyes agent, $0 on the subscription)

* A `reviewer` subagent (Sonnet 5.5, `high`) reads the current `docs/review/h6_review_sheet.md` **and the primary
  chunk text**. It marks the same four boxes (correct / partially / wrong / harmful), and for every verdict gives a
  verbatim supporting quote with its tag. It reads **harmful-first**: deadlines, waiving a claim, going to court,
  penalties, exemptions, anything that could make a person give up a right.
* Output: `docs/review/h6s_self_review_<date>.csv`, headed **"AGENT SELF-REVIEW — NOT A LAWYER"**.
* The main session re-checks every non-`correct` row and 5 random `correct` rows against the source. The owner may
  spot-check 5 rows.
* Routing is H6 step 3 unchanged: corpus text error → human-signed corrections file; answer-shape error → new prompt
  version; retrieval miss → candidate dev question.
* **Gate:** 0 `harmful` rows left without a fix or a disclosure; every `wrong` row has a fix or a written decision; the
  AI expander's "recommendable" status is re-confirmed or withdrawn in writing.
* **Known limit, stated wherever results are cited:** an LLM reviewing LLM answers shares its blind spots. This is
  evidence of care, not of legal correctness. That is exactly why F1 exists.

**H6-S exit:** S.1 on a branch with its gate met, S.2 PASS, S.3 recorded and routed.

## H5b — languages without native speakers

H5b (Yoruba / Hausa / Igbo) **stays not started**. A machine-only self-test (back-translation, tags and helplines
byte-preserved) can catch mechanical breakage, but not wrong meaning about rights, and wrong meaning is the harm. So no
language ships as "supported" before F2. Do not spend quota on it now. The owner may revisit this.

## Order (replaces the H6 dependencies in playbooks 16, 17 and 18)

1. H8a.5 reviewer pass and close-out (`HANDOFF.md`).
2. H6-S.1 (it protects live users; separate branch from `main`), then H6-S.2 on the H8a branch.
3. H7 week-1 read on/after 2026-10-28.
4. H6-S.3 on the current sheet.
5. H8a.6 on free quota days the owner books. Its gate adds an H6-S.3-style self-review of every new-doc answer.
6. H8a.7: merge on the owner's word. H6-S replaces "H6 returned" (F10).
7. H9a whenever approved. H9b's human gate becomes the owner's read (plus the H6-S.3 method), not H6.

## F — funded phase (after grants)

* **F1 legal review:** send the current H6 sheet, the H6-S results and the open questions below to a Nigerian lawyer or
  a JONAPWD/DRAC contact (H6 steps 2–3 as written in playbook 16).
* **F2 native speakers** for H5b.
* **F3 assistive-technology user testing** with persons with disabilities (NVDA/TalkBack, low vision, voice).
* **Open legal questions to carry to F1:** the Regulations' commencement (22 May) vs the gazette date (7 July 2023);
  verbatim reuse of Nigerian Acts and S.I.s in a free tool (`docs/h8a_source_dossier.md`); any later amendment to the
  Regulations; how far the 2018 Act gives effect to the CRPD; whether a Regs card on employment questions and the
  110-word note on about 86% of v3 turns are acceptable.

## Results

> **2026-10-25 — rule recorded; H6-S not started.** The policy is written into `CLAUDE.md`, playbooks 16, 17 and 18,
> the source dossier, `HANDOFF.md`, `STATUS.md` and the learning journal. No code changed.
>
> **H6-S.1 — 2026-10-25, BUILT on `phase11/h6s-disclosure` (from `main`; `b2bac54`; not merged).**
> `app.LEGAL_INFO_NOTICE` renders as a caption directly after the helpline banner in `run()` and inside the AI expander.
> The text is the draft above, so the owner may reword it.
> * `test_phase05` 183/183 (+4 asserts: wording, never claims review, after the banner, in the expander). Break-tested:
>   removing the caption FAILs `h6s-notice-after-banner-in-run`. 03/04/09_ops ALL PASS. `import app` OK.
> * Browser (local :8503 only): axe matrix 33 cells 0/0/0/0. `minor_check`: WCAG axe `[]` (the known `heading-order`
>   only), skip link topmost at 390 px and in HC, no page errors. DOM text order: title → banner → notice.
> * Not done: a spoken read-aloud copy (screen readers read the caption as page text; the per-turn read-aloud button
>   is for answers). Merging deploys, so it waits for the owner's word.
>
> **H6-S.1 + translations — 2026-10-25 (`c025a73`, same branch, not merged).** At the owner's request the notice also
> appears in **Hausa, Igbo and Yorùbá**, in a collapsed expander right after the English line. Each paragraph has its
> own `lang` (ha/ig/yo) so screen readers switch voice. The expander is labelled *"Translated by this project and not
> yet checked by a native speaker. If a translation and the English differ, follow the English."*
> * This is **fixed text only**. No answer is translated, so H5b stays deferred. The native-speaker check of these
>   three paragraphs joins F2.
> * Checks: `test_phase05` 187/187 (+4). Axe matrix 0 over 33 cells. Expander opened with Enter on its summary: open,
>   focus kept, WCAG axe `[]`. Screenshots at 1280 and 360 px in `runs\h6s1_tr\` show the diacritics render.
>
> **High-contrast fix — 2026-10-25 (same branch).** The owner's screenshot showed the HC help tooltip as white on white.
> Playwright measured four defects that had been there since before H6-S: the tooltip surface `#f6f8fa`; the `?` icon
> strokes `rgba(13,17,23,.6)` on black, so the icons were invisible; the expander header's surface not pinned; and
> captions at opacity 0.6, which included the new notice. All four are now pinned black/white in the HC overlay.
> Computed styles were verified in light and dark themes. `test_phase05` 188/188, axe matrix 0, `minor_check` clean.
> **Lesson:** axe passes 60% grey on black (about 7:1), but an HC user asked for full strength. The owner's eyes caught
> what the gate allowed.
>
> **Interface-language switcher — 2026-10-25 (`e51ad50` + `44aad57`, same branch, not merged; owner request).**
> `src/ui_i18n.py` covers English, Hausa, Igbo and Yorùbá. It is **chrome only**: the sidebar headings and control labels,
> the banner wording, the instructions, the answer headings, the voice expander and the chat placeholder.
> * **Never translated:** the law (excerpts are marked `lang="en"`, and a translated line says the law is quoted in its
>   official English text), citation tags, helpline numbers, and answers. H5b stays deferred.
> * **How state survives a switch:** a sidebar radio comes first, with a stable multilingual label and code options. Every
>   translated control carries `key=` (new: `hc`, `font-size`). The route radio keeps English values with
>   `format_func=T`. `<html lang>` follows the choice through the theme-watch loop.
> * **Labelling:** a non-English UI shows the translated notice plus "translated by this project, not native-checked".
> * **Checks:** `test_phase05` 197/197 (+9 i18n asserts: every key used and complete; no digits, DRAC or tags in any
>   translation; the law is never passed to `T`; the selector comes first; state keys present). Axe matrix 0. In a
>   Playwright run, switching by keyboard (ArrowRight) kept focus on the radio, kept HC and the route, and set
>   `lang=ha`. A Yorùbá-UI legal turn showed English excerpts with `lang=en`, unchanged tags, and WCAG axe `[]`.
> * **Tooling fix the switcher exposed:** `minor_check.mjs` and `live_smoke_a11y.mjs` drove the *first* checked sidebar
>   radio, which is now the language picker. They are now scoped to the route group, and `minor_check` passes in full again.
> * **Still English (next pass):** help tooltips, the "Next question" caption, "I treated this as…", "Switch to …",
>   "Read answer aloud", "Was this answer helpful?" plus Yes/No (they are telemetry values, so only `format_func` may
>   change them), the privacy note, the NGO filters, the AI expander and the title. Read-aloud stays English
>   (`en-NG` voice).
>
> **H6-S.2 — 2026-10-25, PASS (`f7e02b2`, branch `phase11/h8a-accessregs`, where the note lives).**
> `scripts/audit_fixed_text.py` keeps a claim ledger for `rag.DOC_STATUS_NOTES`. The ledger has 10 claims: 3 verbatim,
> 6 declared paraphrases (each with a `why`) and 1 interpretive. Every evidence phrase is found in its cited chunk,
> matching case-, space- and punctuation-insensitively because the gazette OCR runs words together. The corpus text is
> untouched. The audit also checks tags, every printed number, and sentence coverage. It runs in CI.
> * **Finding 1, fixed:** the S.I. number, the Governing Council and the 22 May 2023 commencement come from the
>   Regulations' enacting formula, but the note never showed that source's tag. That broke the invariant that every
>   legal claim carries a tag. `[Regs general]` was added after both sentences; no word was changed. The H6 sheet was
>   regenerated (note text only).
> * **Finding 2, owner / F1:** "subsidiary legislation with legal force" is a legal characterisation that no source
>   sentence states. It is listed as UNTRACEABLE on every run, not failed, because the text is owner-signed.
> * **Paraphrases recorded:** "breaks them" stands for "contravenes the provisions of these Regulations"; "regardless
>   of" for "notwithstanding"; "place" for "built environment" (the 90-day notice goes to the owner, manager, occupier
>   or developer); "without giving up your right to go to court" for "without prejudice to his right to seek redress in
>   court". cl. 8(1) is "Subject to section 7", which the note omits.
> * **Break tests:** each of these FAILs: 500,000 → 50,000; 90-day → 30-day; a dropped `[Regs reg. 169]`; an
>   unledgered sentence with a new figure. Changing the note and the ledger together still FAILs, because the evidence
>   must exist in the source.
> * **Regression:** `test_phase05` 194/194; 03/04/09_ops ALL PASS; `audit_corpus` PASS; `eval_h8aR` G5′ PASS, and its
>   dev stage is identical to `scripts/h8aR_dev_stage_2026-10-23.txt`.
>
> **H6-S.1 LIVE — 2026-10-25.** PR #21 was merged by the owner, using the `!` command because auto mode blocks agent
> merges to `main`. Render deployed `6ee7978`. The live check was a page load only, so no telemetry was written: the
> order is title → helplines → notice; the translations box is present; switching to Hausa sets `lang=ha` and keeps both
> numbers; WCAG axe `[]`. `main` was merged back into the H8a branch.
