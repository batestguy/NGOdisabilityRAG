# STATUS — current state (updated 2026-10-22)

Current state only. Replace lines; do not append history. Dated history to 2026-10-22:
`docs/history/status_history.md`. Phase records: `docs/phases/`. Narrative: `LEARNING_JOURNAL.md`.

## Live

- **https://ngodisabilityrag.onrender.com** (Render free, `srv-dah26opt0dsc73e9a350`), `main` = `94db479`
  (PR #20: H8 playbook + H8c + H8b; deployed and live-smoked 2026-10-22).
- Multi-turn chat; helplines first on the page and on every turn; offline by default; Gemini AI expander
  opt-in, default OFF (`cite-strict-v3` / `chat-cite-strict-v2`, "recommendable" per Phase G).
- Corpus v2 (Act gazette-OCR, clause-aligned, cl.1/12/20 corrections signed; Constitution; Factsheet).
  Retrieval `k=4/doc, top_n=12`, hand `SYNONYMS` + OOV bridge, `MIN_SCORE = 0.10`.
- NGO directory: 20 verified orgs, 6 zones, filter/sort (H3). Cedar Foundation = RECHECK (website blank).
- Accessibility: WCAG 2.2 AA audit (H2) + leftovers fixed (skip link, landmarks, native route radio,
  single-name slider, read-aloud follows NGO filter). Axe WCAG matrix 0 (local, 2026-10-22).
- H7 counts-only "Was this answer helpful?" signal in Render logs (`DRLCA_SIGNAL`).
- CI: `.github/workflows/offline-suites.yml` on every PR and push.

## Numbers (current)

- Retrieval (`scripts/baseline_phaseE_2026-09-24.txt`): recall_strict frozen-10 0.734 · dev 0.613 ·
  test 0.647 · test2 0.629. False refusals 0 on every set. `calibrate_refusal` 0/212.
- Generation (Phase G, 2026-10-15): judge 23/23, G4 0 cross-turn drift, G6 10/10 answered, 0 fabricated tags.
- Suites (2026-10-22): `test_phase03` matrix 24/24 + statics 16/16 · `test_phase04` ALL PASS ·
  `test_phase05` 179/179 · `test_phase09_ops` ALL PASS · `import app` + `import ui_render` OK.
- UI code: `app.py` (run / render_turn / replay_turn / history / banner / loaders) 1,352 lines +
  `src/ui_render.py` (shared render helpers, re-exported by `app`) 437 lines (H8b).

## Open

- **Active: H8 — `docs/phases/17_h8_corpus_expansion.md`.** H8c + H8b DONE and live. H8a.0 DONE: the owner
  chose + signed the **Accessibility Regulations 2023 (S.I. 51)** (`docs/h8a_source_dossier.md`; PDF in `data/raw/`).
  **Next: H8a.1** (dev + blind `test3` questions, committed before any parser).
- **H7 week-1 read on/after 2026-10-28** (command in `HANDOFF.md`; discount 4 smoke ids).
- **Owner:** is `test` still clean? · send the H6 review sheet (`docs/review/h6_review_sheet.md`) to a
  legal reviewer · H5b needs 2 quota days (~45 calls) + native Yoruba/Hausa/Igbo checkers
- **Deferred:** NGO directory growth past 20 (no Facebook route). Old owner items (demo GIF encode, LinkedIn) are in `docs/history/status_history.md`; still wanted?
- **Small:** NVDA listen-through of radio + skip link · best-practice `heading-order` (H1 → H3) ·
  Cedar RECHECK · Streamlit 1.66 bump (`aria-expanded` migration).
- **Unmerged branch:** `phase11/h8a-sources` (pushed; dossier + Regs PDF + records; merging redeploys, so bundle with H8a code).
