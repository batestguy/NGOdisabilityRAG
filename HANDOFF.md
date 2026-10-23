# HANDOFF — start here (60 seconds, updated 2026-10-23)

> **■■ 2026-10-23 END OF SESSION: READ THIS BLOCK FIRST ■■**
>
> **Live: unchanged, `main` = `94db479`.** Today ran no deploy, no quota and no telemetry.
>
> **Done today (branch `phase11/h8a-accessregs`, cut from `phase11/h8a-sources`; pushed; NOT merged):**
> * **H8c `/context` check PASSED.** At startup only the global `CLAUDE.md`, project `CLAUDE.md` and `MEMORY.md` load.
>   `.claude/rules/retrieval.md` loaded lazily the first time a `data/processed/` file was read, which is the intended behaviour.
> * **H8a.1 DONE (exit gate met).** `data/eval/questions_accessregs.json` was committed alone as **`af3129e`**, before any
>   parser: **dev 8 / blind `test3` 12 / status 6**, with 5 Pidgin questions. Refs come from the gazette text.
>   **Do not read `test3` again.**
> * The H8a.2 findings are in playbook 17's Results: the commencement date is resolved (22 May 2023); the enacting formula is
>   unnumbered and AR_S04 has empty `expected`; the Arrangement mislabels reg. 133 as "132"; there are two look-alike
>   certificates (reg. 165 vs 166); the naira sign is printed as "N". The gazette text for reading lives in
>   `runs\h8a1
egs_compact.txt` (gitignored).
>
> * **H8a.2 DONE** (executor, then reviewer: "ship to H8a.3"). Commits `44f5a7b` F7 bridge, `0ef9b9e` parser, `fbfe5a2` v3
>   wiring, `af96f0d` review fixes.
>   * Corpus **v3** = v2 + `accessregs2023` (221 chunks, `[Regs reg. N]`), pin `f13b9678…`, `oov_bridge_v3.json`.
>   * v2 is proven bit-identical (fingerprint, pins, 0/212, PORT CHECK).
>   * `CORPUS_VERSION` is still `"v2"`.
>   * Details and warnings are in playbook 17's Results.
>
> **Next session, in this order:**
> 1. **H8a.3 measure (zero quota).** The gate is already written in playbook 17. Run three arms: v2 control, v3 at
>    `top_n=12`, v3 at `top_n=16`.
>    * Read dev and the selection sets first. `test2` and `test3` are read **once, at the end, for the chosen arm only**.
>      Never read `test`.
>    * The harnesses (`eval_heldout`, `calibrate_refusal`) need `--corpus=v3` plus a set loader for
>      `questions_accessregs.json`. Write those **before** looking at any v3 number.
>    * Do not point the `ablate_*` harnesses at v3 (they raise TypeError or use the wrong bridge).
>    * Watch `[Regs general]` (the preamble) in the per-question diff. The reviewer saw it in 11/40 existing-law top-12s,
>      and 38/40 questions lose a v2 hit.
> 2. The H8a.5 cut-over still waits for the H6 legal review to return.
> 3. H9a (suggested follow-ups) can run in parallel once the owner approves it.
>
> **Still open (unchanged from 2026-10-22):** the H7 week-1 read is on/after **2026-10-28** (discount the 4 smoke ids).
> **Owner:** approve H9a and decide on `via=suggestion`; is `test` still clean?; send the H6 sheet; H5b needs quota days and
> native checkers; are the demo GIF and LinkedIn still wanted? **Agent, small:** NVDA listen-through, `heading-order`,
> Cedar RECHECK, Streamlit 1.66 `aria-expanded`.
>
> The 2026-10-22 block moved to `docs/history/handoff_history.md`.

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
