# HANDOFF — start here (60 seconds, updated 2026-10-22)

> **■ 2026-10-22 (latest): H8b DONE → `ef9ae90` + `3b02875` on `phase11/h8b-split`** (stacked on `phase11/h8c-docs`;
> not pushed, not merged). 11 render helpers moved verbatim to `src/ui_render.py` (`app.py` 1,748 → 1,352). The other 3
> stay in `app.py` because they compute with app state. Reviewer SHIP: AST-identical move, test_phase05 179/179 with the
> same names, `eval_chat` byte-identical, axe 0, focus probes identical. **Trap:** to fake Streamlit in a test, patch BOTH
> `app._st` and `ui_render._st`. **Next:** the owner decides whether to push and open a PR for the stack (H8 playbook + H8c +
> H8b). Merging deploys, so that is the owner's call. H8a waits on the H7 read (on/after 2026-10-28) and the H6 return.

> **■ 2026-10-22 (later): H8c DONE → `fc168ae` on `phase11/h8c-docs`** (stacked on `phase11/docs-a11y-deploy`; not
> pushed, not merged). `CLAUDE.md` is 210 lines plus `.claude/rules/{retrieval,ui}.md`, and history is in `docs/history/`.
> **First thing next session: run `/context` and confirm neither rules file loads at startup.** Next: H8b (split
> `app.py` helpers, branch from `phase11/h8c-docs`).

> **■ 2026-10-22: H8 PLAYBOOK WRITTEN → `docs/phases/17_h8_corpus_expansion.md`** (docs only, zero quota,
> committed `2325e29` on `phase11/docs-a11y-deploy`). Main finding: a 4th legal document is a Phase-D-sized
> change. `top_n == 3k` must become `4k` (a measured arm); the prompt needs `cite-strict-v4`, so the G evidence
> lapses until a ~30-call re-run; and the OOV bridge must become version-keyed or v2 stops reproducing.
> * **Order:** H8c (slim CLAUDE.md / STATUS / HANDOFF) → H8b (split `app.py` helpers) → H8a.0 (source dossier) →
>   H8a.1–7 after the H7 week-1 read and the H6 return.
> * **Owner:** approve the order; for H8a.0, pick ONE document (candidates: NCPWD Accessibility Regulations 2023,
>   UN CRPD, Lagos Special People's Law 2011; none verified yet) and sign its licence line.
> * Everything in the 2026-10-21 block below still stands (signal read on/after 2026-10-28).

> **■■ 2026-10-21 END OF SESSION: READ THIS BLOCK FIRST ■■**
>
> **Live on Render (`main` = `0eb8959`).** Two deploys today, both on the owner's explicit word, both CI green and smoked live:
> * **PR #18 → `bf1f6ba`:** H7 counts-only "Was this answer helpful?" signal. Production `DRLCA_SIGNAL` lines are confirmed in Render's
>   logs. They carry only the documented fields and no question text.
> * **PR #19 → `0eb8959`:** the four H2/H3 a11y leftovers fixed:
>   * read-aloud follows the NGO filter;
>   * the route choice is a native radio group;
>   * the slider has a single name;
>   * a skip link and named landmarks.
>
>   PR #19 also carried the H7 deploy record and the **H6 review pack** (`docs/review/h6_review_sheet.{csv,md}`, 30 rows, zero quota).
>   The reviewer blocked the first a11y attempt (focus loss on the route buttons) and passed the fix.
>
> **Housekeeping done:**
> * stale PRs #10 and #11 closed (all their commits were already in `main`);
> * PR #17 auto-merged via #18;
> * Render CLI reinstalled and logged in (`%LOCALAPPDATA%/Programs/render-cli/render.exe`, v2.28.0);
> * the tool-results file that held the `test` questions deleted, unread.
>
> **Unmerged (docs only; merging redeploys, so bundle with the next code merge):** `phase11/docs-a11y-deploy` (this record).
>
> **Telemetry lines to DISCOUNT in the week-1 read:** `b9be6975e327`, `7cba04a4cbd6`, `6c1d650bf360`, `cf37bfd78551` (agent smoke
> runs, all `turn`, no `helpful`).
>
> **Next:**
> 1. **On/after 2026-10-28 (agent):** `render logs -r srv-dah26opt0dsc73e9a350 --text DRLCA_SIGNAL --limit 100 --direction backward -o text --confirm`
>    → file → `scripts/summarise_signal.py` (minus the 4 ids) → H7 results box. Then decide which of M2 / F2 / H5a to reopen, each
>    with a new pre-declared gate.
> 2. **Owner decisions:**
>    * Does `test` still count as unread? An agent command printed it into a temp file, which no model is known to have read; the file is now deleted.
>    * Send the H6 sheet to a legal reviewer.
>    * H5b needs 2 days of Gemini quota (about 45 calls) and native Yoruba, Hausa and Igbo checkers.
> 3. **Agent, small, open:**
>    * an NVDA listen-through of the new radio and skip link;
>    * best-practice `heading-order` (H1 → H3 "Conversation so far");
>    * Cedar Foundation RECHECK;
>    * the Streamlit 1.66 `aria-expanded` migration (H2 CSS + bridge);
>    * plan H8 (corpus expansion) as a playbook first.
>
> **Gotchas learned today:**
> * Auto mode sometimes blocks `gh pr merge` to `main` even with the owner's yes (it allowed #19 and blocked #18). If it blocks,
>   give the owner the exact `!` command.
> * Changing a Streamlit button's label remounts it and drops keyboard focus. Prefer native widgets, and **test focus** as well as state.
> * Smoke runs that ask a question write production telemetry, and retry loops multiply that. Count attempts, and record the ids.
> * Earlier axe baselines use WCAG tags only, so best-practice findings are not regressions against them.
> * The control-character scan must also count lone `\r`. A heredoc turned `\r` into a carriage return three times today. Write such text with the Edit tool, not a heredoc.
> * Render's log API returns transient 503s; retry.
> * The free instance paints the turn slowly, so smoke scripts must wait for elements and not use fixed sleeps.

---

Older blocks (2026-09-10 → 2026-10-21) moved verbatim to `docs/history/handoff_history.md` by H8c on 2026-10-22.
Durable rules live in `CLAUDE.md` and `.claude/rules/*.md`; current state in `STATUS.md`.

## Standing facts (still true 2026-10-22)

- **Render CLI:** `%LOCALAPPDATA%/Programs/render-cli/render.exe` (v2.28.0, logged in). Signal read:
  `render logs -r srv-dah26opt0dsc73e9a350 --text DRLCA_SIGNAL --limit 100 --direction backward -o text --confirm`.
  The log API returns transient 503s; retry after ~30 s.
- **Held-out state:** `test2` clean. `test` cleanliness is the owner's open decision. Unread blind sets:
  `data/eval/offtopic_h4.json` (all), the `pidgin_test` half of `data/eval/pidgin_h5a.json`.
- **Telemetry ids to discount** in the week-1 read: `b9be6975e327`, `7cba04a4cbd6`, `6c1d650bf360`, `cf37bfd78551`.
- **H5b design notes** (calls per question = 3, mask tags/helplines before translate-out, fail closed) are in the
  2026-10-18 block of `docs/history/handoff_history.md`.
- Writing text with `\r` or other control characters: use the Edit tool, not a heredoc.
