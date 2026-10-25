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
