# HANDOFF — start here (60 seconds, updated 2026-10-22)

> **■■ 2026-10-22 END OF SESSION: READ THIS BLOCK FIRST ■■**
>
> **Live: `main` = `94db479`** (PR #20 = H8 playbook + H8c doc split + H8b `app.py` → `src/ui_render.py`; merged on the
> owner's word). CI green; Render `dep-dbcrr8k9v7es73bse4u0` live 07:41 UTC. The live smoke `live_smoke_a11y.mjs` PASSED.
> It asks no question, so there are **no new telemetry ids to discount**.
>
> **Branch `phase11/h8a-sources` (pushed, docs + one raw PDF; NOT merged: merging redeploys, so bundle it with H8a code):**
> * **H8a.0 DONE.** The owner chose the **Persons with Disabilities (Accessibility) Regulations, 2023 (S.I. No. 51 of 2023)**
>   and signed the reuse line ("go with the Accessibility Regulations, I sign off").
> * Dossier: `docs/h8a_source_dossier.md`. PDF: `data/raw/accessibility_regulations_2023_gazette_FGP.pdf`
>   (sha256 `04bb8bec…8b05`, row in `data/raw/SOURCES.md`).
> * Born-digital: regulations 1–172 on pp. 9–68 (the Arrangement on pp. 3–8 is the manifest). The First Schedule figures,
>   pp. 69–172, are images; exclude them.
>
> **Next session, in this order:**
> 1. **Run `/context` once.** Confirm `.claude/rules/retrieval.md` and `ui.md` do NOT load at startup (H8c check, never run).
> 2. ~~Ask about the Act gazette~~ **Answered 2026-10-22: the reuse sign-off covers the live Act gazette too** (recorded in the dossier).
> 3. **H8a.1 (zero quota), branch from `phase11/h8a-sources`.** Spec: `docs/phases/17_h8_corpus_expansion.md` H8a.1.
>    * Author **~20 questions from the official PDF text**, before any parser exists: **dev ~8** and a blind **`test3` ~12**,
>      plus **~6 status probes**. For the Regulations a status probe asks things like "what law lets the Commission make these
>      rules?", where the right evidence is `[Act cl. 56]`, and "is there a fine?" (reg. 168, ₦500,000 minimum).
>    * Mix plain, lay and Pidgin register (e.g. "my office get no ramp, wetin law talk?").
>    * Expected refs = regulation numbers read from the PDF. Proposed tag `[Regs reg. N]`, `doc_id` `accessregs2023`. The tag
>      is not wired yet; H8a.2 does that.
>    * Put them in a new file (e.g. `data/eval/questions_accessregs.json`). Do NOT touch `questions.json`, `questions_test2.json`
>      or the frozen-10.
>    * **Commit the questions in their own commit before writing any parsing code** (the E5.2 `test2` procedure). Do not read
>      `test3` again after authoring.
>    * Extract text only to read it while authoring: `C:\conda-envs\drlca-rag\python.exe -I` with PyMuPDF, output to `runs\`.
>      The parser comes in H8a.2.
> 4. **H8a.2 onward:** start only after H8a.1 is committed. Read playbook 17's F1–F10 first; the OOV bridge must become
>    version-keyed before anything else (F7). **H8a.5 cut-over waits for the H6 legal review to return.**
>
> **Queued after H8a: H9, deterministic follow-ups → `docs/phases/18_h9_deterministic_followups.md`** (planned 2026-10-22,
> zero quota). **H9a** adds suggested follow-up questions built from gazette clause titles; it is low risk and can run while
> H8a waits on H6. **H9b** adds extractive cited "key lines"; it is moderate risk and comes after the H6 review + H7 read.
> A composed rule-based answer was considered and rejected (reasons are in the playbook). **Owner:** approve H9a; decide
> whether to allow a counts-only `via=suggestion` telemetry field.
>
> **Still open (unchanged):**
> * **H7 week-1 signal read on/after 2026-10-28:** command in Standing facts → file → `scripts/summarise_signal.py` minus the
>   4 smoke ids → H7 results box (`docs/phases/16_post_launch_roadmap.md`). Then decide which of M2 / F2 / H5a to reopen,
>   each with a new pre-declared gate.
> * **Owner:** is `test` still clean? · send the H6 sheet (`docs/review/h6_review_sheet.md`) to a legal reviewer (optionally
>   adding the one-line reuse question) · H5b needs 2 quota days (~45 calls) + native Yoruba/Hausa/Igbo checkers · demo GIF
>   and LinkedIn still wanted? (old items; frames in `docs/demo/` are from September and out of date).
> * **Agent, small:** NVDA listen-through of the radio and skip link · best-practice `heading-order` (H1 → H3) · Cedar
>   Foundation RECHECK · Streamlit 1.66 `aria-expanded` migration (own branch).
>
> The 2026-10-21 and earlier 2026-10-22 blocks are in `docs/history/handoff_history.md`. Their gotchas now live in
> `CLAUDE.md`, `.claude/rules/ui.md` and Standing facts below.

---

Older blocks (2026-09-10 → 2026-10-22) moved verbatim to `docs/history/handoff_history.md` by H8c on 2026-10-22.
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
