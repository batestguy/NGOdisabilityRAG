# HANDOFF — start here (60 seconds, updated 2026-10-25)

> **■■ 2026-10-25: READ THIS BLOCK FIRST ■■**
>
> **Live: `main` = `6ee7978` (PR #21, merged by the owner and deployed 2026-10-25).** The live check was a page load
> only, so no question was asked and no telemetry was written. No quota was spent.
>
> **H8a.5 is now DONE (reviewed 2026-10-25).** The 2026-10-23 session had committed it and stopped before the reviewer
> pass and the doc close-out. The four commits on `phase11/h8a-accessregs` are **local only (branch 4 ahead of origin)**:
> * `5595763` held-out opt-out flags (`eval_heldout --no-test`, `eval_chat --dev-only`; defaults unchanged);
> * `09e38c1` `CORPUS_VERSION = "v3"`; harnesses take the version budget; v2-only harnesses pinned to v2;
> * `8d56ba0` H6 review pack regenerated on v3 (F10); the v2 sheet kept as `docs/review/h6_review_sheet_v2_2026-10-21.*`;
> * `aeb317f` `scripts/baseline_v3_2026-10-23.txt` (now with an ERRATA block from the review).
>
> **Baseline headline (as the file states it; unreviewed):** existing law identical on v3 (frozen-10 0.734, dev 0.613);
> accessregs-dev2 0.800; test2/test3 *cited* from `h8aR_blind`, not re-run; `test` not scored; 0 false refusals
> everywhere; calibrate 0/212; suites 03/04/09_ops ALL PASS, 05 193/193. Reported, not gated: off-corpus answered
> 13 → 14/17 (OFF12, v3 bridge suspected, undiagnosed); dev strict@3 0.373 → 0.353 and MRR(shown) 0.428 → 0.399;
> chat_dev r@3 drops as Regs chunks enter the pool top; eval_phase06 reverse_rel 0.667 → 0.630.
>
> **⚠ HELPLINE PROVENANCE (checked 2026-10-25, real browser, drac-ng.org home + /contact):** both banner numbers come from
> the owner's spec `RAGNGO.txt` lines 102–103. No earlier record verified them against DRAC.
> * **Toll-Free `08000-3000-100`: VERIFIED.** The site links `tel:080003000100` labelled "Call Now - Toll Free".
> * **WhatsApp `08000-3000-10`: NOT FOUND on DRAC's site.** There is no WhatsApp text or link anywhere. The only other number
>   is `08115326607` (office: Plot 690 Akon House, Wuye, Abuja). A 0800 toll-free number is also an unlikely WhatsApp
>   account. The banner is an invariant and the spec is the owner's, so **the owner decides**: test it on WhatsApp, or
>   replace or remove it. Screenshot: `runs\drac_contact_2026-10-25.png`.
>
> **OWNER RULE 2026-10-25: zero cost, self-review first.** Paid or recruited reviewers (legal H6, language H5b, AT users)
> wait for grant funding (phase F). Self-review gates replace them, honestly labelled "not reviewed by a lawyer". Full
> text and the new order: `docs/phases/19_zero_cost_self_review.md`. It is also an invariant in `CLAUDE.md`.
>
> **Next, in this order (all $0):**
> 1. ~~Reviewer pass on H8a.5~~ **DONE 2026-10-25**: ship to next step; review fixes committed; branch pushed. Open:
>    OFF12 is answered on v3 (pinned by `off12-v3-characterised-answered`), so diagnose the v3 bridge terms (zero quota).
> 2. ~~H6-S.1~~ **LIVE** (PR #21 → `6ee7978`): the notice, the HA/IG/YO notice, the language switcher and the HC fixes.
>    `main` is merged back into `phase11/h8a-accessregs` (conflicts resolved: the AI expander keeps both captions;
>    test_phase05 212/212). **H8a.7 must still re-run the browser matrix on the merged branch** (v3 + switcher).
> 3. ~~H6-S.2~~ **PASS 2026-10-25** (`f7e02b2`): the audit is in CI. The note gained its missing `[Regs general]` tags.
>    **Owner:** keep or drop "subsidiary legislation with legal force", which no source states (listed UNTRACEABLE).
> 4. **On/after 2026-10-28: H7 week-1 read** (discount the 4 smoke ids below).
> 5. **H6-S.3** agent self-review of the H6 sheet, harmful-first, with a quote for each verdict.
> 6. **Owner: book free quota days for H8a.6** (~30 calls, one clean day, no `--failover`). Then H8a.7 merge on the
>    owner's word.
> 7. H9a if approved. H5b is deferred to F2.
>
> **Still open:** owner: approve H9a and decide on `via=suggestion`; is `test` still clean?; are the demo GIF and LinkedIn still wanted? `k_by_doc` (used only by R-b) is undecided. Agent, small: NVDA
> listen-through, `heading-order`, Cedar RECHECK, Streamlit 1.66 `aria-expanded`. `scripts/eval_tmp.json` (untracked,
> 2026-09-20) is a stale scratch output; leave it or delete it, but never commit it.
>
> The 2026-10-23 block moved to `docs/history/handoff_history.md`.

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
